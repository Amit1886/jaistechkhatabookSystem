class InvoiceItemModel {
  const InvoiceItemModel({
    required this.id,
    required this.invoiceId,
    this.productId,
    required this.name,
    required this.qty,
    required this.unitPrice,
    required this.discount,
    required this.taxPercent,
    required this.lineTotal,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
    required this.isDeleted,
  });

  final String id;
  final String invoiceId;
  final String? productId;
  final String name;
  final double qty;
  final double unitPrice;
  final double discount;
  final double taxPercent;
  final double lineTotal;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;
  final bool isDeleted;

  factory InvoiceItemModel.fromMap(Map<String, Object?> map) {
    return InvoiceItemModel(
      id: (map['id'] ?? '').toString(),
      invoiceId: (map['invoice_id'] ?? '').toString(),
      productId: map['product_id']?.toString(),
      name: (map['name'] ?? '').toString(),
      qty: (map['qty'] as num?)?.toDouble() ?? 0,
      unitPrice: (map['unit_price'] as num?)?.toDouble() ?? 0,
      discount: (map['discount'] as num?)?.toDouble() ?? 0,
      taxPercent: (map['tax_percent'] as num?)?.toDouble() ?? 0,
      lineTotal: (map['line_total'] as num?)?.toDouble() ?? 0,
      createdAt: DateTime.parse((map['created_at'] ?? '').toString()),
      updatedAt: DateTime.parse((map['updated_at'] ?? '').toString()),
      isSynced: (map['is_synced'] ?? 0) == 1,
      isDeleted: (map['is_deleted'] ?? 0) == 1,
    );
  }

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'invoice_id': invoiceId,
      'product_id': productId,
      'name': name,
      'qty': qty,
      'unit_price': unitPrice,
      'discount': discount,
      'tax_percent': taxPercent,
      'line_total': lineTotal,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'is_synced': isSynced ? 1 : 0,
      'is_deleted': isDeleted ? 1 : 0,
    };
  }

  InvoiceItemModel copyWith({
    String? id,
    String? invoiceId,
    String? productId,
    String? name,
    double? qty,
    double? unitPrice,
    double? discount,
    double? taxPercent,
    double? lineTotal,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool? isSynced,
    bool? isDeleted,
  }) {
    return InvoiceItemModel(
      id: id ?? this.id,
      invoiceId: invoiceId ?? this.invoiceId,
      productId: productId ?? this.productId,
      name: name ?? this.name,
      qty: qty ?? this.qty,
      unitPrice: unitPrice ?? this.unitPrice,
      discount: discount ?? this.discount,
      taxPercent: taxPercent ?? this.taxPercent,
      lineTotal: lineTotal ?? this.lineTotal,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isSynced: isSynced ?? this.isSynced,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }
}

