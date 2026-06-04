import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../models/product_model.dart';
import '../../services/product_service.dart';
import '../../services/settings_service.dart';

class StockReportScreen extends StatefulWidget {
  const StockReportScreen({super.key});

  @override
  State<StockReportScreen> createState() => _StockReportScreenState();
}

class _StockReportScreenState extends State<StockReportScreen> {
  bool _loading = true;
  List<ProductModel> _rows = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final businessId = Get.find<SettingsService>().selectedBusinessId;
      _rows = await Get.find<ProductService>().list(businessId: businessId);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final stockValue = _rows.fold<double>(0, (s, r) => s + (r.stockQty * r.purchasePrice));
    return Scaffold(
      appBar: AppBar(title: const Text('Stock Report')),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.inventory_2),
                      title: const Text('Stock Value'),
                      trailing: Text('₹${stockValue.toStringAsFixed(2)}'),
                    ),
                  ),
                  const SizedBox(height: 10),
                  ..._rows.map((p) => Card(
                        child: ListTile(
                          title: Text(p.name),
                          subtitle: Text('Qty ${p.stockQty} • Sale ₹${p.salePrice.toStringAsFixed(2)}'),
                        ),
                      )),
                ],
              ),
      ),
    );
  }
}

