class InvoiceModel {
  const InvoiceModel({
    required this.id,
    required this.businessId,
    required this.partyId,
    required this.type,
    required this.number,
    required this.date,
    required this.status,
    required this.subtotal,
    required this.discount,
    required this.tax,
    required this.total,
    required this.paid,
    required this.balance,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
    required this.isDeleted,
  });

  final String id;
  final String businessId;
  final String partyId;
  final String type; // sale | purchase
  final String number;
  final DateTime date;
  final String status; // draft | unpaid | paid | cancelled
  final double subtotal;
  final double discount;
  final double tax;
  final double total;
  final double paid;
  final double balance;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;
  final bool isDeleted;

  factory InvoiceModel.fromMap(Map<String, Object?> map) {
    return InvoiceModel(
      id: (map['id'] ?? '').toString(),
      businessId: (map['business_id'] ?? '').toString(),
      partyId: (map['party_id'] ?? '').toString(),
      type: (map['type'] ?? 'sale').toString(),
      number: (map['number'] ?? '').toString(),
      date: DateTime.parse((map['date'] ?? '').toString()),
      status: (map['status'] ?? 'unpaid').toString(),
      subtotal: (map['subtotal'] as num?)?.toDouble() ?? 0,
      discount: (map['discount'] as num?)?.toDouble() ?? 0,
      tax: (map['tax'] as num?)?.toDouble() ?? 0,
      total: (map['total'] as num?)?.toDouble() ?? 0,
      paid: (map['paid'] as num?)?.toDouble() ?? 0,
      balance: (map['balance'] as num?)?.toDouble() ?? 0,
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
      'type': type,
      'number': number,
      'date': date.toIso8601String(),
      'status': status,
      'subtotal': subtotal,
      'discount': discount,
      'tax': tax,
      'total': total,
      'paid': paid,
      'balance': balance,
      'notes': notes,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      'is_synced': isSynced ? 1 : 0,
      'is_deleted': isDeleted ? 1 : 0,
    };
  }

  factory InvoiceModel.fromJson(Map<String, dynamic> json, {required String businessId}) {
    return InvoiceModel(
      id: (json['id'] ?? '').toString(),
      businessId: businessId,
      partyId: (json['party_id'] ?? json['customer_id'] ?? '').toString(),
      type: (json['type'] ?? 'sale').toString(),
      number: (json['number'] ?? '').toString(),
      date: DateTime.tryParse((json['date'] ?? json['created_at'] ?? '').toString()) ?? DateTime.now(),
      status: (json['status'] ?? 'unpaid').toString(),
      subtotal: (json['subtotal'] as num?)?.toDouble() ?? 0,
      discount: (json['discount'] as num?)?.toDouble() ?? 0,
      tax: (json['tax'] as num?)?.toDouble() ?? 0,
      total: (json['total'] as num?)?.toDouble() ?? 0,
      paid: (json['paid'] as num?)?.toDouble() ?? 0,
      balance: (json['balance'] as num?)?.toDouble() ?? 0,
      notes: json['notes']?.toString(),
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ?? DateTime.now(),
      updatedAt: DateTime.tryParse((json['updated_at'] ?? '').toString()) ?? DateTime.now(),
      isSynced: true,
      isDeleted: false,
    );
  }

  InvoiceModel copyWith({
    String? id,
    String? businessId,
    String? partyId,
    String? type,
    String? number,
    DateTime? date,
    String? status,
    double? subtotal,
    double? discount,
    double? tax,
    double? total,
    double? paid,
    double? balance,
    String? notes,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool? isSynced,
    bool? isDeleted,
  }) {
    return InvoiceModel(
      id: id ?? this.id,
      businessId: businessId ?? this.businessId,
      partyId: partyId ?? this.partyId,
      type: type ?? this.type,
      number: number ?? this.number,
      date: date ?? this.date,
      status: status ?? this.status,
      subtotal: subtotal ?? this.subtotal,
      discount: discount ?? this.discount,
      tax: tax ?? this.tax,
      total: total ?? this.total,
      paid: paid ?? this.paid,
      balance: balance ?? this.balance,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      isSynced: isSynced ?? this.isSynced,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }
}

