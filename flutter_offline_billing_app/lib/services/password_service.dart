import 'dart:convert';

import 'package:crypto/crypto.dart';

/// Local-only password hashing for offline login.
/// This keeps the app fully standalone and offline-capable.
class PasswordService {
  static String hashPassword(String password, {required String salt}) {
    final bytes = utf8.encode('$salt::$password');
    return sha256.convert(bytes).toString();
  }
}

