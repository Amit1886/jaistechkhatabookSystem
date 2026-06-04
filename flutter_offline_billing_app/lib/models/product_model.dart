class ProductModel {
  const ProductModel({
    required this.id,
    required this.businessId,
    required this.name,
    this.sku,
    this.barcode,
    this.category,
    this.unit,
    required this.salePrice,
    required this.purchasePrice,
    required this.taxPercent,
    required this.stockQty,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
    required this.isDeleted,
  });

  final String id;
  final String businessId;
  final String name;
  final String? sku;
  final String? barcode;
  final String? category;
  final String? unit;
  final double salePrice;
  final double purchasePrice;
  final double taxPercent;
  final double stockQty;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;
  final bool isDeleted;

  factory ProductModel.fromMap(Map<String, Object?> map) {
    return ProductModel(
      id: (map['id'] ?? '').toString(),
      businessId: (map['business_id'] ?? '').toString(),
      name: (map['name'] ?? '').toString(),
      sku: map['sku']?.toString(),
      barcode: map['barcode']?.toString(),
      category: map['category']?.toString(),
      unit: map['unit']?.toString(),
      salePrice: (map['sale_price'] as num?)?.toDouble() ?? 0,
      purchasePrice: (map['purchase_price'] as num?)?.toDouble() ?? 0,
      taxPercent: (map['tax_percent'] as num?)?.toDouble() ?? 0,
      stockQty: (map['stock_qty'] as num?)?.toDouble() ?? 0,
      createdAt: DateTime.parse((map['created_at'] ?? '').toString()),
      updatedAt: DateTime.parse((map['updated_at'] ?? '').toString()),
      isSynced: (map['is_synced'] ?? 0) == 1,
      isDeleted: (map['is_deleted'] ?? 0) == 1,
    );
  }

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'business_id': businessId,
      'name': name,
      'sku': sku,
      'barcode': barcode,
      'category': category,
      'unit': unit,
      'sale_price': salePrice,
      'purchase_price': purchasePrice,
      'tax_percent': taxPercent,
      'stock_qty': stockQty,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'is_synced': isSynced ? 1 : 0,
      'is_deleted': isDeleted ? 1 : 0,
    };
  }

  factory ProductModel.fromJson(Map<String, dynamic> json, {required String businessId}) {
    return ProductModel(
      id: (json['id'] ?? '').toString(),
      businessId: businessId,
      name: (json['name'] ?? '').toString(),
      sku: json['sku']?.toString(),
      barcode: json['barcode']?.toString(),
      category: json['category']?.toString(),
      unit: json['unit']?.toString(),
      salePrice: (json['sale_price'] as num?)?.toDouble() ?? (json['price'] as num?)?.toDouble() ?? 0,
      purchasePrice: (json['purchase_price'] as num?)?.toDouble() ?? 0,
      taxPercent: (json['tax_percent'] as num?)?.toDouble() ?? 0,
      stockQty: (json['stock_qty'] as num?)?.toDouble() ?? 0,
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ?? DateTime.now(),
      updatedAt: DateTime.tryParse((json['updated_at'] ?? '').toString()) ?? DateTime.now(),
      isSynced: true,
      isDeleted: false,
    );
  }

  ProductModel copyWith({
    String? id,
    String? businessId,
    String? name,
    String? sku,
    String? barcode,
    String? category,
    String? unit,
    double? salePrice,
    double? purchasePrice,
    double? taxPercent,
    double? stockQty,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool? isSynced,
    bool? isDeleted,
  }) {
    return ProductModel(
      id: id ?? this.id,
      businessId: businessId ?? this.businessId,
      name: name ?? this.name,
      sku: sku ?? this.sku,
      barcode: barcode ?? this.barcode,
      category: category ?? this.category,
      unit: unit ?? this.unit,
      salePrice: salePrice ?? this.salePrice,
      purchasePrice: purchasePrice ?? this.purchasePrice,
      taxPercent: taxPercent ?? this.taxPercent,
      stockQty: stockQty ?? this.stockQty,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isSynced: isSynced ?? this.isSynced,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }
}

