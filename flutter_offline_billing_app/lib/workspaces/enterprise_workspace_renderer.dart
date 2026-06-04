import 'package:flutter/material.dart';

import '../models/enterprise_app_config.dart';
import '../modules/dynamic/dynamic_module_screen.dart';
import '../modules/super_app/super_app_workspaces.dart';
import '../permissions/permission_engine.dart';
import '../dashboard/enterprise_dashboard_screen.dart';
import '../screens/invoices/invoice_list_screen.dart';
import '../screens/parties/party_list_screen.dart';
import '../screens/products/product_list_screen.dart';

class EnterpriseWorkspaceRenderer extends StatelessWidget {
  const EnterpriseWorkspaceRenderer({
    super.key,
    required this.config,
    required this.module,
    required this.permissionEngine,
  });

  final EnterpriseAppConfig config;
  final EnterpriseModule module;
  final PermissionEngine permissionEngine;

  @override
  Widget build(BuildContext context) {
    if (module.key == 'dashboard') {
      return EnterpriseDashboardScreen(
        config: config,
        permissionEngine: permissionEngine,
      );
    }
    if ({'products', 'inventory'}.contains(module.key)) {
      return const ProductListScreen();
    }
    if ({'crm', 'customers', 'suppliers', 'parties'}.contains(module.key)) {
      return const PartyListScreen();
    }
    if ({'billing', 'invoices', 'sales'}.contains(module.key)) {
      return const InvoiceListScreen();
    }
    final runtimeMode = (module.settings['mode'] ?? '').toString();
    final modelKey =
        (module.settings['model_key'] ?? module.settings['model'] ?? '')
            .toString();
    if (runtimeMode == 'dynamic' || modelKey.isNotEmpty) {
      return DynamicModuleScreen(
        module: module,
        permissionEngine: permissionEngine,
        workspace: config.workspace,
      );
    }
    return SuperAppModuleWorkspace(
      module: module,
      permissionEngine: permissionEngine,
      workspace: config.workspace,
    );
  }
}
