import '../database/local_db.dart';
import '../database/tables.dart';
import '../models/product_model.dart';
import 'api_service.dart';
import 'id_service.dart';

class ProductService {
  ProductService(this._db, {ApiService? api}) : _api = api;

  final LocalDb _db;
  final ApiService? _api;

  Future<List<ProductModel>> list({
    required String businessId,
    String? query,
  }) async {
    final api = _api;
    if (api != null) {
      try {
        final res = await api.getJson(
          '/api/app/products/',
          query: query == null || query.trim().isEmpty
              ? null
              : {'q': query.trim()},
        );
        final rows = (res['results'] as List? ?? const [])
            .whereType<Map>()
            .map((row) => ProductModel.fromJson(
                  Map<String, dynamic>.from(row),
                  businessId: businessId,
                ))
            .toList();
        for (final row in rows) {
          await _db.upsert(Tables.products, row.toMap());
        }
        return rows;
      } catch (_) {
        // Local cache remains the offline fallback.
      }
    }

    final where = <String>['business_id = ?', 'is_deleted = 0'];
    final args = <Object?>[businessId];
    if (query != null && query.trim().isNotEmpty) {
      where.add('name LIKE ?');
      args.add('%${query.trim()}%');
    }
    final rows = await _db.query(
      Tables.products,
      where: where.join(' AND '),
      whereArgs: args,
      orderBy: 'updated_at DESC',
      limit: 800,
    );
    return rows.map(ProductModel.fromMap).toList();
  }

  Future<ProductModel> create({
    required String businessId,
    required String name,
    String? sku,
    String? barcode,
    String? category,
    String? unit,
    double salePrice = 0,
    double purchasePrice = 0,
    double taxPercent = 0,
    double stockQty = 0,
  }) async {
    final trimmedName = name.trim();
    if (trimmedName.isEmpty) throw Exception('Product name is required');
    if (salePrice < 0 || purchasePrice < 0) {
      throw Exception('Price must be >= 0');
    }
    if (taxPercent < 0 || taxPercent > 100) {
      throw Exception('Tax must be between 0 and 100');
    }

    final now = DateTime.now();
    final obj = ProductModel(
      id: IdService.newId(),
      businessId: businessId,
      name: trimmedName,
      sku: sku?.trim().isEmpty ?? true ? null : sku?.trim(),
      barcode: barcode?.trim().isEmpty ?? true ? null : barcode?.trim(),
      category: category?.trim().isEmpty ?? true ? null : category?.trim(),
      unit: unit?.trim().isEmpty ?? true ? null : unit?.trim(),
      salePrice: salePrice,
      purchasePrice: purchasePrice,
      taxPercent: taxPercent,
      stockQty: stockQty,
      createdAt: now,
      updatedAt: now,
      isSynced: false,
      isDeleted: false,
    );
    final api = _api;
    if (api != null) {
      try {
        final res = await api.postJson('/api/app/products/', {
          'name': obj.name,
          'sku': obj.sku,
          'barcode': obj.barcode,
          'sale_price': obj.salePrice,
          'purchase_price': obj.purchasePrice,
          'tax_percent': obj.taxPercent,
          'stock_qty': obj.stockQty,
          'unit': obj.unit,
          'category': obj.category,
        });
        final saved = ProductModel.fromJson(res, businessId: businessId);
        await _db.upsert(Tables.products, saved.toMap());
        return saved;
      } catch (_) {
        // Keep offline create when API is unavailable.
      }
    }

    await _db.upsert(Tables.products, obj.toMap());
    return obj;
  }

  Future<void> update(ProductModel product) async {
    final updated =
        product.copyWith(updatedAt: DateTime.now(), isSynced: false);
    final api = _api;
    if (api != null) {
      try {
        final res = await api.patchJson('/api/app/products/${product.id}/', {
          'name': updated.name,
          'sku': updated.sku,
          'barcode': updated.barcode,
          'sale_price': updated.salePrice,
          'purchase_price': updated.purchasePrice,
          'tax_percent': updated.taxPercent,
          'stock_qty': updated.stockQty,
          'unit': updated.unit,
          'category': updated.category,
        });
        final saved =
            ProductModel.fromJson(res, businessId: product.businessId);
        await _db.upsert(Tables.products, saved.toMap());
        return;
      } catch (_) {
        // Keep offline update when API is unavailable.
      }
    }
    await _db.upsert(Tables.products, updated.toMap());
  }

  Future<void> delete({required String productId}) async {
    final api = _api;
    if (api != null) {
      try {
        await api.deleteJson('/api/app/products/$productId/');
        await _db.softDeleteById(Tables.products, productId);
        return;
      } catch (_) {
        // Keep offline delete when API is unavailable.
      }
    }
    await _db.softDeleteById(Tables.products, productId);
  }
}
