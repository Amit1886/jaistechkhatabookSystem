class Product {
  final String id;
  final String userId;
  final String name;
  final String sku;
  final double price;
  final double taxPercent;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;

  Product({
    required this.id,
    required this.userId,
    required this.name,
    required this.sku,
    required this.price,
    required this.taxPercent,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'user_id': userId,
        'name': name,
        'sku': sku,
        'price': price,
        'tax_percent': taxPercent,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'is_synced': isSynced ? 1 : 0,
      };

  static Product fromMap(Map<String, Object?> map) => Product(
        id: map['id'] as String,
        userId: map['user_id'] as String,
        name: map['name'] as String,
        sku: (map['sku'] as String?) ?? '',
        price: (map['price'] as num).toDouble(),
        taxPercent: (map['tax_percent'] as num).toDouble(),
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: DateTime.parse(map['updated_at'] as String),
        isSynced: (map['is_synced'] as int) == 1,
      );
}

