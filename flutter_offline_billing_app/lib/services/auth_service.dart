import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';

import '../database/local_db.dart';
import '../database/tables.dart';
import '../models/user_model.dart';
import 'api_service.dart';
import 'secure_storage_service.dart';
import 'settings_service.dart';
import 'id_service.dart';

class AuthException implements Exception {
  AuthException(this.message);
  final String message;

  @override
  String toString() => message;
}

class AuthService {
  AuthService({
    required LocalDb db,
    required ApiService api,
    required SecureStorageService secureStorage,
    required SettingsService settings,
  })  : _db = db,
        _api = api,
        _secure = secureStorage,
        _settings = settings;

  final LocalDb _db;
  final ApiService _api;
  final SecureStorageService _secure;
  final SettingsService _settings;

  static String _newSalt() {
    final rand = Random.secure();
    final bytes = List<int>.generate(16, (_) => rand.nextInt(256));
    return base64UrlEncode(bytes);
  }

  static String _hashPassword(
      {required String salt, required String password}) {
    return sha256.convert(utf8.encode('$salt:$password')).toString();
  }

  Future<UserModel?> bootstrap() async {
    final userId = await _secure.getUserId();
    if (userId.isEmpty) return null;

    final rows = await _db.query(Tables.users,
        where: 'id = ?', whereArgs: [userId], limit: 1);
    if (rows.isNotEmpty) return UserModel.fromMap(rows.first);

    // If user is not in DB (first run after reinstall), create a minimal local profile.
    final email = await _secure.getUserEmail();
    final name = await _secure.getUserName();
    final now = DateTime.now();
    final user = UserModel(
      id: userId,
      email: email.isEmpty ? userId : email,
      name: name.isEmpty ? userId : name,
      createdAt: now,
      updatedAt: now,
      isSynced: true,
      isDeleted: false,
    );
    await _db.upsert(Tables.users, user.toMap());
    return user;
  }

  Future<UserModel> login({
    required String username,
    required String password,
  }) async {
    final u = username.trim();
    if (u.isEmpty) throw AuthException('Username is required');
    if (password.isEmpty) throw AuthException('Password is required');

    // In local Django runserver mode /api/login/ is available. FastAPI shapes
    // are kept as fallbacks for API-only deployments.
    final Map<String, dynamic> res;
    try {
      res = await _loginWithFallback(
        u == 'demo' || u == 'demo@test.com'
            ? '/api/demo-login/'
            : '/api/login/',
        {'username': u, 'identifier': u, 'password': password},
      );
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        throw AuthException(
          'Invalid credentials. Web OTP login alag hai; app ke liye email/mobile + password chahiye.',
        );
      }
      if (e.statusCode == 403) {
        throw AuthException(
            'Account active nahi hai. Web par OTP verify karke phir app login try karo.');
      }
      rethrow;
    }

    final access = (res['access'] ?? '').toString();
    final refresh = (res['refresh'] ?? '').toString();
    if (access.isEmpty || refresh.isEmpty) {
      throw AuthException('Login failed: missing token in response');
    }

    final userPayload = res['user'];
    final mapped = userPayload is Map ? userPayload : const {};
    final now = DateTime.now();
    final salt = _newSalt();
    final hash = _hashPassword(salt: salt, password: password);
    final user = UserModel(
      id: (mapped['id'] ?? u).toString(),
      email: (mapped['email'] ?? u).toString(),
      name: (mapped['name'] ?? mapped['username'] ?? u).toString(),
      createdAt: now,
      updatedAt: now,
      isSynced: true,
      isDeleted: false,
    );

    await _secure.setSession(
      accessToken: access,
      refreshToken: refresh,
      userId: user.id,
      email: user.email,
      name: user.name,
    );

