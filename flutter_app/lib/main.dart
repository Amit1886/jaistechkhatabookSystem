import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'providers/erp_provider.dart';
import 'services/api_client.dart';
import 'theme/app_theme.dart';
import 'modules/login_page.dart';
import 'modules/shell_page.dart';

void main() {
  runApp(
    ChangeNotifierProvider(
      create: (_) => ErpProvider(ApiClient()),
      child: const JaisTechErpApp(),
    ),
  );
}

class JaisTechErpApp extends StatelessWidget {
  const JaisTechErpApp({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<ErpProvider>(
      builder: (context, erp, _) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          title: 'JaisTech ERP',
          theme: AppTheme.light(erp.theme),
          darkTheme: AppTheme.dark(erp.theme),
          themeMode: erp.darkMode ? ThemeMode.dark : ThemeMode.light,
          home: erp.modules.isEmpty ? const LoginPage() : const ShellPage(),
        );
      },
    );
  }
}

