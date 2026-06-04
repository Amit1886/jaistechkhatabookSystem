import '../database/local_db.dart';
import '../database/tables.dart';
import '../models/expense_model.dart';
import 'id_service.dart';

class ExpenseService {
  ExpenseService(this._db);

  final LocalDb _db;

  Future<List<ExpenseModel>> list({required String businessId}) async {
    final rows = await _db.query(
      Tables.expenses,
      where: 'business_id = ? AND is_deleted = 0',
      whereArgs: [businessId],
      orderBy: 'date DESC',
      limit: 500,
    );
    return rows.map(ExpenseModel.fromMap).toList();
  }

  Future<ExpenseModel> create({
    required String businessId,
    required double amount,
    required DateTime date,
    String? category,
    String? notes,
  }) async {
    if (amount <= 0) throw Exception('Amount must be > 0');
    final now = DateTime.now();
    final obj = ExpenseModel(
      id: IdService.newId(),
      businessId: businessId,
      category: category?.trim().isEmpty ?? true ? null : category?.trim(),
      amount: amount,
      date: date,
      notes: notes?.trim().isEmpty ?? true ? null : notes?.trim(),
      createdAt: now,
      updatedAt: now,
      isSynced: false,
      isDeleted: false,
    );
    await _db.upsert(Tables.expenses, obj.toMap());
    return obj;
  }

  Future<void> update(ExpenseModel expense) async {
    final updated = expense.copyWith(updatedAt: DateTime.now(), isSynced: false);
    await _db.upsert(Tables.expenses, updated.toMap());
  }

  Future<void> delete(String expenseId) async {
    await _db.softDeleteById(Tables.expenses, expenseId);
  }
}

