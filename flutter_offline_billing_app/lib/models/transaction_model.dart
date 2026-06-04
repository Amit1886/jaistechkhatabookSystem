class TransactionModel {
  const TransactionModel({
    required this.id,
    required this.businessId,
    this.partyId,
    this.invoiceId,
    required this.type,
    required this.amount,
    required this.mode,
    this.reference,
    required this.date,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
    required this.isDeleted,
  });

  final String id;
  final String businessId;
  final String? partyId;
  final String? invoiceId;
  final String type; // payment_in | payment_out | adjustment
  final double amount;
  final String mode; // cash | upi | bank | card | other
  final String? reference;
  final DateTime date;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;
  final bool isDeleted;

  factory TransactionModel.fromMap(Map<String, Object?> map) {
    return TransactionModel(
      id: (map['id'] ?? '').toString(),
      businessId: (map['business_id'] ?? '').toString(),
      partyId: map['party_id']?.toString(),
      invoiceId: map['invoice_id']?.toString(),
      type: (map['type'] ?? 'payment_in').toString(),
      amount: (map['amount'] as num?)?.toDouble() ?? 0,
      mode: (map['mode'] ?? 'cash').toString(),
      reference: map['reference']?.toString(),
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
      'party_id': partyId,
      'invoice_id': invoiceId,
      'type': type,
      'amount': amount,
      'mode': mode,
      'reference': reference,
      'date': date.toIso8601String(),
      'notes': notes,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'is_synced': isSynced ? 1 : 0,
      'is_deleted': isDeleted ? 1 : 0,
    };
  }

  factory TransactionModel.fromJson(Map<String, dynamic> json, {required String businessId}) {
    return TransactionModel(
      id: (json['id'] ?? '').toString(),
      businessId: businessId,
      partyId: json['party_id']?.toString(),
      invoiceId: json['invoice_id']?.toString(),
      type: (json['type'] ?? 'payment_in').toString(),
      amount: (json['amount'] as num?)?.toDouble() ?? 0,
      mode: (json['mode'] ?? 'cash').toString(),
      reference: json['reference']?.toString(),
      date: DateTime.tryParse((json['date'] ?? json['paid_at'] ?? '').toString()) ?? DateTime.now(),
      notes: json['notes']?.toString(),
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ?? DateTime.now(),
      updatedAt: DateTime.tryParse((json['updated_at'] ?? '').toString()) ?? DateTime.now(),
      isSynced: true,
      isDeleted: false,
    );
  }

  TransactionModel copyWith({
    String? id,
    String? businessId,
    String? partyId,
    String? invoiceId,
    String? type,
    double? amount,
    String? mode,
    String? reference,
    DateTime? date,
    String? notes,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool? isSynced,
    bool? isDeleted,
  }) {
    return TransactionModel(
      id: id ?? this.id,
      businessId: businessId ?? this.businessId,
      partyId: partyId ?? this.partyId,
      invoiceId: invoiceId ?? this.invoiceId,
      type: type ?? this.type,
      amount: amount ?? this.amount,
      mode: mode ?? this.mode,
      reference: reference ?? this.reference,
      date: date ?? this.date,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isSynced: isSynced ?? this.isSynced,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }
}

