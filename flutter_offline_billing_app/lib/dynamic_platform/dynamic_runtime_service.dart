import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/enterprise_app_config.dart';
import '../services/api_service.dart';
import 'dynamic_metadata.dart';

class DynamicRuntimeService {
  DynamicRuntimeService({required ApiService api}) : _api = api;

  final ApiService _api;

  static const _bootstrapCacheKey = 'enterprise.runtime.bootstrap.v2';
  static const _screensCacheKey = 'enterprise.runtime.screens.v2';
  static const _screenCachePrefix = 'enterprise.runtime.screen.';

  Future<EnterpriseAppConfig> bootstrap({String platform = 'app'}) async {
    const endpoints = [
      '/api/system/app-config/',
      '/fastapi/mobile/bootstrap',
      '/api/mobile/bootstrap/',
    ];
    for (final endpoint in endpoints) {
      try {
        final payload = await _api.getJson(endpoint, query: {'platform': platform});
        await _api.applyServerConfig(payload);
        await _writeJson(_bootstrapCacheKey, payload);
        return EnterpriseAppConfig.fromJson(payload);
      } catch (_) {}
    }
    final cached = await _readJson(_bootstrapCacheKey);
    if (cached != null) return EnterpriseAppConfig.fromJson(cached);
    return EnterpriseAppConfig.fallback();
  }

  Future<List<DynamicScreenMeta>> screens() async {
    try {
      final payload = await _api.getJson('/fastapi/mobile/screens');
      await _writeJson(_screensCacheKey, payload);
      return _screensFromPayload(payload);
    } catch (_) {
      final cached = await _readJson(_screensCacheKey);
      if (cached != null) return _screensFromPayload(cached);
      return const [];
    }
  }

  Future<DynamicScreenMeta?> screen(String modelKey) async {
    if (modelKey.trim().isEmpty) return null;
    final cacheKey = '$_screenCachePrefix$modelKey';
    try {
      final payload = await _api.getJson('/fastapi/mobile/screens/$modelKey');
      await _writeJson(cacheKey, payload);
      return DynamicScreenMeta.fromJson(payload);
    } catch (_) {
      final cached = await _readJson(cacheKey);
      return cached == null ? null : DynamicScreenMeta.fromJson(cached);
    }
  }

  Future<Map<String, dynamic>> listRecords(
    DynamicScreenMeta screen, {
    String query = '',
    int limit = 50,
    int offset = 0,
    Map<String, String> filters = const {},
  }) {
    final params = <String, String>{
      'limit': '$limit',
      'offset': '$offset',
      if (query.trim().isNotEmpty) 'q': query.trim(),
      ...filters,
    };
    return _api.getJson(screen.listEndpoint, query: params);
  }

  Future<Map<String, dynamic>> createRecord(DynamicScreenMeta screen, Map<String, Object?> value) {
    return _api.postJson(screen.formEndpoint, {'data': value});
  }

  Future<Map<String, dynamic>> updateRecord(DynamicScreenMeta screen, Object id, Map<String, Object?> value) {
    return _api.patchJson('${screen.formEndpoint}/$id', {'data': value});
  }

  List<DynamicScreenMeta> screensForModule(List<DynamicScreenMeta> screens, EnterpriseModule module) {
    final modelKey = (module.settings['model_key'] ?? module.settings['model'] ?? '').toString();
    if (modelKey.isNotEmpty) {
      return screens.where((screen) => screen.model == modelKey).toList();
    }
    final moduleKey = module.key.toLowerCase();
    return screens.where((screen) {
      final model = screen.model.toLowerCase();
      return model.startsWith('$moduleKey.') ||
          model.contains('.$moduleKey') ||
          model.contains(moduleKey);
    }).take(12).toList();
  }

  List<DynamicScreenMeta> _screensFromPayload(Map<String, dynamic> payload) {
    final raw = payload['results'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((row) => DynamicScreenMeta.fromJson(row.map((key, value) => MapEntry(key.toString(), value))))
        .toList();
  }

  Future<void> _writeJson(String key, Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(key, jsonEncode(payload));
  }

  Future<Map<String, dynamic>?> _readJson(String key) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(key);
    if (raw == null || raw.isEmpty) return null;
    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map) return decoded.map((key, value) => MapEntry(key.toString(), value));
    return null;
  }
}
