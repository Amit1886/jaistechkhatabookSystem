import 'package:get/get.dart';

import '../models/expense_model.dart';
import '../services/expense_service.dart';
import '../services/settings_service.dart';

class ExpenseController extends GetxController {
  ExpenseController({
    required ExpenseService expenses,
    required SettingsService settings,
  })  : _expenses = expenses,
        _settings = settings;

  final ExpenseService _expenses;
  final SettingsService _settings;

  final RxList<ExpenseModel> items = <ExpenseModel>[].obs;
  final RxBool isLoading = false.obs;
  final RxString error = ''.obs;

  Future<void> load() async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    isLoading.value = true;
    error.value = '';
    try {
      items.value = await _expenses.list(businessId: businessId);
    } catch (e) {
      error.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }

  Future<void> add({
    required double amount,
    required DateTime date,
    String? category,
    String? notes,
  }) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    await _expenses.create(businessId: businessId, amount: amount, date: date, category: category, notes: notes);
    await load();
  }

  Future<void> remove(String expenseId) async {
    await _expenses.delete(expenseId);
    await load();
  }
}

