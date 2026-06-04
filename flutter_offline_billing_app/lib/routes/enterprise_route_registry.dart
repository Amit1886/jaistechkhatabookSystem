import '../models/enterprise_app_config.dart';
import '../permissions/permission_engine.dart';

class EnterpriseRouteRegistry {
  const EnterpriseRouteRegistry({
    required this.modules,
    required this.permissionEngine,
  });

  final List<EnterpriseModule> modules;
  final PermissionEngine permissionEngine;

  List<EnterpriseModule> get allowedRoutes {
    return modules.where(permissionEngine.canOpen).toList()
      ..sort((a, b) => a.order.compareTo(b.order));
  }

  EnterpriseModule? match(String route) {
    for (final module in allowedRoutes) {
      if (module.route == route || module.key == route) return module;
    }
    return allowedRoutes.isEmpty ? null : allowedRoutes.first;
  }
}
