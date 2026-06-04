import 'package:flutter/material.dart';

class EnterpriseAppConfig {
  const EnterpriseAppConfig({
    required this.version,
    required this.theme,
    required this.workspace,
    required this.modes,
    required this.defaultMode,
    required this.modules,
    required this.menu,
    required this.sidebar,
    required this.launcher,
    required this.buttons,
    required this.widgets,
    required this.permissions,
    required this.api,
    required this.features,
    required this.realtime,
    required this.liveData,
    required this.dashboardConfig,
  });

  final String version;
  final EnterpriseThemeConfig theme;
  final EnterpriseWorkspace workspace;
  final List<String> modes;
  final String defaultMode;
  final List<EnterpriseModule> modules;
  final List<EnterpriseMenuItem> menu;
  final List<EnterpriseMenuItem> sidebar;
  final List<EnterpriseLauncherItem> launcher;
  final List<EnterpriseActionButton> buttons;
  final List<DashboardWidgetConfig> widgets;
  final Map<String, PermissionSet> permissions;
  final Map<String, String> api;
  final Map<String, bool> features;
  final Map<String, String> realtime;
  final Map<String, dynamic> liveData;
  final Map<String, dynamic> dashboardConfig;

  List<EnterpriseModule> get visibleModules =>
      modules.where((module) => module.visible && module.enabled).toList()
        ..sort((a, b) => a.order.compareTo(b.order));

  factory EnterpriseAppConfig.fromJson(Map<String, dynamic> json) {
    final normalized = _normalizeConfig(json);
    final modules = _list(normalized['modules'])
        .map((e) => EnterpriseModule.fromJson(_map(e)))
        .toList();
    final menu = _list(normalized['menu']).isEmpty
        ? modules
            .map((m) => EnterpriseMenuItem(
                  key: m.key,
                  title: m.title,
                  icon: m.icon,
                  route: m.route,
                  color: m.color,
                ))
            .toList()
        : _list(normalized['menu'])
            .map((e) => EnterpriseMenuItem.fromJson(_map(e)))
            .toList();

    return EnterpriseAppConfig(
      version: (normalized['version'] ?? '').toString(),
      theme: EnterpriseThemeConfig.fromJson(_map(normalized['theme'])),
      workspace: EnterpriseWorkspace.fromJson(_map(normalized['workspace'])),
      modes: _list(normalized['modes']).map((e) => e.toString()).toList(),
      defaultMode:
          (normalized['default_mode'] ?? normalized['platform'] ?? 'desktop')
              .toString(),
      modules: modules,
      menu: menu,
      sidebar: _list(normalized['sidebar'])
          .map((e) => EnterpriseMenuItem.fromJson(_map(e)))
          .toList(),
      launcher: _list(normalized['launcher'])
          .map((e) => EnterpriseLauncherItem.fromJson(_map(e)))
          .toList(),
      buttons: _list(normalized['buttons'])
          .map((e) => EnterpriseActionButton.fromJson(_map(e)))
          .toList(),
      widgets: _list(normalized['widgets'])
          .map((e) => DashboardWidgetConfig.fromJson(_map(e)))
          .toList(),
      permissions: _parsePermissions(_map(normalized['permissions'])),
      api: _map(normalized['api'])
          .map((key, value) => MapEntry(key, value.toString())),
      features: _map(normalized['features'])
          .map((key, value) => MapEntry(key, value == true)),
      realtime: _map(normalized['realtime'])
          .map((key, value) => MapEntry(key, value.toString())),
      liveData: _map(normalized['live_data']),
      dashboardConfig: _map(normalized['dashboard_config']),
    );
  }

