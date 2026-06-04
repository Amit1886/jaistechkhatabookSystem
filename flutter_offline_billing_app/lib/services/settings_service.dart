import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsService {
  // Android emulator uses 10.0.2.2 to reach the host machine localhost.
  static const String liveServerIp = '10.0.2.2:8000';

  static String get defaultBaseUrl {
    if (kIsWeb) {
      return 'http://127.0.0.1:8000';
    }
    return 'http://$liveServerIp';
  }

  static const _defaultSyncToken = 'local-dev-sync-token';
  static const _kApiBaseUrl = 'api_base_url';
  static const _kSyncToken = 'sync_api_token';
  static const _kSelectedBusinessId = 'selected_business_id';

  SharedPreferences? _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    final saved = _p.getString(_kApiBaseUrl);
    final shouldResetToLocal = saved == null ||
        saved.contains('127.0.0.1:8000') ||
        saved.contains('10.0.2.2:8000') ||
        saved.contains('localhost:8000') ||
        saved.contains('127.0.0.1:57824') ||
        saved.contains('localhost:57824') ||
        saved.contains('49.43.113.95');
    final normalized =
        _normalizeBaseUrl(shouldResetToLocal ? defaultBaseUrl : saved);
    if (saved != normalized) {
      await _p.setString(_kApiBaseUrl, normalized);
    }
  }

  SharedPreferences get _p {
    final prefs = _prefs;
    if (prefs == null) {
      throw StateError('SettingsService not initialized. Call init() first.');
    }
    return prefs;
  }

  String get apiBaseUrl =>
      _normalizeBaseUrl(_p.getString(_kApiBaseUrl) ?? defaultBaseUrl);

  Future<void> setApiBaseUrl(String value) async {
    await _p.setString(_kApiBaseUrl, _normalizeBaseUrl(value));
  }

  String get syncToken {
    final saved = _p.getString(_kSyncToken);
    if (saved == null || saved.trim().isEmpty) {
      return _defaultSyncToken;
    }
    return saved;
  }

  Future<void> setSyncToken(String value) async {
    await _p.setString(_kSyncToken, value.trim());
  }

  String get selectedBusinessId => _p.getString(_kSelectedBusinessId) ?? '';

  Future<void> setSelectedBusinessId(String value) async {
    await _p.setString(_kSelectedBusinessId, value.trim());
  }

  static String _normalizeBaseUrl(String value) {
    var raw = value.trim();
    if (raw.isEmpty) return defaultBaseUrl;
    raw = raw.replaceAll(RegExp(r'/+$'), '');
    final uri = Uri.tryParse(raw);
    if (uri != null && uri.hasScheme && uri.host.isNotEmpty) {
      if ({'127.0.0.1', 'localhost'}.contains(uri.host) &&
          (uri.port == 8000 || uri.port == 57824)) {
        return defaultBaseUrl;
      }
      return raw;
    }
    return 'http://$raw';
  }
}
