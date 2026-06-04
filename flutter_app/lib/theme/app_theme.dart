import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData light(Map<String, dynamic> remote) {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorSchemeSeed: _hex(remote['primary'] ?? '#176B87'),
      scaffoldBackgroundColor: _hex(remote['surface'] ?? '#F6F8FB'),
      cardTheme: const CardThemeData(elevation: 0, margin: EdgeInsets.zero, shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(8)))),
      navigationBarTheme: const NavigationBarThemeData(height: 68, labelBehavior: NavigationDestinationLabelBehavior.alwaysShow),
    );
  }

  static ThemeData dark(Map<String, dynamic> remote) {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorSchemeSeed: _hex(remote['secondary'] ?? '#2D9CDB'),
      scaffoldBackgroundColor: _hex(remote['dark_surface'] ?? '#111827'),
      cardTheme: const CardThemeData(elevation: 0, margin: EdgeInsets.zero, shape: RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(8)))),
    );
  }

  static Color _hex(String value) {
    final cleaned = value.replaceAll('#', '');
    return Color(int.parse('FF$cleaned', radix: 16));
  }
}

