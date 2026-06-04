import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorageService {
  static const _kAccessToken = 'access_token';
  static const _kRefreshToken = 'refresh_token';
  static const _kUserId = 'user_id';
  static const _kUserEmail = 'user_email';
  static const _kUserName = 'user_name';

  final FlutterSecureStorage _storage;

  SecureStorageService({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
            );

  Future<void> setSession({
    required String accessToken,
    required String refreshToken,
    required String userId,
    required String email,
    required String name,
  }) async {
    await _storage.write(key: _kAccessToken, value: accessToken);
    await _storage.write(key: _kRefreshToken, value: refreshToken);
    await _storage.write(key: _kUserId, value: userId);
    await _storage.write(key: _kUserEmail, value: email);
    await _storage.write(key: _kUserName, value: name);
  }

  Future<String> getAccessToken() async => (await _storage.read(key: _kAccessToken)) ?? '';
  Future<String> getRefreshToken() async => (await _storage.read(key: _kRefreshToken)) ?? '';

  Future<String> getUserId() async => (await _storage.read(key: _kUserId)) ?? '';
  Future<String> getUserEmail() async => (await _storage.read(key: _kUserEmail)) ?? '';
  Future<String> getUserName() async => (await _storage.read(key: _kUserName)) ?? '';

  Future<void> clearSession() async {
    await _storage.delete(key: _kAccessToken);
    await _storage.delete(key: _kRefreshToken);
    await _storage.delete(key: _kUserId);
    await _storage.delete(key: _kUserEmail);
    await _storage.delete(key: _kUserName);
  }
}

