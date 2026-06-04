import 'api_service.dart';

class EnterpriseLiveService {
  EnterpriseLiveService({required ApiService api}) : _api = api;

  final ApiService _api;

  // Legacy endpoints (kept for compatibility)
  Future<Map<String, dynamic>> dashboard() => _api.getJson('/api/app/dashboard/');

  Future<List<Map<String, dynamic>>> parties({String partyType = ''}) async {
    final res = await _api.getJson(
      '/api/app/parties/',
      query: partyType.isEmpty ? null : {'party_type': partyType},
    );
    return _results(res);
  }

  Future<void> createParty({
    required String name,
    String mobile = '',
    String partyType = 'customer',
  }) async {
    await _api.postJson('/api/app/parties/', {
      'name': name,
      'mobile': mobile,
      'party_type': partyType,
    });
  }

  Future<List<Map<String, dynamic>>> products() async {
    final res = await _api.getJson('/api/app/products/');
    return _results(res);
  }

  Future<void> createProduct({
    required String name,
    required String sku,
    required String price,
    required String stock,
  }) async {
    await _api.postJson('/api/app/products/', {
      'name': name,
      'sku': sku,
      'price': price,
      'stock': stock,
    });
  }

  Future<List<Map<String, dynamic>>> transactions() async {
    final res = await _api.getJson('/api/app/transactions/');
    return _results(res);
  }

  Future<void> createTransaction({
    required String partyId,
    required String amount,
    required String txnType,
    String mode = 'cash',
    String notes = '',
  }) async {
    await _api.postJson('/api/app/transactions/', {
      'party_id': partyId,
      'amount': amount,
      'txn_type': txnType,
      'txn_mode': mode,
      'notes': notes,
    });
  }

  // ============================================================
  // NEW FLUTTER-SPECIFIC API ENDPOINTS
  // ============================================================

  /// Get current user profile with all details
  Future<Map<String, dynamic>> getUserProfile() {
    return _api.getJson('/api/auth/user/profile/');
  }

  /// Get user permissions from backend
  Future<Map<String, dynamic>> getUserPermissions() {
    return _api.getJson('/api/auth/user/permissions/');
  }

  /// Get dashboard data with real metrics
  Future<Map<String, dynamic>> getDashboardData() {
    return _api.getJson('/api/dashboard/data/');
  }

  /// Get products list with pagination and search
  Future<Map<String, dynamic>> getInventoryProducts({
    int limit = 100,
    int offset = 0,
    String search = '',
  }) {
    final query = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (search.isNotEmpty) query['search'] = search;
    return _api.getJson('/api/inventory/products/', query: query);
  }

  /// Get invoices list with filtering
  Future<Map<String, dynamic>> getBillingInvoices({
    int limit = 50,
    int offset = 0,
    String status = '',
  }) {
    final query = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (status.isNotEmpty) query['status'] = status;
    return _api.getJson('/api/billing/invoices/', query: query);
  }

  /// Get customers/parties list with search
  Future<Map<String, dynamic>> getCRMParties({
    int limit = 100,
    int offset = 0,
    String search = '',
  }) {
    final query = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (search.isNotEmpty) query['search'] = search;
    return _api.getJson('/api/crm/parties/', query: query);
  }

  /// Get transactions/ledger entries
  Future<Map<String, dynamic>> getTransactionsList({
    int limit = 100,
    int offset = 0,
    String partyId = '',
  }) {
    final query = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (partyId.isNotEmpty) query['party_id'] = partyId;
    return _api.getJson('/api/ledger/transactions/', query: query);
  }

  List<Map<String, dynamic>> _results(Map<String, dynamic> res) {
    final raw = res['results'];
    if (raw is! List) return const [];
    return raw.whereType<Map>().map((row) => row.map((key, value) => MapEntry(key.toString(), value))).toList();
  }
}
