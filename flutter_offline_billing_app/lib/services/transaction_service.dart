import '../database/local_db.dart';
import '../database/tables.dart';
import '../models/transaction_model.dart';
import 'id_service.dart';

class TransactionService {
  TransactionService(this._db);

  final LocalDb _db;

  Future<List<TransactionModel>> list({
    required String businessId,
    String? type,
    String? partyId,
  }) async {
    final where = <String>['business_id = ?', 'is_deleted = 0'];
    final args = <Object?>[businessId];
    if (type != null && type.isNotEmpty) {
      where.add('type = ?');
      args.add(type);
    }
    if (partyId != null && partyId.isNotEmpty) {
      where.add('party_id = ?');
      args.add(partyId);
    }
    final rows = await _db.query(
      Tables.transactions,
      where: where.join(' AND '),
      whereArgs: args,
      orderBy: 'date DESC',
      limit: 500,
    );
    return rows.map(TransactionModel.fromMap).toList();
  }

  Future<TransactionModel> create({
    required String businessId,
    required String type,
    required double amount,
    required String mode,
    String? partyId,
    String? invoiceId,
    String? reference,
    String? notes,
    DateTime? date,
  }) async {
    if (amount <= 0) throw Exception('Amount must be > 0');
    final now = DateTime.now();
    final obj = TransactionModel(
      id: IdService.newId(),
      businessId: businessId,
      partyId: partyId,
      invoiceId: invoiceId,
      type: type,
      amount: amount,
      mode: mode,
      reference: reference?.trim().isEmpty ?? true ? null : reference?.trim(),
      date: date ?? now,
      notes: notes?.trim().isEmpty ?? true ? null : notes?.trim(),
      createdAt: now,
      updatedAt: now,
      isSynced: false,
      isDeleted: false,
    );
    await _db.upsert(Tables.transactions, obj.toMap());
    return obj;
  }

  Future<void> delete(String transactionId) async {
    await _db.softDeleteById(Tables.transactions, transactionId);
  }
}

