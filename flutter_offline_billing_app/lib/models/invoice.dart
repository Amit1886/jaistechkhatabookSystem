class Invoice {
  final String id;
  final String userId;
  final String customerId;
  final String number;
  final String status; // paid/unpaid/pending/hold
  final double subtotal;
  final double discount;
  final double tax;
  final double total;
  final double paid;
  final double balance;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;

  Invoice({
    required this.id,
    required this.userId,
    required this.customerId,
    required this.number,
    required this.status,
    required this.subtotal,
    required this.discount,
    required this.tax,
    required this.total,
    required this.paid,
    required this.balance,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'user_id': userId,
        'customer_id': customerId,
        'number': number,
        'status': status,
        'subtotal': subtotal,
        'discount': discount,
        'tax': tax,
        'total': total,
        'paid': paid,
        'balance': balance,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'is_synced': isSynced ? 1 : 0,
      };

  static Invoice fromMap(Map<String, Object?> map) => Invoice(
        id: map['id'] as String,
        userId: map['user_id'] as String,
        customerId: map['customer_id'] as String,
        number: map['number'] as String,
        status: map['status'] as String,
        subtotal: (map['subtotal'] as num).toDouble(),
        discount: (map['discount'] as num).toDouble(),
        tax: (map['tax'] as num).toDouble(),
        total: (map['total'] as num).toDouble(),
        paid: (map['paid'] as num).toDouble(),
        balance: (map['balance'] as num).toDouble(),
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: DateTime.parse(map['updated_at'] as String),
        isSynced: (map['is_synced'] as int) == 1,
      );
}

