import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'secure_storage_service.dart';
import 'settings_service.dart';

class ApiException implements Exception {
  ApiException({
    required this.method,
    required this.url,
    required this.statusCode,
    required this.body,
  });

  final String method;
  final Uri url;
  final int statusCode;
  final String body;

  @override
  String toString() => 'API $method $url failed ($statusCode): $body';
}

/// HTTP API client.
///
/// - Uses `SettingsService.apiBaseUrl`
/// - Adds `Authorization` header when token is available
/// - Supports both:
///   - Bearer <accessToken>  (JWT)
///   - Token <syncToken>     (shared-token sync, if enabled)
class ApiService {
  ApiService({
    required SettingsService settings,
    required SecureStorageService secure,
  })  : _settings = settings,
        _secure = secure;

  final SettingsService _settings;
  final SecureStorageService _secure;

  Future<void> applyServerConfig(Map<String, dynamic> payload) async {
    final raw = (payload['api_base_url'] ?? payload['backend_url'] ?? '')
        .toString()
        .trim();
    if (raw.isEmpty) return;
    final uri = Uri.tryParse(raw);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) return;
    await _settings.setApiBaseUrl(
        raw.endsWith('/') ? raw.substring(0, raw.length - 1) : raw);
  }

  Uri _uri(String path, [Map<String, String>? query]) {
    return _uriForBase(_settings.apiBaseUrl.trim(), path, query);
  }

  Uri _uriForBase(String baseUrl, String path, [Map<String, String>? query]) {
    if (baseUrl.isEmpty) {
      throw StateError('API base URL is empty. Set it in Settings.');
    }
    final clean = path.startsWith('/') ? path : '/$path';
    final parsed = Uri.parse(baseUrl);
    return parsed.replace(path: '${parsed.path}$clean', queryParameters: query);
  }

  List<String> _baseCandidates() {
    final configured = _settings.apiBaseUrl.trim();
    final candidates = <String>[if (configured.isNotEmpty) configured];
    final parsed = Uri.tryParse(configured);
    final localHost = parsed != null &&
        {'localhost', '127.0.0.1', '10.0.2.2'}.contains(parsed.host);
    if (localHost) {
      if (parsed.host != '10.0.2.2') {
        candidates.add(parsed
            .replace(
                host: '10.0.2.2', port: parsed.port == 0 ? 8000 : parsed.port)
            .toString()
            .replaceFirst(RegExp(r'/$'), ''));
      }
      if (parsed.host != '127.0.0.1') {
        candidates.add(parsed
            .replace(
                host: '127.0.0.1', port: parsed.port == 0 ? 8000 : parsed.port)
            .toString()
            .replaceFirst(RegExp(r'/$'), ''));
      }
      for (final port in const [8000, 8080]) {
        if (parsed.port == port) continue;
        candidates.add(parsed
            .replace(port: port)
            .toString()
            .replaceFirst(RegExp(r'/$'), ''));
      }
    }
    return candidates.toSet().toList();
  }

  void _log(String message) {
    if (kDebugMode) debugPrint('[API] $message');
  }

  String _safeHeaders(Map<String, String> headers) {
    final copy = Map<String, String>.from(headers);
    if (copy.containsKey('Authorization')) copy['Authorization'] = '***';
    return copy.toString();
  }

  Future<http.Response> _sendWithFallback(
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, Object?>? body,
    String? tokenOverride,
    bool useSyncToken = false,
  }) async {
    Object? lastError;
    http.Response? lastResponse;
    for (final base in _baseCandidates()) {
      final url = _uriForBase(base, path, query);
      final headers = await _headers(
          tokenOverride: tokenOverride, useSyncToken: useSyncToken);
      _log('$method $url headers=${_safeHeaders(headers)}');
      try {
        final encoded = body == null ? null : jsonEncode(body);
        final response = switch (method) {
          'GET' => await http
              .get(url, headers: headers)
              .timeout(const Duration(seconds: 20)),
          'POST' => await http
              .post(url, headers: headers, body: encoded)
              .timeout(const Duration(seconds: 25)),
          'PUT' => await http
              .put(url, headers: headers, body: encoded)
              .timeout(const Duration(seconds: 25)),
          'PATCH' => await http
              .patch(url, headers: headers, body: encoded)
              .timeout(const Duration(seconds: 25)),
          'DELETE' => await http
              .delete(url, headers: headers)
              .timeout(const Duration(seconds: 25)),
          _ => throw StateError('Unsupported method $method'),
        };
        _log(
            '$method $url -> ${response.statusCode} ${response.body.length} bytes');
        if (response.statusCode == 404 ||
            response.statusCode == 502 ||
            response.statusCode == 503) {
          lastResponse = response;
          continue;
        }
        if (base != _settings.apiBaseUrl.trim() && response.statusCode < 500) {
          await _settings.setApiBaseUrl(base);
        }
        return response;
      } catch (e) {
        lastError = e;
        _log('$method $url failed: $e');
      }
    }
    if (lastResponse != null) return lastResponse;
    throw ApiException(
      method: method,
      url: _uri(path, query),
      statusCode: 0,
      body: 'Connection failed: $lastError',
    );
  }

  Future<Map<String, String>> _headers(
      {String? tokenOverride, bool useSyncToken = false}) async {
    final headers = <String, String>{'Content-Type': 'application/json'};

    final token = tokenOverride ??
        (useSyncToken ? _settings.syncToken : await _secure.getAccessToken());
    if (token.isEmpty) return headers;

    if (useSyncToken) {
      headers['Authorization'] = 'Token $token';
      return headers;
    }
    headers['Authorization'] = 'Bearer $token';
    return headers;
  }

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, String>? query,
    String? tokenOverride,
    bool useSyncToken = false,
  }) async {
    final url = _uri(path, query);
    final res = await _sendWithFallback('GET', path,
        query: query, tokenOverride: tokenOverride, useSyncToken: useSyncToken);
    return _decodeOrThrow(method: 'GET', url: url, res: res);
  }

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, Object?> body, {
    String? tokenOverride,
    bool useSyncToken = false,
  }) async {
    final url = _uri(path);
    final res = await _sendWithFallback('POST', path,
        body: body, tokenOverride: tokenOverride, useSyncToken: useSyncToken);
    return _decodeOrThrow(method: 'POST', url: url, res: res);
  }

  Future<Map<String, dynamic>> putJson(
    String path,
    Map<String, Object?> body, {
    String? tokenOverride,
    bool useSyncToken = false,
  }) async {
    final url = _uri(path);
    final res = await _sendWithFallback('PUT', path,
        body: body, tokenOverride: tokenOverride, useSyncToken: useSyncToken);
    return _decodeOrThrow(method: 'PUT', url: url, res: res);
  }

  Future<Map<String, dynamic>> patchJson(
    String path,
    Map<String, Object?> body, {
    String? tokenOverride,
    bool useSyncToken = false,
  }) async {
    final url = _uri(path);
    final res = await _sendWithFallback('PATCH', path,
        body: body, tokenOverride: tokenOverride, useSyncToken: useSyncToken);
    return _decodeOrThrow(method: 'PATCH', url: url, res: res);
  }

  Future<Map<String, dynamic>> deleteJson(
    String path, {
    String? tokenOverride,
    bool useSyncToken = false,
  }) async {
    final url = _uri(path);
    final res = await _sendWithFallback('DELETE', path,
        tokenOverride: tokenOverride, useSyncToken: useSyncToken);
    return _decodeOrThrow(method: 'DELETE', url: url, res: res);
  }

  Map<String, dynamic> _decodeOrThrow(
      {required String method, required Uri url, required http.Response res}) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiException(
          method: method, url: url, statusCode: res.statusCode, body: res.body);
    }
    final decoded = jsonDecode(res.body);
    if (decoded is Map<String, dynamic>) return decoded;
    throw ApiException(
        method: method,
        url: url,
        statusCode: res.statusCode,
        body: 'Response is not a JSON object');
  }
}
