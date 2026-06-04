import 'package:get/get.dart';

import '../models/transaction_model.dart';
import '../services/settings_service.dart';
import '../services/transaction_service.dart';

class TransactionController extends GetxController {
  TransactionController({
    required TransactionService transactions,
    required SettingsService settings,
  })  : _transactions = transactions,
        _settings = settings;

  final TransactionService _transactions;
  final SettingsService _settings;

  final RxList<TransactionModel> items = <TransactionModel>[].obs;
  final RxBool isLoading = false.obs;
  final RxString error = ''.obs;

  Future<void> load({String? type}) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    isLoading.value = true;
    error.value = '';
    try {
      items.value = await _transactions.list(businessId: businessId, type: type);
    } catch (e) {
      error.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }

  Future<void> add({
    required String type,
    required double amount,
    required String mode,
    String? partyId,
    String? reference,
    String? notes,
  }) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    await _transactions.create(
      businessId: businessId,
      type: type,
      amount: amount,
      mode: mode,
      partyId: partyId,
      reference: reference,
      notes: notes,
    );
    await load(type: type);
  }
}

