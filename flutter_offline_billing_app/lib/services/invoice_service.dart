import '../database/local_db.dart';
import '../database/tables.dart';
import '../models/invoice_item_model.dart';
import '../models/invoice_model.dart';
import '../models/product_model.dart';
import '../models/transaction_model.dart';
import 'api_service.dart';
import 'id_service.dart';

class InvoiceDraftItem {
  InvoiceDraftItem({
    required this.product,
    required this.qty,
    double? unitPriceOverride,
  }) : unitPrice = unitPriceOverride ?? product.salePrice;

  final ProductModel product;
  final double qty;
  final double unitPrice;
}

class InvoiceService {
  InvoiceService(this._db, {ApiService? api}) : _api = api;

  final LocalDb _db;
  final ApiService? _api;

  Future<List<InvoiceModel>> list({required String businessId}) async {
    final api = _api;
    if (api != null) {
      try {
        final res = await api.getJson('/api/app/invoices/');
        final rows = (res['results'] as List? ?? const [])
            .whereType<Map>()
            .map((row) => InvoiceModel.fromJson(
                  Map<String, dynamic>.from(row),
                  businessId: businessId,
                ))
            .toList();
        for (final row in rows) {
          await _db.upsert(Tables.invoices, row.toMap());
        }
        return rows;
      } catch (_) {
        // Local cache remains the offline fallback.
      }
    }

    final rows = await _db.query(
      Tables.invoices,
      where: 'business_id = ? AND is_deleted = 0',
      whereArgs: [businessId],
      orderBy: 'date DESC',
      limit: 500,
    );
    return rows.map(InvoiceModel.fromMap).toList();
  }

  Future<InvoiceModel?> getById(String invoiceId) async {
    final rows = await _db.query(Tables.invoices,
        where: 'id = ?', whereArgs: [invoiceId], limit: 1);
    if (rows.isEmpty) return null;
    return InvoiceModel.fromMap(rows.first);
  }

  Future<List<InvoiceItemModel>> itemsForInvoice(String invoiceId) async {
    final rows = await _db.query(
      Tables.invoiceItems,
      where: 'invoice_id = ? AND is_deleted = 0',
      whereArgs: [invoiceId],
      orderBy: 'created_at ASC',
    );
    return rows.map(InvoiceItemModel.fromMap).toList();
  }

  Future<List<TransactionModel>> transactionsForInvoice(
      String invoiceId) async {
    final rows = await _db.query(
      Tables.transactions,
      where: 'invoice_id = ? AND is_deleted = 0',
      whereArgs: [invoiceId],
      orderBy: 'date DESC',
    );
    return rows.map(TransactionModel.fromMap).toList();
  }

