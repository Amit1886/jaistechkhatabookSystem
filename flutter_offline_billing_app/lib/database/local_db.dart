import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import 'tables.dart';

/// Local offline database (SQFlite).
///
/// Design goals:
/// - App works fully offline.
/// - All write operations are saved locally first.
/// - Each row includes `created_at`, `updated_at`, `is_synced` (and soft delete flag)
///   to support sync.
class LocalDb {
  LocalDb._();

  static final LocalDb instance = LocalDb._();

  static const _dbName = 'jaistech_billing.db';
  static const _dbVersion = 2;

  Database? _db;
  final Map<String, List<Map<String, Object?>>> _memoryTables = {
    Tables.users: <Map<String, Object?>>[],
    Tables.businesses: <Map<String, Object?>>[],
    Tables.parties: <Map<String, Object?>>[],
    Tables.products: <Map<String, Object?>>[],
    Tables.invoices: <Map<String, Object?>>[],
    Tables.invoiceItems: <Map<String, Object?>>[],
    Tables.transactions: <Map<String, Object?>>[],
    Tables.expenses: <Map<String, Object?>>[],
    Tables.syncState: <Map<String, Object?>>[],
  };

  Future<Database> get database async {
    final existing = _db;
    if (existing != null) return existing;
    _db = await _open();
    return _db!;
  }

  Future<Database> _open() async {
    final dir = await getApplicationDocumentsDirectory();
    final path = p.join(dir.path, _dbName);

    return openDatabase(
      path,
      version: _dbVersion,
      onConfigure: (db) async {
        await db.execute('PRAGMA foreign_keys = ON');
      },
      onCreate: (db, version) async {
        await _createTables(db);
      },
      onUpgrade: (db, oldVersion, newVersion) async {
        // Add schema migrations here when bumping `_dbVersion`.
        if (oldVersion < 2) {
          // Offline auth support (local password hash).
          try {
            await db.execute('ALTER TABLE ${Tables.users} ADD COLUMN password_salt TEXT;');
          } catch (_) {}
          try {
            await db.execute('ALTER TABLE ${Tables.users} ADD COLUMN password_hash TEXT;');
          } catch (_) {}
        }
      },
    );
  }

