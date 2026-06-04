class PartyModel {
  const PartyModel({
    required this.id,
    required this.businessId,
    required this.type,
    required this.name,
    this.phone,
    this.address,
    this.gstin,
    required this.openingBalance,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
    required this.isDeleted,
  });

  final String id;
  final String businessId;
  final String type; // customer | supplier
  final String name;
  final String? phone;
  final String? address;
  final String? gstin;
  final double openingBalance;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;
  final bool isDeleted;

  factory PartyModel.fromMap(Map<String, Object?> map) {
    return PartyModel(
      id: (map['id'] ?? '').toString(),
      businessId: (map['business_id'] ?? '').toString(),
      type: (map['type'] ?? 'customer').toString(),
      name: (map['name'] ?? '').toString(),
      phone: map['phone']?.toString(),
      address: map['address']?.toString(),
      gstin: map['gstin']?.toString(),
      openingBalance: (map['opening_balance'] as num?)?.toDouble() ?? 0,
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
      'type': type,
      'name': name,
      'phone': phone,
      'address': address,
      'gstin': gstin,
      'opening_balance': openingBalance,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'is_synced': isSynced ? 1 : 0,
      'is_deleted': isDeleted ? 1 : 0,
    };
  }

  factory PartyModel.fromJson(Map<String, dynamic> json, {required String businessId, required String type}) {
    return PartyModel(
      id: (json['id'] ?? '').toString(),
      businessId: businessId,
      type: type,
      name: (json['name'] ?? '').toString(),
      phone: json['phone']?.toString(),
      address: json['address']?.toString(),
      gstin: json['gstin']?.toString(),
      openingBalance: (json['opening_balance'] as num?)?.toDouble() ?? 0,
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ?? DateTime.now(),
      updatedAt: DateTime.tryParse((json['updated_at'] ?? '').toString()) ?? DateTime.now(),
      isSynced: true,
      isDeleted: false,
    );
  }

  PartyModel copyWith({
    String? id,
    String? businessId,
    String? type,
    String? name,
    String? phone,
    String? address,
    String? gstin,
    double? openingBalance,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool? isSynced,
    bool? isDeleted,
  }) {
    return PartyModel(
      id: id ?? this.id,
      businessId: businessId ?? this.businessId,
      type: type ?? this.type,
      name: name ?? this.name,
      phone: phone ?? this.phone,
      address: address ?? this.address,
      gstin: gstin ?? this.gstin,
      openingBalance: openingBalance ?? this.openingBalance,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isSynced: isSynced ?? this.isSynced,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }
}

