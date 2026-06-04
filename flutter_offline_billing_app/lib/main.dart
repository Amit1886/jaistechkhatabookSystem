import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:get/get.dart';

import 'core/bindings/app_binding.dart';
import 'core/theme/app_theme.dart';
import 'database/local_db.dart';
import 'dynamic_platform/dynamic_runtime_service.dart';
import 'screens/root_screen.dart';
import 'screens/settings/settings_screen.dart';
import 'services/api_service.dart';
import 'services/auth_service.dart';
import 'services/enterprise_app_service.dart';
import 'services/enterprise_live_service.dart';
import 'services/expense_service.dart';
import 'services/invoice_service.dart';
import 'services/party_service.dart';
import 'services/product_service.dart';
import 'services/report_service.dart';
import 'services/secure_storage_service.dart';
import 'services/settings_service.dart';
import 'services/sync_service.dart';
import 'services/transaction_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  ErrorWidget.builder = (details) {
    return Material(
      color: const Color(0xFF080F0E),
      child: Center(
        child: Container(
          margin: const EdgeInsets.all(20),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFF3F1212),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFFB7185)),
          ),
          child: SingleChildScrollView(
            child: Text(
              details.exceptionAsString(),
              style: const TextStyle(color: Colors.white),
            ),
          ),
        ),
      ),
    );
  };

  final db = LocalDb.instance;
  if (!kIsWeb) {
    await db.database;
  }

  final settings = SettingsService();
  await settings.init();

  final secure = SecureStorageService();
  final api = ApiService(settings: settings, secure: secure);

  // Services
  Get.put<LocalDb>(db, permanent: true);
  Get.put<SettingsService>(settings, permanent: true);
  Get.put<SecureStorageService>(secure, permanent: true);
  Get.put<ApiService>(api, permanent: true);
  Get.put<EnterpriseAppService>(EnterpriseAppService(api: api),
      permanent: true);
  Get.put<EnterpriseLiveService>(EnterpriseLiveService(api: api),
      permanent: true);
  Get.put<DynamicRuntimeService>(DynamicRuntimeService(api: api),
      permanent: true);

  Get.put<AuthService>(
    AuthService(db: db, api: api, secureStorage: secure, settings: settings),
    permanent: true,
  );
  Get.put<PartyService>(PartyService(db, api: api), permanent: true);
  Get.put<ProductService>(ProductService(db, api: api), permanent: true);
  Get.put<InvoiceService>(InvoiceService(db, api: api), permanent: true);
  Get.put<TransactionService>(TransactionService(db), permanent: true);
  Get.put<ExpenseService>(ExpenseService(db), permanent: true);
  Get.put<ReportService>(ReportService(db), permanent: true);
  Get.put<SyncService>(
    SyncService(db: db, api: api, secureStorage: secure, settings: settings),
    permanent: true,
  );

  runApp(const JaisTechBillingApp());
}

class JaisTechBillingApp extends StatelessWidget {
  const JaisTechBillingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return GetMaterialApp(
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.dark,
      initialBinding: AppBinding(),
      home: const RootScreen(),
      getPages: [
        GetPage(name: '/SettingsScreen', page: () => const SettingsScreen()),
        GetPage(name: '/settings', page: () => const SettingsScreen()),
      ],
      unknownRoute: GetPage(name: '/not-found', page: () => const RootScreen()),
    );
  }
}
