import 'package:get/get.dart';

import '../services/report_service.dart';
import '../services/settings_service.dart';

class DashboardController extends GetxController {
  DashboardController({
    required ReportService reports,
    required SettingsService settings,
  })  : _reports = reports,
        _settings = settings;

  final ReportService _reports;
  final SettingsService _settings;

  final Rxn<DashboardSummary> summary = Rxn<DashboardSummary>();
  final RxBool isLoading = false.obs;
  final RxString error = ''.obs;

  Future<void> load() async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    isLoading.value = true;
    error.value = '';
    try {
      summary.value = await _reports.dashboardSummary(businessId: businessId);
    } catch (e) {
      error.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }
}

