import 'package:get/get.dart';

import '../services/settings_service.dart';

class SettingsController extends GetxController {
  SettingsController(this._settings);

  final SettingsService _settings;

  final RxString apiBaseUrl = ''.obs;
  final RxString syncToken = ''.obs;

  @override
  void onInit() {
    super.onInit();
    apiBaseUrl.value = _settings.apiBaseUrl;
    syncToken.value = _settings.syncToken;
  }

  Future<void> save({
    required String baseUrl,
    required String token,
  }) async {
    await _settings.setApiBaseUrl(baseUrl);
    await _settings.setSyncToken(token);
    apiBaseUrl.value = _settings.apiBaseUrl;
    syncToken.value = _settings.syncToken;
  }
}

