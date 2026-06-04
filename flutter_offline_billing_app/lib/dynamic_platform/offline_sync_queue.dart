import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import 'enterprise_api_client.dart';

class OfflineSyncOperation {
  final String clientId;
  final String model;
  final String operation;
  final String? pk;
  final Map<String, dynamic> data;
  final DateTime createdAt;

  OfflineSyncOperation({
    required this.clientId,
    required this.model,
    required this.operation,
    required this.data,
    required this.createdAt,
    this.pk,
  });

  Map<String, dynamic> toJson() => {
        'client_id': clientId,
        'model': model,
        'operation': operation,
        'pk': pk,
        'data': data,
        'client_timestamp': createdAt.toIso8601String(),
      };

  factory OfflineSyncOperation.fromJson(Map<String, dynamic> json) {
    return OfflineSyncOperation(
      clientId: json['client_id']?.toString() ?? '',
      model: json['model']?.toString() ?? '',
      operation: json['operation']?.toString() ?? '',
      pk: json['pk']?.toString(),
      data: (json['data'] as Map?)?.cast<String, dynamic>() ?? {},
      createdAt: DateTime.tryParse(json['client_timestamp']?.toString() ?? '') ?? DateTime.now(),
    );
  }
}

class OfflineSyncQueue {
  static const _storageKey = 'enterprise_offline_sync_queue';
  final EnterpriseApiClient api;

  OfflineSyncQueue(this.api);

  Future<void> enqueue(OfflineSyncOperation operation) async {
    final prefs = await SharedPreferences.getInstance();
    final current = await pending();
    current.add(operation);
    await prefs.setString(_storageKey, jsonEncode(current.map((e) => e.toJson()).toList()));
  }

  Future<List<OfflineSyncOperation>> pending() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_storageKey);
    if (raw == null || raw.isEmpty) return [];
    final list = jsonDecode(raw) as List;
    return list.whereType<Map>().map((e) => OfflineSyncOperation.fromJson(e.cast<String, dynamic>())).toList();
  }

  Future<Map<String, dynamic>> flush({required String deviceId}) async {
    final operations = await pending();
    if (operations.isEmpty) return {'ok': true, 'results': []};
    final response = await api.postJson('/offline/push', {
      'device_id': deviceId,
      'operations': operations.map((e) => e.toJson()).toList(),
    });
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_storageKey);
    return response;
  }
}
