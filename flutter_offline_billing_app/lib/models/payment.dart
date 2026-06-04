class Payment {
  final String id;
  final String invoiceId;
  final double amount;
  final String mode; // cash/upi/card/bank
  final String reference;
  final String status; // success/failed/pending/hold
  final DateTime paidAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final bool isSynced;

  Payment({
    required this.id,
    required this.invoiceId,
    required this.amount,
    required this.mode,
    required this.reference,
    required this.status,
    required this.paidAt,
    required this.createdAt,
    required this.updatedAt,
    required this.isSynced,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'invoice_id': invoiceId,
        'amount': amount,
        'mode': mode,
        'reference': reference,
        'status': status,
        'paid_at': paidAt.toIso8601String(),
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
        'is_synced': isSynced ? 1 : 0,
      };

  static Payment fromMap(Map<String, Object?> map) => Payment(
        id: map['id'] as String,
        invoiceId: map['invoice_id'] as String,
        amount: (map['amount'] as num).toDouble(),
        mode: map['mode'] as String,
        reference: (map['reference'] as String?) ?? '',
        status: map['status'] as String,
        paidAt: DateTime.parse(map['paid_at'] as String),
        createdAt: DateTime.parse(map['created_at'] as String),
        updatedAt: DateTime.parse(map['updated_at'] as String),
        isSynced: (map['is_synced'] as int) == 1,
      );
}

