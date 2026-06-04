import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';

import '../database/dao/sync_state_dao.dart';
import '../database/local_db.dart';
import '../database/tables.dart';
import 'api_service.dart';
import 'secure_storage_service.dart';
import 'settings_service.dart';

enum SyncStatus { offline, idle, syncing, error }

class SyncService {
  SyncService({
    required LocalDb db,
    required ApiService api,
    required SecureStorageService secureStorage,
    required SettingsService settings,
    Connectivity? connectivity,
  })  : _db = db,
        _api = api,
        _secure = secureStorage,
        _settings = settings,
        _connectivity = connectivity ?? Connectivity(),
        _syncState = SyncStateDao(db);

  final LocalDb _db;
  final ApiService _api;
  final SecureStorageService _secure;
  final SettingsService _settings;
  final Connectivity _connectivity;
  final SyncStateDao _syncState;

  Timer? _timer;

  SyncStatus status = SyncStatus.idle;
  DateTime? lastSyncAt;
  String? lastError;

  Future<void> bootstrap() async {
    if (kIsWeb) {
      status = SyncStatus.idle;
      return;
    }
    final raw = await _syncState.getValue('last_sync_at');
    lastSyncAt = raw != null && raw.isNotEmpty ? DateTime.tryParse(raw) : null;
  }