  Future<void> _createTables(Database db) async {
    // Users (cached profile; auth tokens are stored in secure storage).
    await db.execute('''
CREATE TABLE ${Tables.users} (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  password_salt TEXT,
  password_hash TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 1,
  is_deleted INTEGER NOT NULL DEFAULT 0
);
''');

    // Multi-business support.
    await db.execute('''
CREATE TABLE ${Tables.businesses} (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  address TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES ${Tables.users}(id) ON DELETE CASCADE
);
''');
    await db.execute('CREATE INDEX idx_businesses_user ON ${Tables.businesses}(user_id);');

    // Parties (customers + suppliers).
    await db.execute('''
CREATE TABLE ${Tables.parties} (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL,
  type TEXT NOT NULL, /* customer | supplier */
  name TEXT NOT NULL,
  phone TEXT,
  address TEXT,
  gstin TEXT,
  opening_balance REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (business_id) REFERENCES ${Tables.businesses}(id) ON DELETE CASCADE
);
''');
    await db.execute('CREATE INDEX idx_parties_business ON ${Tables.parties}(business_id);');
    await db.execute('CREATE INDEX idx_parties_type ON ${Tables.parties}(type);');

    // Products / Inventory.
    await db.execute('''
CREATE TABLE ${Tables.products} (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL,
  name TEXT NOT NULL,
  sku TEXT,
  barcode TEXT,
  category TEXT,
  unit TEXT,
  sale_price REAL NOT NULL DEFAULT 0,
  purchase_price REAL NOT NULL DEFAULT 0,
  tax_percent REAL NOT NULL DEFAULT 0,
  stock_qty REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (business_id) REFERENCES ${Tables.businesses}(id) ON DELETE CASCADE
);
''');
    await db.execute('CREATE INDEX idx_products_business ON ${Tables.products}(business_id);');
    await db.execute('CREATE INDEX idx_products_barcode ON ${Tables.products}(barcode);');

    // Invoices (sales/purchase).
    await db.execute('''
CREATE TABLE ${Tables.invoices} (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL,
  party_id TEXT NOT NULL,
  type TEXT NOT NULL, /* sale | purchase */
  number TEXT NOT NULL,
  date TEXT NOT NULL,
  status TEXT NOT NULL,
  subtotal REAL NOT NULL,
  discount REAL NOT NULL,
  tax REAL NOT NULL,
  total REAL NOT NULL,
  paid REAL NOT NULL,
  balance REAL NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (business_id) REFERENCES ${Tables.businesses}(id) ON DELETE CASCADE,
  FOREIGN KEY (party_id) REFERENCES ${Tables.parties}(id) ON DELETE RESTRICT
);
''');
    await db.execute('CREATE INDEX idx_invoices_business ON ${Tables.invoices}(business_id);');
    await db.execute('CREATE INDEX idx_invoices_party ON ${Tables.invoices}(party_id);');
    await db.execute('CREATE INDEX idx_invoices_date ON ${Tables.invoices}(date);');

    // Invoice Items.
    await db.execute('''
CREATE TABLE ${Tables.invoiceItems} (
  id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL,
  product_id TEXT,
  name TEXT NOT NULL,
  qty REAL NOT NULL,
  unit_price REAL NOT NULL,
  discount REAL NOT NULL DEFAULT 0,
  tax_percent REAL NOT NULL DEFAULT 0,
  line_total REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (invoice_id) REFERENCES ${Tables.invoices}(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES ${Tables.products}(id) ON DELETE RESTRICT
);
''');
    await db.execute('CREATE INDEX idx_items_invoice ON ${Tables.invoiceItems}(invoice_id);');

    // Transactions (payments in/out, adjustments).
    await db.execute('''
CREATE TABLE ${Tables.transactions} (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL,
  party_id TEXT,
  invoice_id TEXT,
  type TEXT NOT NULL, /* payment_in | payment_out | adjustment */
  amount REAL NOT NULL,
  mode TEXT NOT NULL, /* cash | upi | bank | card | other */
  reference TEXT,
  date TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (business_id) REFERENCES ${Tables.businesses}(id) ON DELETE CASCADE,
  FOREIGN KEY (party_id) REFERENCES ${Tables.parties}(id) ON DELETE SET NULL,
  FOREIGN KEY (invoice_id) REFERENCES ${Tables.invoices}(id) ON DELETE SET NULL
);
''');
    await db.execute('CREATE INDEX idx_txn_business ON ${Tables.transactions}(business_id);');
    await db.execute('CREATE INDEX idx_txn_party ON ${Tables.transactions}(party_id);');
    await db.execute('CREATE INDEX idx_txn_date ON ${Tables.transactions}(date);');

    // Expenses.
    await db.execute('''
CREATE TABLE ${Tables.expenses} (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL,
  category TEXT,
  amount REAL NOT NULL,
  date TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  is_synced INTEGER NOT NULL DEFAULT 0,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (business_id) REFERENCES ${Tables.businesses}(id) ON DELETE CASCADE
);
''');
    await db.execute('CREATE INDEX idx_expenses_business ON ${Tables.expenses}(business_id);');
    await db.execute('CREATE INDEX idx_expenses_date ON ${Tables.expenses}(date);');

    // Sync state key-value store.
    await db.execute('''
CREATE TABLE ${Tables.syncState} (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
''');
  }

