class Customer {
  final String id;
  final String userId;
  final String name;
  final String phone;
  final String address;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;

  Customer({
    required this.id,
    required this.userId,
    required this.name,
    required this.phone,
    required this.address,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'user_id': userId,
        'name': name,
        'phone': phone,
        'address': address,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'is_synced': isSynced ? 1 : 0,
      };

  static Customer fromMap(Map<String, Object?> map) => Customer(
        id: map['id'] as String,
        userId: map['user_id'] as String,
        name: map['name'] as String,
        phone: (map['phone'] as String?) ?? '',
        address: (map['address'] as String?) ?? '',
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: DateTime.parse(map['updated_at'] as String),
        isSynced: (map['is_synced'] as int) == 1,
      );
}

