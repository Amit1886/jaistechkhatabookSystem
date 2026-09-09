import 'package:flutter_offline_billing_app/models/command_center_models.dart';

class CommandCenterService {
  Future<List<CommandCenterAction>> fetchActions() async {
    await Future.delayed(const Duration(milliseconds: 200));
    return [
      CommandCenterAction(
        id: 'sales',
        label: 'New Sale',
        route: '/sales/new',
      ),
      CommandCenterAction(
        id: 'reports',
        label: 'View Reports',
        route: '/reports',
      ),
      CommandCenterAction(
        id: 'inventory',
        label: 'Inventory',
        route: '/inventory',
      ),
    ];
  }

  Future<CommandCenterResult> execute(CommandCenterAction action) async {
    await Future.delayed(const Duration(milliseconds: 300));
    return CommandCenterResult(
      success: true,
      message: 'Executed ${action.label}',
    );
  }
}