  factory EnterpriseAppConfig.fallback() {
    const modules = <EnterpriseModule>[
      EnterpriseModule(
        key: 'dashboard',
        title: 'Command Center',
        icon: 'dashboard',
        route: '/dashboard',
        webUrl: '/accounts/dashboard/',
        permission: 'dashboard',
        color: Color(0xFF14B8A6),
        mode: 'analytics',
        visible: true,
        enabled: true,
        order: 1,
      ),
      EnterpriseModule(
        key: 'pos',
        title: 'POS',
        icon: 'point_of_sale',
        route: '/pos',
        webUrl: '/pos/ui/',
        permission: 'pos',
        color: Color(0xFF2563EB),
        mode: 'billing',
        visible: true,
        enabled: true,
        order: 2,
      ),
      EnterpriseModule(
        key: 'company',
        title: 'Company',
        icon: 'account_balance',
        route: '/company',
        webUrl: '/accounts/company/',
        permission: 'company',
        color: Color(0xFF5EEAD4),
        mode: 'organization',
        visible: true,
        enabled: true,
        order: 3,
      ),
      EnterpriseModule(
        key: 'ledger',
        title: 'Accounting',
        icon: 'account_tree',
        route: '/ledger',
        webUrl: '/ledger/',
        permission: 'ledger',
        color: Color(0xFF34D399),
        mode: 'accounting',
        visible: true,
        enabled: true,
        order: 4,
      ),
      EnterpriseModule(
        key: 'products',
        title: 'Products',
        icon: 'category',
        route: '/products',
        webUrl: '/commerce/products/',
        permission: 'products',
        color: Color(0xFF22D3EE),
        mode: 'catalog',
        visible: true,
        enabled: true,
        order: 5,
      ),
      EnterpriseModule(
        key: 'website',
        title: 'Website',
        icon: 'language',
        route: '/website',
        webUrl: '/website/',
        permission: 'website',
        color: Color(0xFFA78BFA),
        mode: 'content',
        visible: true,
        enabled: true,
        order: 6,
      ),
      EnterpriseModule(
        key: 'selfcheckout',
        title: 'Self Checkout',
        icon: 'scan-line',
        route: '/self-checkout',
        webUrl: '/pos/self-checkout/',
        permission: 'selfcheckout',
        color: Color(0xFF7C3AED),
        mode: 'kiosk',
        visible: true,
        enabled: true,
        order: 7,
      ),
      EnterpriseModule(
        key: 'inventory',
        title: 'Inventory',
        icon: 'inventory_2',
        route: '/inventory',
        webUrl: '/commerce/products/',
        permission: 'inventory',
        color: Color(0xFFF59E0B),
        mode: 'inventory',
        visible: true,
        enabled: true,
        order: 8,
      ),
      EnterpriseModule(
        key: 'billing',
        title: 'Billing',
        icon: 'receipt_long',
        route: '/billing',
        webUrl: '/billing/',
        permission: 'billing',
        color: Color(0xFF10B981),
        mode: 'billing',
        visible: true,
        enabled: true,
        order: 9,
      ),
      EnterpriseModule(
        key: 'sales',
        title: 'Sales',
        icon: 'shopping_cart_checkout',
        route: '/sales',
        webUrl: '/commerce/sales/',
        permission: 'sales',
        color: Color(0xFF2DD4BF),
        mode: 'sales',
        visible: true,
        enabled: true,
        order: 10,
      ),
      EnterpriseModule(
        key: 'crm',
        title: 'CRM',
        icon: 'groups',
        route: '/crm',
        webUrl: '/api/v1/crm/',
        permission: 'crm',
        color: Color(0xFF0EA5E9),
        mode: 'relationship',
        visible: true,
        enabled: true,
        order: 11,
      ),
      EnterpriseModule(
        key: 'ecommerce',
        title: 'Ecommerce',
        icon: 'store',
        route: '/store',
        webUrl: '/store/',
        permission: 'ecommerce',
        color: Color(0xFFEC4899),
        mode: 'commerce',
        visible: true,
        enabled: true,
        order: 12,
      ),
      EnterpriseModule(
        key: 'b2b',
        title: 'B2B Portal',
        icon: 'business_center',
        route: '/b2b',
        webUrl: '/portal/b2b/',
        permission: 'b2b',
        color: Color(0xFF2563EB),
        mode: 'commerce',
        visible: true,
        enabled: true,
        order: 13,
      ),
      EnterpriseModule(
        key: 'b2c',
        title: 'B2C',
        icon: 'store',
        route: '/b2c',
        webUrl: '/store/',
        permission: 'b2c',
        color: Color(0xFFF43F5E),
        mode: 'commerce',
        visible: true,
        enabled: true,
        order: 14,
      ),
      EnterpriseModule(
        key: 'suppliers',
        title: 'Vendor Portal',
        icon: 'local_shipping',
        route: '/suppliers',
        webUrl: '/portal/',
        permission: 'suppliers',
        color: Color(0xFF64748B),
        mode: 'supply',
        visible: true,
        enabled: true,
        order: 15,
      ),
      EnterpriseModule(
        key: 'hrm',
        title: 'HRM',
        icon: 'badge',
        route: '/hrm',
        webUrl: '/users/',
        permission: 'hrm',
        color: Color(0xFFF472B6),
        mode: 'people',
        visible: true,
        enabled: true,
        order: 16,
      ),
      EnterpriseModule(
        key: 'purchases',
        title: 'Purchases',
        icon: 'shopping_cart',
        route: '/purchases',
        webUrl: '/procurement/',
        permission: 'purchases',
        color: Color(0xFFFB7185),
        mode: 'procurement',
        visible: true,
        enabled: true,
        order: 17,
      ),
      EnterpriseModule(
        key: 'reports',
        title: 'Reports',
        icon: 'bar_chart',
        route: '/reports',
        webUrl: '/reports/',
        permission: 'reports',
        color: Color(0xFFEF4444),
        mode: 'analytics',
        visible: true,
        enabled: true,
        order: 18,
      ),
      EnterpriseModule(
        key: 'admin_panel',
        title: 'Admin Builder',
        icon: 'admin_panel_settings',
        route: '/admin-builder',
        webUrl: '/admin/',
        permission: 'admin_panel',
        color: Color(0xFFA78BFA),
        mode: 'control',
        visible: true,
        enabled: true,
        order: 19,
      ),
      EnterpriseModule(
        key: 'api_management',
        title: 'API Management',
        icon: 'api',
        route: '/api-management',
        webUrl: '/api/enterprise/',
        permission: 'api_management',
        color: Color(0xFF06B6D4),
        mode: 'control',
        visible: true,
        enabled: true,
        order: 20,
      ),
      EnterpriseModule(
        key: 'customer_app',
        title: 'Customer App',
        icon: 'person',
        route: '/customer-app',
        webUrl: '/portal/customer/',
        permission: 'customer_app',
        color: Color(0xFFFB7185),
        mode: 'portal',
        visible: true,
        enabled: true,
        order: 21,
      ),
      EnterpriseModule(
        key: 'delivery_app',
        title: 'Delivery App',
        icon: 'delivery_dining',
        route: '/delivery-app',
        webUrl: '/portal/delivery/',
        permission: 'delivery_app',
        color: Color(0xFF22C55E),
        mode: 'portal',
        visible: true,
        enabled: true,
        order: 22,
      ),
      EnterpriseModule(
        key: 'apk_builder',
        title: 'APK Builder',
        icon: 'android',
        route: '/apk-builder',
        webUrl: '/distribution/',
        permission: 'apk_builder',
        color: Color(0xFF84CC16),
        mode: 'distribution',
        visible: true,
        enabled: true,
        order: 23,
      ),
      EnterpriseModule(
        key: 'settings',
        title: 'Settings',
        icon: 'settings',
        route: '/settings',
        webUrl: '/admin/',
        permission: 'settings',
        color: Color(0xFF94A3B8),
        mode: 'control',
        visible: true,
        enabled: true,
        order: 24,
      ),
    ];
    return EnterpriseAppConfig(
      version: 'offline-fallback',
      theme: const EnterpriseThemeConfig(
        brandName: 'JAISTECH',
        logoUrl: '',
        primary: Color(0xFF5B21B6),
        secondary: Color(0xFF7C3AED),
        accent: Color(0xFF00A884),
        surface: Color(0xFFF8FAFC),
        darkSurface: Color(0xFF0B1120),
        radius: 8,
        density: 'comfortable',
        animation: 'smooth',
      ),
      workspace: const EnterpriseWorkspace(
        key: 'offline_workspace',
        name: 'Offline Enterprise Workspace',
        landingRoute: '/dashboard',
        layout: {'density': 'comfortable', 'columns': 12},
      ),
      modes: const [
        'mobile',
        'tablet',
        'desktop',
        'pos',
        'self_checkout',
        'kiosk',
        'landscape',
        'touch',
      ],
      defaultMode: 'desktop',
      modules: modules,
      menu: modules
          .map((m) => EnterpriseMenuItem(
                key: m.key,
                title: m.title,
                icon: m.icon,
                route: m.route,
                color: m.color,
              ))
          .toList(),
      sidebar: modules
          .map((m) => EnterpriseMenuItem(
                key: m.key,
                title: m.title,
                icon: m.icon,
                route: m.route,
                color: m.color,
              ))
          .toList(),
      launcher: modules
          .map((m) => EnterpriseLauncherItem(
                key: m.key,
                title: m.title,
                icon: m.icon,
                route: m.route,
                color: m.color,
                order: m.order,
              ))
          .toList(),
      buttons: modules
          .take(8)
          .map((m) => EnterpriseActionButton(
                key: m.key,
                label: m.title,
                module: m.key,
                actionType: 'module',
                route: m.route,
                icon: m.icon,
                color: m.color,
                gradient: [m.color, const Color(0xFF0B1120)],
                shape: 'rounded',
                animation: 'smooth',
                primary: m.order <= 4,
                order: m.order,
              ))
          .toList(),
      widgets: const [
        DashboardWidgetConfig(
          key: 'sales_today',
          title: 'Live Sales',
          type: 'metric',
          permission: 'dashboard',
          value: 'Offline ready',
          accent: Color(0xFF14B8A6),
        ),
        DashboardWidgetConfig(
          key: 'inventory_status',
          title: 'Inventory Status',
          type: 'status',
          permission: 'inventory',
          value: 'Local cache',
          accent: Color(0xFFF59E0B),
        ),
        DashboardWidgetConfig(
          key: 'ai_copilot',
          title: 'AI Copilot',
          type: 'insight',
          permission: 'dashboard',
          value: 'Ready',
          accent: Color(0xFF7C3AED),
        ),
      ],
      permissions: {
        for (final module in modules)
          module.permission: const PermissionSet.allow()
      },
      api: const {},
      features: const {'offline_mode': true, 'auto_sync': true, 'pwa': true},
      realtime: const {},
      liveData: const {},
      dashboardConfig: const {},
    );
  }
}

