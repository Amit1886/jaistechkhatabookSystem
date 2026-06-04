import '../database/local_db.dart';

class DashboardSummary {
  const DashboardSummary({
    required this.salesTotal,
    required this.salesPaid,
    required this.salesBalance,
    required this.purchaseTotal,
    required this.expenseTotal,
    required this.stockCount,
    required this.stockValue,
  });

  final double salesTotal;
  final double salesPaid;
  final double salesBalance;
  final double purchaseTotal;
  final double expenseTotal;
  final int stockCount;
  final double stockValue;
}

/// Offline reports built from local SQFlite data.
class ReportService {
  ReportService(this._db);

  final LocalDb _db;

  Future<DashboardSummary> dashboardSummary({required String businessId}) async {
    final salesRow = await _singleRow(
      '''
SELECT
  COALESCE(SUM(total), 0) AS total_sales,
  COALESCE(SUM(paid), 0) AS total_paid,
  COALESCE(SUM(balance), 0) AS total_balance
FROM invoices
WHERE business_id = ? AND type = 'sale' AND is_deleted = 0
''',
      [businessId],
    );

    final purchaseRow = await _singleRow(
      '''
SELECT COALESCE(SUM(total), 0) AS total_purchase
FROM invoices
WHERE business_id = ? AND type = 'purchase' AND is_deleted = 0
''',
      [businessId],
    );

    final expenseRow = await _singleRow(
      '''
SELECT COALESCE(SUM(amount), 0) AS total_expense
FROM expenses
WHERE business_id = ? AND is_deleted = 0
''',
      [businessId],
    );

    final stockRow = await _singleRow(
      '''
SELECT
  COUNT(*) AS product_count,
  COALESCE(SUM(stock_qty * purchase_price), 0) AS stock_value
FROM products
WHERE business_id = ? AND is_deleted = 0
''',
      [businessId],
    );

    return DashboardSummary(
      salesTotal: ((salesRow['total_sales'] as num?) ?? 0).toDouble(),
      salesPaid: ((salesRow['total_paid'] as num?) ?? 0).toDouble(),
      salesBalance: ((salesRow['total_balance'] as num?) ?? 0).toDouble(),
      purchaseTotal: ((purchaseRow['total_purchase'] as num?) ?? 0).toDouble(),
      expenseTotal: ((expenseRow['total_expense'] as num?) ?? 0).toDouble(),
      stockCount: ((stockRow['product_count'] as num?) ?? 0).toInt(),
      stockValue: ((stockRow['stock_value'] as num?) ?? 0).toDouble(),
    );
  }

  Future<Map<String, Object?>> _singleRow(String sql, List<Object?> args) async {
    final rows = await _db.rawQuery(sql, args);
    if (rows.isEmpty) return const <String, Object?>{};
    return rows.first;
  }
}

