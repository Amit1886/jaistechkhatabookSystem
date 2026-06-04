import 'package:get/get.dart';

import '../models/product_model.dart';
import '../services/product_service.dart';
import '../services/settings_service.dart';

class ProductController extends GetxController {
  ProductController({
    required ProductService products,
    required SettingsService settings,
  })  : _products = products,
        _settings = settings;

  final ProductService _products;
  final SettingsService _settings;

  final RxList<ProductModel> items = <ProductModel>[].obs;
  final RxBool isLoading = false.obs;
  final RxString error = ''.obs;

  Future<void> load({String? query}) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    isLoading.value = true;
    error.value = '';
    try {
      items.value = await _products.list(businessId: businessId, query: query);
    } catch (e) {
      error.value = e.toString();
    } finally {
      isLoading.value = false;
    }
  }

  Future<void> add({
    required String name,
    String? sku,
    String? barcode,
    double salePrice = 0,
    double taxPercent = 0,
  }) async {
    final businessId = _settings.selectedBusinessId.trim();
    if (businessId.isEmpty) return;
    await _products.create(
      businessId: businessId,
      name: name,
      sku: sku,
      barcode: barcode,
      salePrice: salePrice,
      taxPercent: taxPercent,
    );
    await load();
  }

  Future<void> remove(String productId) async {
    await _products.delete(productId: productId);
    await load();
  }
}

