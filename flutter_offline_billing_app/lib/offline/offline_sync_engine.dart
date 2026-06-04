import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class OfflineSyncJob {
  const OfflineSyncJob({
    required this.module,
    required this.operation,
    required this.payload,
    required this.createdAt,
  });

  final String module;
  final String operation;
  final Map<String, Object?> payload;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
        'module': module,
        'operation': operation,
        'payload': payload,
        'created_at': createdAt.toIso8601String(),
      };

  factory OfflineSyncJob.fromJson(Map<String, dynamic> json) {
    return OfflineSyncJob(
      module: (json['module'] ?? '').toString(),
      operation: (json['operation'] ?? '').toString(),
      payload: (json['payload'] as Map?)?.map((key, value) => MapEntry(key.toString(), value)) ?? const {},
      createdAt: DateTime.tryParse((json['created_at'] ?? '').toString()) ?? DateTime.now(),
    );
  }
}

class OfflineSyncEngine {
  static const _cacheKey = 'enterprise.offline.sync.queue.v1';
  final List<OfflineSyncJob> _queue = [];

  List<OfflineSyncJob> get pendingJobs => List.unmodifiable(_queue);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_cacheKey);
    if (raw == null || raw.isEmpty) return;
    final decoded = jsonDecode(raw);
    if (decoded is! List) return;
    _queue
      ..clear()
      ..addAll(decoded.whereType<Map>().map((row) => OfflineSyncJob.fromJson(row.map((key, value) => MapEntry(key.toString(), value)))));
  }

  Future<void> enqueue({
    required String module,
    required String operation,
    required Map<String, Object?> payload,
  }) async {
    _queue.add(
      OfflineSyncJob(
        module: module,
        operation: operation,
        payload: payload,
        createdAt: DateTime.now(),
      ),
    );
    await _persist();
  }

  Future<void> markSynced(OfflineSyncJob job) async {
    _queue.remove(job);
    await _persist();
  }

  Future<void> clear() async {
    _queue.clear();
    await _persist();
  }

  Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_cacheKey, jsonEncode(_queue.map((job) => job.toJson()).toList()));
  }
}