class EnterpriseWorkspace {
  const EnterpriseWorkspace({
    required this.key,
    required this.name,
    required this.landingRoute,
    required this.layout,
  });

  final String key;
  final String name;
  final String landingRoute;
  final Map<String, dynamic> layout;

  factory EnterpriseWorkspace.fromJson(Map<String, dynamic> json) {
    return EnterpriseWorkspace(
      key: (json['key'] ?? 'default').toString(),
      name: (json['name'] ?? 'Enterprise Workspace').toString(),
      landingRoute: (json['landing_route'] ?? '/dashboard').toString(),
      layout: _map(json['layout']),
    );
  }
}

class EnterpriseThemeConfig {
  const EnterpriseThemeConfig({
    required this.brandName,
    required this.logoUrl,
    required this.primary,
    required this.secondary,
    required this.accent,
    required this.surface,
    required this.darkSurface,
    required this.radius,
    required this.density,
    required this.animation,
  });

  final String brandName;
  final String logoUrl;
  final Color primary;
  final Color secondary;
  final Color accent;
  final Color surface;
  final Color darkSurface;
  final double radius;
  final String density;
  final String animation;

  factory EnterpriseThemeConfig.fromJson(Map<String, dynamic> json) {
    return EnterpriseThemeConfig(
      brandName: (json['brand_name'] ?? 'JAISTECH').toString(),
      logoUrl: (json['logo_url'] ?? '').toString(),
      primary: _color(json['primary'], const Color(0xFF0F766E)),
      secondary: _color(json['secondary'], const Color(0xFF2563EB)),
      accent: _color(json['accent'], const Color(0xFFF59E0B)),
      surface: _color(json['surface'], const Color(0xFFF8FAFC)),
      darkSurface: _color(json['dark_surface'], const Color(0xFF0B1120)),
      radius: double.tryParse((json['radius'] ?? '8').toString()) ?? 8,
      density: (json['density'] ?? 'comfortable').toString(),
      animation: (json['animation'] ?? 'smooth').toString(),
    );
  }
}

