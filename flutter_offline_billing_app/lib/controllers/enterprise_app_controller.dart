import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../models/enterprise_app_config.dart';
import '../services/enterprise_app_service.dart';

class EnterpriseAppController extends GetxController {
  EnterpriseAppController({required EnterpriseAppService service}) : _service = service;

  final EnterpriseAppService _service;

  final Rxn<EnterpriseAppConfig> config = Rxn<EnterpriseAppConfig>();
  final RxBool isLoading = true.obs;
  final RxString selectedModuleKey = 'dashboard'.obs;
  final RxString selectedMode = 'desktop'.obs;
  
  final RxString activeProfile = 'Enterprise ERP'.obs;

  final List<String> profiles = const [
    'Enterprise ERP',
    'Retail Billing',
    'E-Commerce Hub',
    'AI Business Copilot',
  ];

  Color get profileColor {
    switch (activeProfile.value) {
      case 'Retail Billing':
        return const Color(0xFF10B981);
      case 'E-Commerce Hub':
        return const Color(0xFFF43F5E);
      case 'AI Business Copilot':
        return const Color(0xFFF59E0B);
      default:
        return const Color(0xFF6366F1);
    }
  }

  bool isModuleHighlighted(String moduleKey) {
    final highlighted = switch (activeProfile.value) {
      'Retail Billing' => const ['pos', 'billing', 'selfcheckout', 'products', 'inventory'],
      'E-Commerce Hub' => const ['ecommerce', 'website', 'products', 'suppliers', 'purchases'],
      'AI Business Copilot' => const ['dashboard', 'reports'],
      _ => const ['dashboard', 'company', 'ledger', 'crm', 'hrm', 'reports', 'settings'],
    };
    return highlighted.contains(moduleKey);
  }

  void switchProfile(String profile) {
    if (profiles.contains(profile)) {
      activeProfile.value = profile;
    }
  }

  @override
  void onInit() {
    super.onInit();
    refreshConfig();
  }

  Future<void> refreshConfig({String? mode}) async {
    isLoading.value = true;
    try {
      if (mode != null) selectedMode.value = mode;
      final next = await _service.bootstrap(mode: selectedMode.value);
      config.value = next;
      selectedMode.value = next.defaultMode;
      final modules = next.visibleModules;
      final hasDashboard = modules.any((m) => m.key == 'dashboard');
      if (hasDashboard && selectedModuleKey.value == 'settings') {
        selectedModuleKey.value = 'dashboard';
      } else if (modules.isNotEmpty && modules.every((m) => m.key != selectedModuleKey.value)) {
        selectedModuleKey.value = hasDashboard ? 'dashboard' : modules.first.key;
      }
    } finally {
      isLoading.value = false;
    }
  }

  EnterpriseModule? get selectedModule {
    final current = config.value;
    if (current == null) return null;
    for (final module in current.visibleModules) {
      if (module.key == selectedModuleKey.value) return module;
    }
    return current.visibleModules.isNotEmpty ? current.visibleModules.first : null;
  }

  void selectModule(EnterpriseModule module) {
    selectedModuleKey.value = module.key;
  }
}
