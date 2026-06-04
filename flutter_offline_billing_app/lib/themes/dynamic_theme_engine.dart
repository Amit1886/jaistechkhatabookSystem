import 'package:flutter/material.dart';

import '../models/enterprise_app_config.dart';

class DynamicThemeEngine {
  const DynamicThemeEngine._();

  static ThemeData buildLight(EnterpriseThemeConfig config) {
    final scheme = ColorScheme.fromSeed(seedColor: config.primary, brightness: Brightness.light);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme.copyWith(secondary: config.secondary),
      scaffoldBackgroundColor: config.surface,
      visualDensity: config.density == 'compact' ? VisualDensity.compact : VisualDensity.standard,
      navigationRailTheme: const NavigationRailThemeData(
        groupAlignment: -0.92,
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(config.radius)),
        color: Colors.white,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(config.radius)),
      ),
    );
  }

  static ThemeData buildDark(EnterpriseThemeConfig config) {
    final scheme = ColorScheme.fromSeed(seedColor: config.primary, brightness: Brightness.dark);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme.copyWith(secondary: config.secondary),
      scaffoldBackgroundColor: config.darkSurface,
      visualDensity: config.density == 'compact' ? VisualDensity.compact : VisualDensity.standard,
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(config.radius)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(config.radius)),
      ),
    );
  }
}