  Future<InvoiceModel> createInvoice({
    required String businessId,
    required String partyId,
    required List<InvoiceDraftItem> items,
    String type = 'sale',
    double discount = 0,
    double paid = 0,
    String paymentMode = 'cash',
    String? notes,
  }) async {
    if (items.isEmpty) throw Exception('Add at least one item');
    if (discount < 0) throw Exception('Discount cannot be negative');
    if (paid < 0) throw Exception('Paid amount cannot be negative');

    final now = DateTime.now();
    final invoiceId = IdService.newId();
    final number = _buildInvoiceNumber(now);

    double subtotal = 0;
    double tax = 0;
    final itemModels = <InvoiceItemModel>[];

    for (final row in items) {
      if (row.qty <= 0) throw Exception('Quantity must be > 0');
      if (row.unitPrice < 0) throw Exception('Unit price must be >= 0');

      final lineBase = row.qty * row.unitPrice;
      final lineTax = lineBase * (row.product.taxPercent / 100.0);
      final lineTotal = lineBase + lineTax;
      subtotal += lineBase;
      tax += lineTax;

      itemModels.add(
        InvoiceItemModel(
          id: IdService.newId(),
          invoiceId: invoiceId,
          productId: row.product.id,
          name: row.product.name,
          qty: row.qty,
          unitPrice: row.unitPrice,
          discount: 0,
          taxPercent: row.product.taxPercent,
          lineTotal: lineTotal,
          createdAt: now,
          updatedAt: now,
          isSynced: false,
          isDeleted: false,
        ),
      );
    }

    final total = (subtotal - discount) + tax;
    final clampedPaid = paid.clamp(0.0, total).toDouble();
    final balance =
        (total - clampedPaid).clamp(0.0, double.infinity).toDouble();
    final status = balance <= 0 ? 'paid' : 'unpaid';

    final invoice = InvoiceModel(
      id: invoiceId,
      businessId: businessId,
      partyId: partyId,
      type: type,
      number: number,
      date: now,
      status: status,
      subtotal: subtotal,
      discount: discount,
      tax: tax,
      total: total,
      paid: clampedPaid,
      balance: balance,
      notes: notes?.trim().isEmpty ?? true ? null : notes?.trim(),
      createdAt: now,
      updatedAt: now,
      isSynced: false,
      isDeleted: false,
    );

    final api = _api;
    if (api != null) {
      try {
        final res = await api.postJson('/api/app/invoices/', {
          'party_id': partyId,
          'type': type,
          'discount': discount,
          'paid': paid,
          'payment_mode': paymentMode,
          'notes': notes,
          'items': items
              .map((row) => {
                    'product_id': row.product.id,
                    'name': row.product.name,
                    'qty': row.qty,
                    'unit_price': row.unitPrice,
                    'tax_percent': row.product.taxPercent,
                  })
              .toList(),
        });
        final saved = InvoiceModel.fromJson(res, businessId: businessId);
        await _db.upsert(Tables.invoices, saved.toMap());
        return saved;
      } catch (_) {
        // Keep offline invoice creation when API is unavailable.
      }
    }

    await _db.transaction((txn) async {
      await txn.insert(Tables.invoices, invoice.toMap());
      for (final it in itemModels) {
        await txn.insert(Tables.invoiceItems, it.toMap());
      }
      if (clampedPaid > 0) {
        final t = TransactionModel(
          id: IdService.newId(),
          businessId: businessId,
          partyId: partyId,
          invoiceId: invoiceId,
          type: 'payment_in',
          amount: clampedPaid,
          mode: paymentMode,
          reference: null,
          date: now,
          notes: 'Initial payment',
          createdAt: now,
          updatedAt: now,
          isSynced: false,
          isDeleted: false,
        );
        await txn.insert(Tables.transactions, t.toMap());
      }
    });

    return invoice;
  }

  Future<void> addPayment({
    required String invoiceId,
    required String businessId,
    required String partyId,
    required double amount,
    String mode = 'cash',
    String? reference,
  }) async {
    if (amount <= 0) throw Exception('Payment amount must be > 0');

    final now = DateTime.now();
    final invoice = await getById(invoiceId);
    if (invoice == null) throw Exception('Invoice not found');

    final newPaid = invoice.paid + amount;
    final newBalance =
        (invoice.total - newPaid).clamp(0.0, double.infinity).toDouble();
    final status = newBalance <= 0 ? 'paid' : 'unpaid';

    await _db.transaction((txn) async {
      final t = TransactionModel(
        id: IdService.newId(),
        businessId: businessId,
        partyId: partyId,
        invoiceId: invoiceId,
        type: 'payment_in',
        amount: amount,
        mode: mode,
        reference: reference?.trim().isEmpty ?? true ? null : reference?.trim(),
        date: now,
        notes: null,
        createdAt: now,
        updatedAt: now,
        isSynced: false,
        isDeleted: false,
      );
      await txn.insert(Tables.transactions, t.toMap());

      await txn.update(
        Tables.invoices,
        {
          'paid': newPaid,
          'balance': newBalance,
          'status': status,
          'updated_at': now.toIso8601String(),
          'is_synced': 0,
        },
        where: 'id = ?',
        whereArgs: [invoiceId],
      );
    });
  }

  Future<void> softDeleteInvoice(String invoiceId) async {
    await _db.softDeleteById(Tables.invoices, invoiceId);
  }

  static String _buildInvoiceNumber(DateTime now) {
    final y = now.year.toString().padLeft(4, '0');
    final m = now.month.toString().padLeft(2, '0');
    final d = now.day.toString().padLeft(2, '0');
    final t = now.millisecondsSinceEpoch.toString().substring(7);
    return 'INV-$y$m$d-$t';
  }
}
