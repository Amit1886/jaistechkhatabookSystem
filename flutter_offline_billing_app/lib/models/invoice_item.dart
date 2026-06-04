class InvoiceItem {
  final String id;
  final String invoiceId;
  final String productId;
  final String name;
  final double qty;
  final double unitPrice;
  final double taxPercent;
  final double lineTotal;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;

  InvoiceItem({
    required this.id,
    required this.invoiceId,
    required this.productId,
    required this.name,
    required this.qty,
    required this.unitPrice,
    required this.taxPercent,
    required this.lineTotal,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'invoice_id': invoiceId,
        'product_id': productId,
        'name': name,
        'qty': qty,
        'unit_price': unitPrice,
        'tax_percent': taxPercent,
        'line_total': lineTotal,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'is_synced': isSynced ? 1 : 0,
      };

  static InvoiceItem fromMap(Map<String, Object?> map) => InvoiceItem(
        id: map['id'] as String,
        invoiceId: map['invoice_id'] as String,
        productId: map['product_id'] as String,
        name: map['name'] as String,
        qty: (map['qty'] as num).toDouble(),
        unitPrice: (map['unit_price'] as num).toDouble(),
        taxPercent: (map['tax_percent'] as num).toDouble(),
        lineTotal: (map['line_total'] as num).toDouble(),
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: DateTime.parse(map['updated_at'] as String),
        isSynced: (map['is_synced'] as int) == 1,
      );
}

