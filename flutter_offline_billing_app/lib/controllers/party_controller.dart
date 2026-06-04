import 'package:get/get.dart';

import '../models/party_model.dart';
import '../services/party_service.dart';
import '../services/settings_service.dart';

class PartyController extends GetxController {
  PartyController({
    required PartyService parties,
    required SettingsService settings,
  })  : _parties = parties,
        _settings = settings;

  final PartyService _parties;
  final SettingsService _settings;

  final RxList<PartyModel> items = <PartyModel>[].obs;
  final RxBool isLoading = false.obs;
  final RxString error = ''.obs;

  Future<void> load({String? type, String? query}) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    isLoading.value = true;
    error.value = '';
    try {
      items.value = await _parties.list(businessId: businessId, type: type, query: query);
    } catch (e) {
      error.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }

  Future<void> add({
    required String type,
    required String name,
    String? phone,
    String? address,
  }) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    await _parties.create(businessId: businessId, type: type, name: name, phone: phone, address: address);
    await load(type: type);
  }

  Future<void> remove(String partyId, {String? type}) async {
    await _parties.delete(partyId: partyId);
    await load(type: type);
  }
}

