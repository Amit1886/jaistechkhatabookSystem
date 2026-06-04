import 'package:flutter/foundation.dart';

import '../models/module.dart';
import '../services/api_client.dart';

class ErpProvider extends ChangeNotifier {
  ErpProvider(this.api);

  final ApiClient api;
  bool loading = false;
  bool darkMode = false;
  Map<String, dynamic> dashboard = {};
  Map<String, dynamic> theme = {};
  List<ErpModule> modules = [];
  String? error;

  void toggleTheme() {
    darkMode = !darkMode;
    notifyListeners();
  }

  Future<void> bootstrap() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final boot = await api.get('/api/app/bootstrap/');
      theme = Map<String, dynamic>.from(boot['theme'] ?? {});
      modules = (boot['modules'] as List? ?? []).map((e) => ErpModule.fromJson(Map<String, dynamic>.from(e))).toList();
      dashboard = Map<String, dynamic>.from(await api.get('/api/dashboard/'));
    } catch (e) {
      error = '$e';
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<bool> login(String email, String password) async {
    final ok = await api.login(email, password);
    if (ok) await bootstrap();
    return ok;
  }
}
