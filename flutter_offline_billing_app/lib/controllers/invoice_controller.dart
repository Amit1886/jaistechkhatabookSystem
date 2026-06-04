import 'package:get/get.dart';

import '../models/invoice_model.dart';
import '../models/product_model.dart';
import '../services/invoice_service.dart';
import '../services/settings_service.dart';

class InvoiceController extends GetxController {
  InvoiceController({
    required InvoiceService invoices,
    required SettingsService settings,
  })  : _invoices = invoices,
        _settings = settings;

  final InvoiceService _invoices;
  final SettingsService _settings;

  final RxList<InvoiceModel> items = <InvoiceModel>[].obs;
  final RxBool isLoading = false.obs;
  final RxString error = ''.obs;

  Future<void> load() async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    isLoading.value = true;
    error.value = '';
    try {
      items.value = await _invoices.list(businessId: businessId);
    } catch (e) {
      error.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }

  Future<InvoiceModel> create({
    required String partyId,
    required List<InvoiceDraftItem> draftItems,
    double discount = 0,
    double paid = 0,
  }) async {
    final businessId = _settings.selectedBusinessId.trim();
    final invoice = await _invoices.createInvoice(
      businessId: businessId,
      partyId: partyId,
      items: draftItems,
      discount: discount,
      paid: paid,
    );
    await load();
    return invoice;
  }

  InvoiceDraftItem draftItemFromProduct(ProductModel product, double qty) {
    return InvoiceDraftItem(product: product, qty: qty);
  }
}