class EnterpriseModule {
  const EnterpriseModule({
    required this.key,
    required this.title,
    required this.icon,
    required this.route,
    required this.webUrl,
    required this.permission,
    required this.color,
    required this.mode,
    required this.visible,
    required this.enabled,
    required this.order,
    this.settings = const {},
  });

  final String key;
  final String title;
  final String icon;
  final String route;
  final String webUrl;
  final String permission;
  final Color color;
  final String mode;
  final bool visible;
  final bool enabled;
  final int order;
  final Map<String, dynamic> settings;

  factory EnterpriseModule.fromJson(Map<String, dynamic> json) {
    final key = (json['key'] ?? '').toString();
    final rawPermission = json['permission'];
    final permission =
        rawPermission is bool ? key : (rawPermission ?? key).toString();
    return EnterpriseModule(
      key: key,
      title: (json['title'] ?? json['name'] ?? '').toString(),
      icon: (json['icon'] ?? 'apps').toString(),
      route: (json['route'] ?? json['app_route'] ?? '/$key').toString(),
      webUrl: (json['web_url'] ?? json['api_base'] ?? '').toString(),
      permission: permission.isEmpty || permission == 'true' ? key : permission,
      color: _color(json['color'], const Color(0xFF0F766E)),
      mode: (json['mode'] ?? json['api_namespace'] ?? '').toString(),
      visible: json['visible'] != false,
      enabled: json['enabled'] != false && json['is_enabled'] != false,
      order: int.tryParse((json['order'] ?? '999').toString()) ?? 999,
      settings: _map(json['settings']),
    );
  }
}