  Future<int> upsert(String table, Map<String, Object?> row, {Transaction? txn}) async {
    if (kIsWeb) return _memoryUpsert(table, row);
    final db = txn ?? await database;
    return db.insert(table, row, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<int> updateById(String table, String id, Map<String, Object?> values, {Transaction? txn}) async {
    if (kIsWeb) return _memoryUpdateById(table, id, values);
    final db = txn ?? await database;
    return db.update(table, values, where: 'id = ?', whereArgs: [id]);
  }

  Future<int> hardDeleteById(String table, String id, {Transaction? txn}) async {
    if (kIsWeb) return _memoryHardDeleteById(table, id);
    final db = txn ?? await database;
    return db.delete(table, where: 'id = ?', whereArgs: [id]);
  }

  Future<int> softDeleteById(String table, String id, {Transaction? txn}) async {
    final now = DateTime.now().toIso8601String();
    return updateById(
      table,
      id,
      {
        'is_deleted': 1,
        'is_synced': 0,
        'updated_at': now,
      },
      txn: txn,
    );
  }

  Future<List<Map<String, Object?>>> query(
    String table, {
    String? where,
    List<Object?>? whereArgs,
    String? orderBy,
    int? limit,
  }) async {
    if (kIsWeb) return _memoryQuery(table, where: where, whereArgs: whereArgs, orderBy: orderBy, limit: limit);
    final db = await database;
    return db.query(table, where: where, whereArgs: whereArgs, orderBy: orderBy, limit: limit);
  }

  Future<List<Map<String, Object?>>> rawQuery(String sql, [List<Object?>? args]) async {
    if (kIsWeb) return const <Map<String, Object?>>[];
    final db = await database;
    return db.rawQuery(sql, args);
  }

  Future<T> transaction<T>(Future<T> Function(Transaction txn) action) async {
    if (kIsWeb) {
      throw UnsupportedError('SQLite transactions are not available in Flutter Web preview mode.');
    }
    final db = await database;
    return db.transaction(action);
  }

  Future<void> close() async {
    final db = _db;
    _db = null;
    if (db == null) return;
    await db.close();
  }

  int _memoryUpsert(String table, Map<String, Object?> row) {
    final rows = _memoryTables.putIfAbsent(table, () => <Map<String, Object?>>[]);
    final id = row['id']?.toString();
    if (id != null && id.isNotEmpty) {
      final index = rows.indexWhere((item) => item['id']?.toString() == id);
      if (index >= 0) {
        rows[index] = Map<String, Object?>.from(row);
        return 1;
      }
    }
    rows.add(Map<String, Object?>.from(row));
    return 1;
  }

  int _memoryUpdateById(String table, String id, Map<String, Object?> values) {
    final rows = _memoryTables.putIfAbsent(table, () => <Map<String, Object?>>[]);
    final index = rows.indexWhere((item) => item['id']?.toString() == id);
    if (index < 0) return 0;
    rows[index] = {...rows[index], ...values};
    return 1;
  }

  int _memoryHardDeleteById(String table, String id) {
    final rows = _memoryTables.putIfAbsent(table, () => <Map<String, Object?>>[]);
    final before = rows.length;
    rows.removeWhere((item) => item['id']?.toString() == id);
    return before - rows.length;
  }

  List<Map<String, Object?>> _memoryQuery(
    String table, {
    String? where,
    List<Object?>? whereArgs,
    String? orderBy,
    int? limit,
  }) {
    final rows = List<Map<String, Object?>>.from(_memoryTables[table] ?? const []);
    final filtered = where == null || where.trim().isEmpty
        ? rows
        : rows.where((row) => _matchesWhere(row, where, whereArgs ?? const [])).toList();

    if (orderBy != null && orderBy.trim().isNotEmpty) {
      final parts = orderBy.trim().split(RegExp(r'\s+'));
      final field = parts.first;
      final descending = parts.any((part) => part.toUpperCase() == 'DESC');
      filtered.sort((a, b) {
        final av = a[field]?.toString() ?? '';
        final bv = b[field]?.toString() ?? '';
        return descending ? bv.compareTo(av) : av.compareTo(bv);
      });
    }

    final sliced = limit == null ? filtered : filtered.take(limit).toList();
    return sliced.map((row) => Map<String, Object?>.from(row)).toList();
  }

  bool _matchesWhere(Map<String, Object?> row, String where, List<Object?> args) {
    var argIndex = 0;
    final clauses = where.split(RegExp(r'\s+AND\s+', caseSensitive: false));
    for (final rawClause in clauses) {
      final clause = rawClause.trim();
      if (clause.endsWith('IS NOT NULL')) {
        final field = clause.replaceAll('IS NOT NULL', '').trim();
        if (row[field] == null) return false;
        continue;
      }
      if (clause.endsWith('IS NULL')) {
        final field = clause.replaceAll('IS NULL', '').trim();
        if (row[field] != null) return false;
        continue;
      }
      if (clause.contains('LIKE ?')) {
        final field = clause.split('LIKE').first.trim();
        final pattern = (args.length > argIndex ? args[argIndex++] : '').toString().replaceAll('%', '').toLowerCase();
        if (!(row[field]?.toString().toLowerCase().contains(pattern) ?? false)) return false;
        continue;
      }
      if (clause.contains('= ?')) {
        final field = clause.split('=').first.trim();
        final expected = args.length > argIndex ? args[argIndex++] : null;
        if (row[field]?.toString() != expected?.toString()) return false;
      }
    }
    return true;
  }
}
