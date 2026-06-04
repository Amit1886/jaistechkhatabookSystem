import '../services/api_client.dart';

class SyncQueueService {
  SyncQueueService(this.api);

  final ApiClient api;
  final List<Map<String, dynamic>> _pending = [];

  void enqueue(Map<String, dynamic> item) {
    _pending.add(item);
  }

  Future<void> flush() async {
    if (_pending.isEmpty) return;
    await api.post('/api/sync/push/', {'items': List<Map<String, dynamic>>.from(_pending)});
    _pending.clear();
  }
}

