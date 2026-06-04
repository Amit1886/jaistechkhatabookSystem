import '../models/enterprise_app_config.dart';

enum PermissionAction {
  view,
  create,
  edit,
  delete,
  export,
  print,
  approve,
  manage,
}

class PermissionEngine {
  const PermissionEngine(this.permissions);

  final Map<String, PermissionSet> permissions;

  bool can(String permission, PermissionAction action) {
    final set = permissions[permission];
    if (set == null) return false;
    return switch (action) {
      PermissionAction.view => set.canView,
      PermissionAction.create => set.canCreate,
      PermissionAction.edit => set.canEdit,
      PermissionAction.delete => set.canDelete,
      PermissionAction.export => set.canExport,
      PermissionAction.print => set.canPrint,
      PermissionAction.approve => set.canApprove,
      PermissionAction.manage => set.canManage,
    };
  }

  bool canOpen(EnterpriseModule module) {
    return module.enabled && module.visible && can(module.permission, PermissionAction.view);
  }
}
