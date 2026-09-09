class CommandCenterAction {
  final String id;
  final String label;
  final String route;
  final Map<String, dynamic>? params;

  CommandCenterAction({
    required this.id,
    required this.label,
    required this.route,
    this.params,
  });

  factory CommandCenterAction.fromJson(Map<String, dynamic> json) {
    return CommandCenterAction(
      id: json['id'] as String,
      label: json['label'] as String,
      route: json['route'] as String,
      params: json['params'] as Map<String, dynamic>?,
    );
  }
}

class CommandCenterResult {
  final bool success;
  final String? message;
  final dynamic data;

  CommandCenterResult({required this.success, this.message, this.data});
}
