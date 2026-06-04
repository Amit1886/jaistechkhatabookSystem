class ErpModule {
  final String key;
  final String name;
  final String icon;
  final String color;
  final String apiBase;
  final String appRoute;

  ErpModule({
    required this.key,
    required this.name,
    required this.icon,
    required this.color,
    required this.apiBase,
    required this.appRoute,
  });

  factory ErpModule.fromJson(Map<String, dynamic> json) {
    return ErpModule(
      key: '${json['key'] ?? ''}',
      name: '${json['name'] ?? ''}',
      icon: '${json['icon'] ?? 'apps'}',
      color: '${json['color'] ?? '#2563EB'}',
      apiBase: '${json['api_base'] ?? '/api/${json['key']}/'}',
      appRoute: '${json['app_route'] ?? '/module/${json['key']}'}',
    );
  }
}