  void start() {
    if (kIsWeb) return;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) {
      unawaited(syncOnce());
    });
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> syncOnce() async {
    if (kIsWeb) {
      status = SyncStatus.idle;
      return;
    }
    final online = await _isOnline();
    if (!online) {
      status = SyncStatus.offline;
      return;
    }

    final baseUrl = _settings.apiBaseUrl.trim();
    if (baseUrl.isEmpty) {
      status = SyncStatus.idle;
      return;
    }

    // This Django mobile sync API is protected by the logged-in user's JWT.
    // Keep sync quiet until a user has an online session.
    final accessToken = await _secure.getAccessToken();
    if (accessToken.isEmpty) {
      status = SyncStatus.idle;
      return;
    }

    final userId = await _secure.getUserId();
    final businessId = _settings.selectedBusinessId.trim();
    if (userId.isEmpty || businessId.isEmpty) {
      status = SyncStatus.idle;
      return;
    }

    status = SyncStatus.syncing;
    try {
      await _pushUnsynced(userId: userId, businessId: businessId);
      await _pullUpdates(userId: userId, businessId: businessId);

      final now = DateTime.now();
      lastSyncAt = now;
      await _syncState.setValue('last_sync_at', now.toIso8601String());
      lastError = null;
      status = SyncStatus.idle;
    } catch (e) {
      lastError = e.toString();
      status = SyncStatus.error;
    }
  }

  Future<void> _pushUnsynced({
    required String userId,
    required String businessId,
  }) async {
    // Push: customers (from parties), products, invoices, invoice_items, payments (from transactions).
    await _pushPartiesAsCustomers(userId: userId, businessId: businessId);
    await _pushProducts(userId: userId, businessId: businessId);
    await _pushInvoices(userId: userId, businessId: businessId);
    await _pushInvoiceItems(userId: userId, businessId: businessId);
    await _pushTransactionsAsPayments(userId: userId, businessId: businessId);
  }

  Future<void> _pushPartiesAsCustomers({
    required String userId,
    required String businessId,
  }) async {
    final rows = await _db.query(
      Tables.parties,
      where:
          'business_id = ? AND type = ? AND is_synced = 0 AND is_deleted = 0',
      whereArgs: [businessId, 'customer'],
      orderBy: 'updated_at ASC',
      limit: 200,
    );
    if (rows.isEmpty) return;

    final payloadRows = rows
        .map(
          (r) => {
            'id': (r['id'] ?? '').toString(),
            'user_id': userId,
            'name': (r['name'] ?? '').toString(),
            'phone': r['phone']?.toString(),
            'address': r['address']?.toString(),
            'created_at': (r['created_at'] ?? '').toString(),
            'updated_at': (r['updated_at'] ?? '').toString(),
            'is_synced': 0,
          },
        )
        .toList();

    final res = await _api.postJson(
      '/api/v1/mobile/sync/push/',
      {'user_id': userId, 'table': 'customers', 'rows': payloadRows},
    );
    if (res['ok'] != true) throw Exception('Push failed: customers');

    final now = DateTime.now().toIso8601String();
    await _db.transaction((txn) async {
      for (final r in rows) {
        final id = (r['id'] ?? '').toString();
        if (id.isEmpty) continue;
        await _db.updateById(
            Tables.parties, id, {'is_synced': 1, 'updated_at': now},
            txn: txn);
      }
    });
  }

  Future<void> _pushProducts({
    required String userId,
    required String businessId,
  }) async {
    final rows = await _db.query(
      Tables.products,
      where: 'business_id = ? AND is_synced = 0 AND is_deleted = 0',
      whereArgs: [businessId],
      orderBy: 'updated_at ASC',
      limit: 200,
    );
    if (rows.isEmpty) return;

    final payloadRows = rows
        .map(
          (r) => {
            'id': (r['id'] ?? '').toString(),
            'user_id': userId,
            'name': (r['name'] ?? '').toString(),
            'sku': r['sku']?.toString(),
            'price': (r['sale_price'] ?? 0),
            'tax_percent': (r['tax_percent'] ?? 0),
            'created_at': (r['created_at'] ?? '').toString(),
            'updated_at': (r['updated_at'] ?? '').toString(),
            'is_synced': 0,
          },
        )
        .toList();

    final res = await _api.postJson(
      '/api/v1/mobile/sync/push/',
      {'user_id': userId, 'table': 'products', 'rows': payloadRows},
    );
    if (res['ok'] != true) throw Exception('Push failed: products');

    final now = DateTime.now().toIso8601String();
    await _db.transaction((txn) async {
      for (final r in rows) {
        final id = (r['id'] ?? '').toString();
        if (id.isEmpty) continue;
        await _db.updateById(
            Tables.products, id, {'is_synced': 1, 'updated_at': now},
            txn: txn);
      }
    });
  }

  Future<void> _pushInvoices({
    required String userId,
    required String businessId,
  }) async {
    final rows = await _db.query(
      Tables.invoices,
      where: 'business_id = ? AND is_synced = 0 AND is_deleted = 0',
      whereArgs: [businessId],
      orderBy: 'updated_at ASC',
      limit: 200,
    );
    if (rows.isEmpty) return;

    final payloadRows = rows
        .map(
          (r) => {
            'id': (r['id'] ?? '').toString(),
            'user_id': userId,
            'customer_id': (r['party_id'] ?? '').toString(),
            'number': (r['number'] ?? '').toString(),
            'status': (r['status'] ?? 'unpaid').toString(),
            'subtotal': (r['subtotal'] ?? 0),
            'discount': (r['discount'] ?? 0),
            'tax': (r['tax'] ?? 0),
            'total': (r['total'] ?? 0),
            'paid': (r['paid'] ?? 0),
            'balance': (r['balance'] ?? 0),
            'created_at': (r['created_at'] ?? '').toString(),
            'updated_at': (r['updated_at'] ?? '').toString(),
            'is_synced': 0,
          },
        )
        .toList();

    final res = await _api.postJson(
      '/api/v1/mobile/sync/push/',
      {'user_id': userId, 'table': 'invoices', 'rows': payloadRows},
    );
    if (res['ok'] != true) throw Exception('Push failed: invoices');

    final now = DateTime.now().toIso8601String();
    await _db.transaction((txn) async {
      for (final r in rows) {
        final id = (r['id'] ?? '').toString();
        if (id.isEmpty) continue;
        await _db.updateById(
            Tables.invoices, id, {'is_synced': 1, 'updated_at': now},
            txn: txn);
      }
    });
  }

  Future<void> _pushInvoiceItems({
    required String userId,
    required String businessId,
  }) async {
    // Invoice items are scoped by invoice_id; push unsynced items.
    final rows = await _db.query(
      Tables.invoiceItems,
      where: 'is_synced = 0 AND is_deleted = 0',
      orderBy: 'updated_at ASC',
      limit: 400,
    );
    if (rows.isEmpty) return;

    final payloadRows = rows
        .map(
          (r) => {
            'id': (r['id'] ?? '').toString(),
            'invoice_id': (r['invoice_id'] ?? '').toString(),
            'product_id': (r['product_id'] ?? '').toString(),
            'name': (r['name'] ?? '').toString(),
            'qty': (r['qty'] ?? 0),
            'unit_price': (r['unit_price'] ?? 0),
            'tax_percent': (r['tax_percent'] ?? 0),
            'line_total': (r['line_total'] ?? 0),
            'created_at': (r['created_at'] ?? '').toString(),
            'updated_at': (r['updated_at'] ?? '').toString(),
            'is_synced': 0,
          },
        )
        .toList();

    final res = await _api.postJson(
      '/api/v1/mobile/sync/push/',
      {'user_id': userId, 'table': 'invoice_items', 'rows': payloadRows},
    );
    if (res['ok'] != true) throw Exception('Push failed: invoice_items');

    final now = DateTime.now().toIso8601String();
    await _db.transaction((txn) async {
      for (final r in rows) {
        final id = (r['id'] ?? '').toString();
        if (id.isEmpty) continue;
        await _db.updateById(
            Tables.invoiceItems, id, {'is_synced': 1, 'updated_at': now},
            txn: txn);
      }
    });
  }

  Future<void> _pushTransactionsAsPayments({
    required String userId,
    required String businessId,
  }) async {
    final rows = await _db.query(
      Tables.transactions,
      where:
          'business_id = ? AND invoice_id IS NOT NULL AND is_synced = 0 AND is_deleted = 0',
      whereArgs: [businessId],
      orderBy: 'updated_at ASC',
      limit: 200,
    );
    if (rows.isEmpty) return;

    final payloadRows = rows
        .map(
          (r) => {
            'id': (r['id'] ?? '').toString(),
            'invoice_id': (r['invoice_id'] ?? '').toString(),
            'amount': (r['amount'] ?? 0),
            'mode': (r['mode'] ?? 'cash').toString(),
            'reference': r['reference']?.toString(),
            'status': 'success',
            'paid_at': (r['date'] ?? '').toString(),
            'created_at': (r['created_at'] ?? '').toString(),
            'updated_at': (r['updated_at'] ?? '').toString(),
            'is_synced': 0,
          },
        )
        .toList();

    final res = await _api.postJson(
      '/api/v1/mobile/sync/push/',
      {'user_id': userId, 'table': 'payments', 'rows': payloadRows},
    );
    if (res['ok'] != true) throw Exception('Push failed: payments');

    final now = DateTime.now().toIso8601String();
    await _db.transaction((txn) async {
      for (final r in rows) {
        final id = (r['id'] ?? '').toString();
        if (id.isEmpty) continue;
        await _db.updateById(
            Tables.transactions, id, {'is_synced': 1, 'updated_at': now},
            txn: txn);
      }
    });
  }

  Future<void> _pullUpdates({
    required String userId,
    required String businessId,
  }) async {
    final since = lastSyncAt?.toIso8601String();
    final res = await _api.postJson(
      '/api/v1/mobile/sync/pull/',
      {'user_id': userId, 'since': since},
    );
    if (res['ok'] != true) throw Exception('Pull failed');
    final data = res['data'];
    if (data is! Map) return;

    await _db.transaction((txn) async {
      // customers -> parties (type=customer)
      final customers = data['customers'];
      if (customers is List) {
        for (final row in customers) {
          if (row is! Map) continue;
          final id = (row['id'] ?? '').toString();
          if (id.isEmpty) continue;
          await _upsertWithConflictCheck(
            txn: txn,
            table: Tables.parties,
            id: id,
            remoteUpdatedAt: row['updated_at']?.toString(),
            remoteRow: {
              'id': id,
              'business_id': businessId,
              'type': 'customer',
              'name': (row['name'] ?? '').toString(),
              'phone': row['phone']?.toString(),
              'address': row['address']?.toString(),
              'gstin': null,
              'opening_balance': 0,
              'created_at': (row['created_at'] ?? '').toString(),
              'updated_at': (row['updated_at'] ?? '').toString(),
              'is_synced': 1,
              'is_deleted': 0,
            },
          );
        }
      }

      // products
      final products = data['products'];
      if (products is List) {
        for (final row in products) {
          if (row is! Map) continue;
          final id = (row['id'] ?? '').toString();
          if (id.isEmpty) continue;
          await _upsertWithConflictCheck(
            txn: txn,
            table: Tables.products,
            id: id,
            remoteUpdatedAt: row['updated_at']?.toString(),
            remoteRow: {
              'id': id,
              'business_id': businessId,
              'name': (row['name'] ?? '').toString(),
              'sku': row['sku']?.toString(),
              'barcode': null,
              'category': null,
              'unit': null,
              'sale_price': row['price'] ?? 0,
              'purchase_price': 0,
              'tax_percent': row['tax_percent'] ?? 0,
              'stock_qty': 0,
              'created_at': (row['created_at'] ?? '').toString(),
              'updated_at': (row['updated_at'] ?? '').toString(),
              'is_synced': 1,
              'is_deleted': 0,
            },
          );
        }
      }

      // invoices
      final invoices = data['invoices'];
      if (invoices is List) {
        for (final row in invoices) {
          if (row is! Map) continue;
          final id = (row['id'] ?? '').toString();
          if (id.isEmpty) continue;
          final createdAt = (row['created_at'] ?? '').toString();
          await _upsertWithConflictCheck(
            txn: txn,
            table: Tables.invoices,
            id: id,
            remoteUpdatedAt: row['updated_at']?.toString(),
            remoteRow: {
              'id': id,
              'business_id': businessId,
              'party_id': (row['customer_id'] ?? '').toString(),
              'type': 'sale',
              'number': (row['number'] ?? '').toString(),
              'date': createdAt,
              'status': (row['status'] ?? 'unpaid').toString(),
              'subtotal': row['subtotal'] ?? 0,
              'discount': row['discount'] ?? 0,
              'tax': row['tax'] ?? 0,
              'total': row['total'] ?? 0,
              'paid': row['paid'] ?? 0,
              'balance': row['balance'] ?? 0,
              'notes': null,
              'created_at': createdAt,
              'updated_at': (row['updated_at'] ?? '').toString(),
              'is_synced': 1,
              'is_deleted': 0,
            },
          );
        }
      }

      // invoice_items
      final items = data['invoice_items'];
      if (items is List) {
        for (final row in items) {
          if (row is! Map) continue;
          final id = (row['id'] ?? '').toString();
          if (id.isEmpty) continue;
          await _upsertWithConflictCheck(
            txn: txn,
            table: Tables.invoiceItems,
            id: id,
            remoteUpdatedAt: row['updated_at']?.toString(),
            remoteRow: {
              'id': id,
              'invoice_id': (row['invoice_id'] ?? '').toString(),
              'product_id': (row['product_id'] ?? '').toString(),
              'name': (row['name'] ?? '').toString(),
              'qty': row['qty'] ?? 0,
              'unit_price': row['unit_price'] ?? 0,
              'discount': 0,
              'tax_percent': row['tax_percent'] ?? 0,
              'line_total': row['line_total'] ?? 0,
              'created_at': (row['created_at'] ?? '').toString(),
              'updated_at': (row['updated_at'] ?? '').toString(),
              'is_synced': 1,
              'is_deleted': 0,
            },
          );
        }
      }

      // payments -> transactions
      final payments = data['payments'];
      if (payments is List) {
        for (final row in payments) {
          if (row is! Map) continue;
          final id = (row['id'] ?? '').toString();
          if (id.isEmpty) continue;
          final paidAt = (row['paid_at'] ?? '').toString();
          await _upsertWithConflictCheck(
            txn: txn,
            table: Tables.transactions,
            id: id,
            remoteUpdatedAt: row['updated_at']?.toString(),
            remoteRow: {
              'id': id,
              'business_id': businessId,
              'party_id': null,
              'invoice_id': (row['invoice_id'] ?? '').toString(),
              'type': 'payment_in',
              'amount': row['amount'] ?? 0,
              'mode': (row['mode'] ?? 'cash').toString(),
              'reference': row['reference']?.toString(),
              'date': paidAt,
              'notes': null,
              'created_at': (row['created_at'] ?? '').toString(),
              'updated_at': (row['updated_at'] ?? '').toString(),
              'is_synced': 1,
              'is_deleted': 0,
            },
          );
        }
      }
    });
  }

  Future<void> _upsertWithConflictCheck({
    required Transaction txn,
    required String table,
    required String id,
    required String? remoteUpdatedAt,
    required Map<String, Object?> remoteRow,
  }) async {
    // If local row has pending changes and is newer, keep local (last-write-wins).
    final local =
        await txn.query(table, where: 'id = ?', whereArgs: [id], limit: 1);
    if (local.isNotEmpty) {
      final r = local.first;
      final localSynced = (r['is_synced'] ?? 0) == 1;
      final localUpdated =
          DateTime.tryParse((r['updated_at'] ?? '').toString());
      final remoteUpdated =
          DateTime.tryParse((remoteUpdatedAt ?? '').toString());
      if (!localSynced &&
          localUpdated != null &&
          remoteUpdated != null &&
          localUpdated.isAfter(remoteUpdated)) {
        return;
      }
    }
    await txn.insert(table, remoteRow,
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<bool> _isOnline() async {
    final results = await _connectivity.checkConnectivity();
    return results.any((r) => r != ConnectivityResult.none);
  }
}
