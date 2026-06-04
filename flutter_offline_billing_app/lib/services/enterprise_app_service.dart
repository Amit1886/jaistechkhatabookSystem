import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/enterprise_app_config.dart';
import 'api_service.dart';

class EnterpriseAppService {
  EnterpriseAppService({required ApiService api}) : _api = api;

  final ApiService _api;
  static const _cacheKey = 'enterprise.app.config.v3';

  Future<EnterpriseAppConfig> bootstrap({String mode = 'desktop'}) async {
    const endpoints = [
      '/api/app/bootstrap/',
      '/api/system/app-config/',
      '/api/mobile/bootstrap/',
      '/api/mobile/app-config/',
    ];
    Object? lastError;
    for (final endpoint in endpoints) {
      try {
        final payload = await _api.getJson(endpoint, query: {'platform': mode});
        final modules = payload['modules'];
        if (modules is! List || modules.isEmpty) {
          if (endpoint == '/api/system/app-config/') {
            await _writeCache(payload);
            return EnterpriseAppConfig.fallback();
          }
          lastError = 'Empty module payload from $endpoint';
          continue;
        }
        await _api.applyServerConfig(payload);
        await _writeCache(payload);
        return EnterpriseAppConfig.fromJson(payload);
      } catch (e) {
        lastError = e;
      }
    }

    final cached = await _readCache();
    if (cached != null &&
        cached['modules'] is List &&
        (cached['modules'] as List).isNotEmpty) {
      return EnterpriseAppConfig.fromJson(cached);
    }
    // ignore: avoid_print
    print('[API] enterprise bootstrap failed: $lastError');
    return EnterpriseAppConfig.fallback();
  }

  Future<EnterpriseAppConfig> refreshFromControlCenter(
      {String mode = 'desktop'}) async {
    try {
      final payload = await _api
          .getJson('/api/enterprise/dashboard/', query: {'platform': mode});
      await _writeCache(payload);
      return EnterpriseAppConfig.fromJson(payload);
    } catch (_) {
      return EnterpriseAppConfig.fallback();
    }
  }

  Future<void> _writeCache(Map<String, dynamic> payload) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_cacheKey, jsonEncode(payload));
  }

  Future<Map<String, dynamic>?> _readCache() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_cacheKey);
    if (raw == null || raw.isEmpty) return null;
    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map) {
      return decoded.map((key, value) => MapEntry(key.toString(), value));
    }
    return null;
  }
}