    await _db.upsert(
      Tables.users,
      {
        ...user.toMap(),
        'password_salt': salt,
        'password_hash': hash,
      },
    );
    await _ensureDefaultBusiness(userId: user.id);
    return user;
  }

  Future<Map<String, dynamic>> _loginWithFallback(
    String primaryEndpoint,
    Map<String, Object?> primaryBody,
  ) async {
    try {
      return await _api.postJson(primaryEndpoint, primaryBody,
          tokenOverride: null);
    } on ApiException catch (e) {
      if (e.statusCode != 0 && e.statusCode != 404 && e.statusCode < 500) {
        rethrow;
      }
      return await _api.postJson(
        '/api/login/',
        {
          'username': primaryBody['username'],
          'identifier': primaryBody['identifier'],
          'password': primaryBody['password'],
        },
        tokenOverride: null,
      );
    }
  }

  /// Offline signup (no internet required).
  ///
  /// Creates a local user row with a salted password hash, then starts a local session.
  Future<UserModel> signupOffline({
    required String username,
    required String password,
    String? name,
  }) async {
    final u = username.trim();
    if (u.isEmpty) throw AuthException('Username is required');
    if (password.isEmpty) throw AuthException('Password is required');
    if (password.length < 4) {
      throw AuthException('Password must be at least 4 characters');
    }

    final existing = await _db.query(
      Tables.users,
      where: 'id = ? OR email = ?',
      whereArgs: [u, u],
      limit: 1,
    );
    if (existing.isNotEmpty) throw AuthException('User already exists');

    final now = DateTime.now();
    final salt = _newSalt();
    final hash = _hashPassword(salt: salt, password: password);

    final user = UserModel(
      id: u,
      email: u,
      name: (name ?? '').trim().isEmpty ? u : name!.trim(),
      createdAt: now,
      updatedAt: now,
      isSynced: false,
      isDeleted: false,
    );

    await _db.upsert(
      Tables.users,
      {
        ...user.toMap(),
        'password_salt': salt,
        'password_hash': hash,
      },
    );

    await _secure.setSession(
      accessToken: '',
      refreshToken: '',
      userId: user.id,
      email: user.email,
      name: user.name,
    );

    await _ensureDefaultBusiness(userId: user.id);
    return user;
  }

  Future<UserModel> signupOnline({
    required String username,
    required String password,
    String? name,
  }) async {
    final u = username.trim();
    if (u.isEmpty) throw AuthException('Username is required');
    if (password.isEmpty) throw AuthException('Password is required');
    if (password.length < 4) {
      throw AuthException('Password must be at least 4 characters');
    }

    final res = await _api.postJson(
      '/api/app-signup/',
      {
        'username': u,
        'email': u,
        'name': (name ?? '').trim(),
        'password': password,
      },
      tokenOverride: null,
    );

    final access = (res['access'] ?? '').toString();
    final refresh = (res['refresh'] ?? '').toString();
    if (access.isEmpty || refresh.isEmpty) {
      throw AuthException('Signup failed: missing token in response');
    }

    final userPayload = res['user'];
    final mapped = userPayload is Map ? userPayload : const {};
    final now = DateTime.now();
    final salt = _newSalt();
    final hash = _hashPassword(salt: salt, password: password);
    final user = UserModel(
      id: (mapped['id'] ?? u).toString(),
      email: (mapped['email'] ?? u).toString(),
      name: (mapped['name'] ?? mapped['username'] ?? u).toString(),
      createdAt: now,
      updatedAt: now,
      isSynced: true,
      isDeleted: false,
    );

    await _secure.setSession(
      accessToken: access,
      refreshToken: refresh,
      userId: user.id,
      email: user.email,
      name: user.name,
    );

    await _db.upsert(
      Tables.users,
      {
        ...user.toMap(),
        'password_salt': salt,
        'password_hash': hash,
      },
    );
    await _ensureDefaultBusiness(userId: user.id);
    return user;
  }

  /// Offline login (no internet required).
  ///
  /// Validates username + password against the local SQLite user row.
  Future<UserModel> loginOffline({
    required String username,
    required String password,
  }) async {
    final u = username.trim();
    if (u.isEmpty) throw AuthException('Username is required');
    if (password.isEmpty) throw AuthException('Password is required');

    final rows = await _db.query(
      Tables.users,
      where: 'id = ? OR email = ?',
      whereArgs: [u, u],
      limit: 1,
    );
    if (rows.isEmpty) {
      throw AuthException(
          'No offline account found. Tap "Create account" first.');
    }

    final row = rows.first;
    final salt = (row['password_salt'] ?? '').toString();
    final expected = (row['password_hash'] ?? '').toString();
    if (salt.isEmpty || expected.isEmpty) {
      throw AuthException(
          'Offline password is not set for this user. Login online once or sign up offline.');
    }

    final got = _hashPassword(salt: salt, password: password);
    if (got != expected) throw AuthException('Invalid credentials');

    final user = UserModel.fromMap(row);

    // If this same user already has valid JWT tokens stored, keep them.
    final existingUserId = await _secure.getUserId();
    final keepTokens = existingUserId == user.id;
    final access = keepTokens ? await _secure.getAccessToken() : '';
    final refresh = keepTokens ? await _secure.getRefreshToken() : '';

    await _secure.setSession(
      accessToken: access,
      refreshToken: refresh,
      userId: user.id,
      email: user.email,
      name: user.name,
    );

    await _ensureDefaultBusiness(userId: user.id);
    return user;
  }

  Future<void> logout() async {
    await _secure.clearSession();
  }

  Future<void> _ensureDefaultBusiness({required String userId}) async {
    if (_settings.selectedBusinessId.isNotEmpty) return;

    final existing = await _db.query(
      Tables.businesses,
      where: 'user_id = ? AND is_deleted = 0',
      whereArgs: [userId],
      limit: 1,
    );
    if (existing.isNotEmpty) {
      final id = existing.first['id']?.toString() ?? '';
      if (id.isNotEmpty) {
        await _settings.setSelectedBusinessId(id);
        return;
      }
    }

    final now = DateTime.now();
    final businessId = IdService.newId();
    await _db.upsert(
      Tables.businesses,
      {
        'id': businessId,
        'user_id': userId,
        'name': 'My Business',
        'address': null,
        'created_at': now.toIso8601String(),
        'updated_at': now.toIso8601String(),
        'is_synced': 0,
        'is_deleted': 0,
      },
    );
    await _settings.setSelectedBusinessId(businessId);
  }
}
