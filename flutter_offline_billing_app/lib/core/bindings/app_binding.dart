import 'package:get/get.dart';

import '../../controllers/auth_controller.dart';
import '../../controllers/dashboard_controller.dart';
import '../../controllers/enterprise_app_controller.dart';
import '../../controllers/expense_controller.dart';
import '../../controllers/invoice_controller.dart';
import '../../controllers/party_controller.dart';
import '../../controllers/product_controller.dart';
import '../../controllers/settings_controller.dart';
import '../../controllers/sync_controller.dart';
import '../../controllers/transaction_controller.dart';
import '../../services/auth_service.dart';
import '../../services/enterprise_app_service.dart';
import '../../services/expense_service.dart';
import '../../services/invoice_service.dart';
import '../../services/party_service.dart';
import '../../services/product_service.dart';
import '../../services/report_service.dart';
import '../../services/settings_service.dart';
import '../../services/sync_service.dart';
import '../../services/transaction_service.dart';

class AppBinding extends Bindings {
  @override
  void dependencies() {
    Get.put(SettingsController(Get.find<SettingsService>()), permanent: true);
    Get.put(SyncController(Get.find<SyncService>()), permanent: true);
    Get.put(
      AuthController(auth: Get.find<AuthService>(), sync: Get.find<SyncService>()),
      permanent: true,
    );
    Get.put(
      EnterpriseAppController(service: Get.find<EnterpriseAppService>()),
      permanent: true,
    );

    Get.put(
      DashboardController(reports: Get.find<ReportService>(), settings: Get.find<SettingsService>()),
      permanent: true,
    );
    Get.put(
      PartyController(parties: Get.find<PartyService>(), settings: Get.find<SettingsService>()),
      permanent: true,
    );
    Get.put(
      ProductController(products: Get.find<ProductService>(), settings: Get.find<SettingsService>()),
      permanent: true,
    );
    Get.put(
      InvoiceController(invoices: Get.find<InvoiceService>(), settings: Get.find<SettingsService>()),
      permanent: true,
    );
    Get.put(
      ExpenseController(expenses: Get.find<ExpenseService>(), settings: Get.find<SettingsService>()),
      permanent: true,
    );
    Get.put(
      TransactionController(
        transactions: Get.find<TransactionService>(),
        settings: Get.find<SettingsService>(),
      ),
      permanent: true,
    );
  }
}
