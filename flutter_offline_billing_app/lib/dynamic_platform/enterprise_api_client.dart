import 'dart:convert';

import 'package:http/http.dart' as http;

class EnterpriseApiClient {
  final String baseUrl;
  final http.Client _client;
  String? accessToken;
  String? companyId;
  String? tenantId;

  EnterpriseApiClient({
    required this.baseUrl,
    http.Client? client,
    this.accessToken,
    this.companyId,
    this.tenantId,
  }) : _client = client ?? http.Client();

  Uri _uri(String path) {
    final cleanBase = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$cleanBase$cleanPath');
  }

  Map<String, String> _headers() {
    return {
      'Content-Type': 'application/json',
      if (accessToken != null && accessToken!.isNotEmpty) 'Authorization': 'Bearer $accessToken',
      if (companyId != null && companyId!.isNotEmpty) 'X-Company-Id': companyId!,
      if (tenantId != null && tenantId!.isNotEmpty) 'X-Tenant-Id': tenantId!,
    };
  }

  Future<Map<String, dynamic>> getJson(String path) async {
    final response = await _client.get(_uri(path), headers: _headers());
    return _decode(response);
  }

  Future<Map<String, dynamic>> postJson(String path, Map<String, dynamic> body) async {
    final response = await _client.post(_uri(path), headers: _headers(), body: jsonEncode(body));
    return _decode(response);
  }

  Future<Map<String, dynamic>> patchJson(String path, Map<String, dynamic> body) async {
    final response = await _client.patch(_uri(path), headers: _headers(), body: jsonEncode(body));
    return _decode(response);
  }

  Future<void> delete(String path) async {
    final response = await _client.delete(_uri(path), headers: _headers());
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Delete failed: ${response.statusCode} ${response.body}');
    }
  }

  Map<String, dynamic> _decode(http.Response response) {
    final body = response.body.isEmpty ? <String, dynamic>{} : jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(body['detail']?.toString() ?? 'Request failed: ${response.statusCode}');
    }
    return body;
  }
}
