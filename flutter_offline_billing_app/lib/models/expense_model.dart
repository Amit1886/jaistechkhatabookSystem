class ExpenseModel {
  const ExpenseModel({
    required this.id,
    required this.businessId,
    this.category,
    required this.amount,
    required this.date,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
    required this.isDeleted,
  });

  final String id;
  final String businessId;
  final String? category;
  final double amount;
  final DateTime date;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;
  final bool isDeleted;

  factory ExpenseModel.fromMap(Map<String, Object?> map) {
    return ExpenseModel(
      id: (map['id'] ?? '').toString(),
      businessId: (map['business_id'] ?? '').toString(),
      category: map['category']?.toString(),
      amount: (map['amount'] as num?)?.toDouble() ?? 0,
      date: DateTime.parse((map['date'] ?? '').toString()),
      notes: map['notes']?.toString(),
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
      'category': category,
      'amount': amount,
      'date': date.toIso8601String(),
      'notes': notes,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'is_synced': isSynced ? 1 : 0,
      'is_deleted': isDeleted ? 1 : 0,
    };
  }

  ExpenseModel copyWith({
    String? id,
    String? businessId,
    String? category,
    double? amount,
    DateTime? date,
    String? notes,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool? isSynced,
    bool? isDeleted,
  }) {
    return ExpenseModel(
      id: id ?? this.id,
      businessId: businessId ?? this.businessId,
      category: category ?? this.category,
      amount: amount ?? this.amount,
      date: date ?? this.date,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isSynced: isSynced ?? this.isSynced,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }
}

