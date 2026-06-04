import 'package:shared_preferences/shared_preferences.dart';

/// Stores lightweight session state locally (offline).
class SessionService {
  static const _kUserId = 'session.user_id';
  static const _kLastSyncAt = 'sync.last_at';
  static const _kApiBaseUrl = 'sync.api_base_url';
  static const _kApiToken = 'sync.api_token';

  Future<void> setCurrentUserId(String? userId) async {
    final prefs = await SharedPreferences.getInstance();
    if (userId == null || userId.isEmpty) {
      await prefs.remove(_kUserId);
      return;
    }
    await prefs.setString(_kUserId, userId);
  }

  Future<String?> getCurrentUserId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_kUserId);
  }

  Future<void> setLastSyncAt(DateTime? value) async {
    final prefs = await SharedPreferences.getInstance();
    if (value == null) {
      await prefs.remove(_kLastSyncAt);
      return;
    }
    await prefs.setString(_kLastSyncAt, value.toIso8601String());
  }

  Future<DateTime?> getLastSyncAt() async {
    final prefs = await SharedPreferences.getInstance();
    final s = prefs.getString(_kLastSyncAt);
    if (s == null || s.isEmpty) return null;
    return DateTime.tryParse(s);
  }

  Future<void> setApiBaseUrl(String? baseUrl) async {
    final prefs = await SharedPreferences.getInstance();
    if (baseUrl == null || baseUrl.trim().isEmpty) {
      await prefs.remove(_kApiBaseUrl);
      return;
    }
    await prefs.setString(_kApiBaseUrl, baseUrl.trim());
  }

  Future<String?> getApiBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final s = prefs.getString(_kApiBaseUrl);
    if (s == null || s.isEmpty) return null;
    return s;
  }

  Future<void> setApiToken(String? token) async {
    final prefs = await SharedPreferences.getInstance();
    if (token == null || token.trim().isEmpty) {
      await prefs.remove(_kApiToken);
      return;
    }
    await prefs.setString(_kApiToken, token.trim());
  }

  Future<String?> getApiToken() async {
    final prefs = await SharedPreferences.getInstance();
    final s = prefs.getString(_kApiToken);
    if (s == null || s.isEmpty) return null;
    return s;
  }
}