class EnterpriseMenuItem {
  const EnterpriseMenuItem({
    required this.key,
    required this.title,
    required this.icon,
    required this.route,
    required this.color,
    this.badge = '',
    this.order = 999,
    this.isGroup = false,
    this.children = const [],
  });

  final String key;
  final String title;
  final String icon;
  final String route;
  final Color color;
  final String badge;
  final int order;
  final bool isGroup;
  final List<EnterpriseMenuItem> children;

  factory EnterpriseMenuItem.fromJson(Map<String, dynamic> json) {
    return EnterpriseMenuItem(
      key: (json['key'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      icon: (json['icon'] ?? 'apps').toString(),
      route: (json['route'] ?? '/').toString(),
      color: _color(json['color'], const Color(0xFF0F766E)),
      badge: (json['badge'] ?? '').toString(),
      order: int.tryParse((json['order'] ?? '999').toString()) ?? 999,
      isGroup: json['is_group'] == true,
      children: _list(json['children'])
          .map((e) => EnterpriseMenuItem.fromJson(_map(e)))
          .toList(),
    );
  }
}

class EnterpriseLauncherItem {
  const EnterpriseLauncherItem({
    required this.key,
    required this.title,
    required this.icon,
    required this.route,
    required this.color,
    required this.order,
  });

  final String key;
  final String title;
  final String icon;
  final String route;
  final Color color;
  final int order;

  factory EnterpriseLauncherItem.fromJson(Map<String, dynamic> json) {
    return EnterpriseLauncherItem(
      key: (json['key'] ?? '').toString(),
      title: (json['title'] ?? json['label'] ?? '').toString(),
      icon: (json['icon'] ?? 'apps').toString(),
      route: (json['route'] ?? '/').toString(),
      color: _color(json['color'], const Color(0xFF0F766E)),
      order: int.tryParse((json['order'] ?? '999').toString()) ?? 999,
    );
  }
}

class EnterpriseActionButton {
  const EnterpriseActionButton({
    required this.key,
    required this.label,
    required this.module,
    required this.actionType,
    required this.route,
    required this.icon,
    required this.color,
    required this.gradient,
    required this.shape,
    required this.animation,
    required this.primary,
    required this.order,
  });

  final String key;
  final String label;
  final String module;
  final String actionType;
  final String route;
  final String icon;
  final Color color;
  final List<Color> gradient;
  final String shape;
  final String animation;
  final bool primary;
  final int order;

  factory EnterpriseActionButton.fromJson(Map<String, dynamic> json) {
    final color = _color(json['color'], const Color(0xFF0F766E));
    final gradient =
        _list(json['gradient']).map((e) => _color(e, color)).toList();
    return EnterpriseActionButton(
      key: (json['key'] ?? '').toString(),
      label: (json['label'] ?? json['title'] ?? '').toString(),
      module: (json['module'] ?? '').toString(),
      actionType: (json['action_type'] ?? 'route').toString(),
      route: (json['route'] ?? '/').toString(),
      icon: (json['icon'] ?? 'bolt').toString(),
      color: color,
      gradient:
          gradient.isEmpty ? [color, color.withValues(alpha: 0.55)] : gradient,
      shape: (json['shape'] ?? 'rounded').toString(),
      animation: (json['animation'] ?? 'smooth').toString(),
      primary: json['primary'] == true,
      order: int.tryParse((json['order'] ?? '999').toString()) ?? 999,
    );
  }
}

class DashboardWidgetConfig {
  const DashboardWidgetConfig({
    required this.key,
    required this.title,
    required this.type,
    required this.permission,
    required this.value,
    required this.accent,
  });

  final String key;
  final String title;
  final String type;
  final String permission;
  final String value;
  final Color accent;

  factory DashboardWidgetConfig.fromJson(Map<String, dynamic> json) {
    return DashboardWidgetConfig(
      key: (json['key'] ?? '').toString(),
      title: (json['title'] ?? '').toString(),
      type: (json['type'] ?? json['widget_type'] ?? 'metric').toString(),
      permission:
          (json['permission'] ?? json['permission_key'] ?? '').toString(),
      value: (json['value'] ?? json['data_source'] ?? '').toString(),
      accent: _color(json['accent'], const Color(0xFF0F766E)),
    );
  }
}

class PermissionSet {
  const PermissionSet({
    required this.canView,
    required this.canCreate,
    required this.canEdit,
    required this.canDelete,
    required this.canExport,
    required this.canPrint,
    required this.canApprove,
    required this.canManage,
  });

  const PermissionSet.allow()
      : canView = true,
        canCreate = true,
        canEdit = true,
        canDelete = true,
        canExport = true,
        canPrint = true,
        canApprove = true,
        canManage = true;

  final bool canView;
  final bool canCreate;
  final bool canEdit;
  final bool canDelete;
  final bool canExport;
  final bool canPrint;
  final bool canApprove;
  final bool canManage;

  factory PermissionSet.fromJson(Map<String, dynamic> json) {
    if (json.containsKey('view') ||
        json.containsKey('create') ||
        json.containsKey('edit')) {
      return PermissionSet(
        canView: json['view'] == true,
        canCreate: json['create'] == true,
        canEdit: json['edit'] == true,
        canDelete: json['delete'] == true,
        canExport: json['export'] == true,
        canPrint: json['print'] == true,
        canApprove: json['approve'] == true,
        canManage: json.values.any((v) => v == true),
      );
    }
    return PermissionSet(
      canView: json['can_view'] == true,
      canCreate: json['can_create'] == true,
      canEdit: json['can_edit'] == true,
      canDelete: json['can_delete'] == true,
      canExport: json['can_export'] == true,
      canPrint: json['can_print'] == true,
      canApprove: json['can_approve'] == true || json['can_manage'] == true,
      canManage: json['can_manage'] == true,
    );
  }
}

Map<String, dynamic> _normalizeConfig(Map<String, dynamic> json) {
  final result = Map<String, dynamic>.from(json);
  final app = _map(json['app']);
  final theme = _map(json['theme']);
  final ui = _map(json['ui']);
  final menus = _list(json['menus']).isNotEmpty
      ? _list(json['menus'])
      : _list(json['menu']);

  result['version'] ??= 'jaistech-bootstrap';
  result['default_mode'] ??= 'mobile';
  result['modes'] = _list(result['modes']).isEmpty
      ? const ['mobile', 'tablet', 'desktop', 'pos', 'self_checkout', 'kiosk']
      : result['modes'];
  result['workspace'] = {
    'key': 'jaistech_workspace',
    'name': app['display_name'] ?? app['name'] ?? 'JAISTECH',
    'landing_route': '/dashboard',
    'layout': const {'density': 'comfortable', 'columns': 12},
    ..._map(result['workspace']),
  };
  result['theme'] = {
    'brand_name': app['name'] ?? theme['brand_name'] ?? 'JAISTECH',
    'primary': theme['primary'] ?? '#5B21B6',
    'secondary': theme['secondary'] ?? '#7C3AED',
    'accent': theme['accent'] ?? '#00A884',
    'surface': theme['surface'] ?? '#F6F8FB',
    'dark_surface': theme['dark_surface'] ?? '#111827',
    'radius': theme['radius'] ?? 8,
    'density': theme['density'] ?? 'comfortable',
    'animation': theme['animation'] ?? 'smooth',
  };

  if (menus.isNotEmpty) {
    result['menu'] = menus;
    result['sidebar'] =
        _list(result['sidebar']).isEmpty ? menus : result['sidebar'];
    result['launcher'] =
        _list(result['launcher']).isEmpty ? menus : result['launcher'];
  }

  final moduleFlags = _map(ui['modules']);
  final features = {..._map(result['features'])};
  if (moduleFlags.isNotEmpty) {
    features.addAll(moduleFlags);
    features['offline_mode'] = true;
    features['auto_sync'] = true;
    result['features'] = features;
  }

  result['permissions'] = _normalizePermissions(
    rawPermissions: json['permissions'],
    rawActions: ui['actions'],
    modules: _list(json['modules']),
  );
  result['api'] = {
    'django': app['api_base_url'] ?? '',
    'fastapi': app['fastapi_url'] ?? '',
    ..._map(result['api']),
  };
  result['realtime'] = {
    'orders': '/ws/orders/',
    'notifications': '/ws/notifications/',
    ..._map(result['realtime']),
  };
  result['buttons'] = _list(result['buttons']).isEmpty
      ? menus.take(8).map((item) {
          final row = _map(item);
          return {
            'key': row['key'],
            'label': row['title'],
            'module': row['key'],
            'action_type': 'module',
            'route': row['route'],
            'icon': row['icon'],
            'color': row['color'],
            'primary': true,
            'order': row['order'] ?? 999,
          };
        }).toList()
      : result['buttons'];
  return result;
}

Map<String, dynamic> _normalizePermissions({
  required Object? rawPermissions,
  required Object? rawActions,
  required List<dynamic> modules,
}) {
  final normalized = <String, Map<String, bool>>{};
  final actions = _map(rawActions);
  for (final entry in actions.entries) {
    normalized[entry.key] = _actionAliases(_map(entry.value));
  }

  if (rawPermissions is List) {
    for (final item in rawPermissions) {
      final row = _map(item);
      final module = (row['module'] ?? row['module__key'] ?? '').toString();
      final action = (row['action'] ?? '').toString();
      if (module.isEmpty || action.isEmpty) continue;
      normalized.putIfAbsent(module, () => <String, bool>{})[action] = true;
    }
  } else {
    for (final entry in _map(rawPermissions).entries) {
      normalized[entry.key] = _actionAliases(_map(entry.value));
    }
  }

  for (final item in modules) {
    final module = _map(item);
    final key = (module['key'] ?? '').toString();
    if (key.isEmpty) continue;
    normalized.putIfAbsent(key, () => {'view': true});
  }

  return normalized.map((key, value) => MapEntry(key, _actionAliases(value)));
}

Map<String, bool> _actionAliases(Map<String, dynamic> actions) {
  final canView = actions['view'] == true ||
      actions['list'] == true ||
      actions['retrieve'] == true ||
      actions['can_view'] == true;
  final canCreate = actions['create'] == true || actions['can_create'] == true;
  final canEdit = actions['edit'] == true ||
      actions['update'] == true ||
      actions['partial_update'] == true ||
      actions['can_edit'] == true;
  final canDelete = actions['delete'] == true ||
      actions['destroy'] == true ||
      actions['can_delete'] == true;
  final canExport = actions['export'] == true || actions['can_export'] == true;
  final canSync = actions['sync'] == true;
  return {
    ...actions.map((key, value) => MapEntry(key, value == true)),
    'view': canView,
    'create': canCreate,
    'edit': canEdit,
    'delete': canDelete,
    'export': canExport,
    'sync': canSync,
    'print': actions['print'] == true || canExport,
    'approve': actions['approve'] == true,
  };
}

Map<String, PermissionSet> _parsePermissions(Map<String, dynamic> json) {
  final result = <String, PermissionSet>{};
  for (final entry in json.entries) {
    if (entry.key == 'platform') continue;
    result[entry.key] = PermissionSet.fromJson(_map(entry.value));
  }
  return result;
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, value) => MapEntry(key.toString(), value));
  }
  return <String, dynamic>{};
}

List<dynamic> _list(Object? value) => value is List ? value : const [];

Color _color(Object? value, Color fallback) {
  final raw = value?.toString().trim();
  if (raw == null || raw.isEmpty) return fallback;
  final hex = raw.replaceAll('#', '');
  final normalized = hex.length == 6 ? 'FF$hex' : hex;
  return Color(int.tryParse(normalized, radix: 16) ?? fallback.toARGB32());
}
