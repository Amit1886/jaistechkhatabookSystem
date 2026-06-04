import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../models/invoice_model.dart';
import '../../services/invoice_service.dart';
import '../../services/settings_service.dart';

class SalesReportScreen extends StatefulWidget {
  const SalesReportScreen({super.key});

  @override
  State<SalesReportScreen> createState() => _SalesReportScreenState();
}

class _SalesReportScreenState extends State<SalesReportScreen> {
  bool _loading = true;
  List<InvoiceModel> _rows = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final businessId = Get.find<SettingsService>().selectedBusinessId;
      final invoices = await Get.find<InvoiceService>().list(businessId: businessId);
      _rows = invoices.where((i) => i.type == 'sale' && !i.isDeleted).toList();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = _rows.fold<double>(0, (s, r) => s + r.total);
    return Scaffold(
      appBar: AppBar(title: const Text('Sales Report')),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.trending_up),
                      title: const Text('Total Sales'),
                      trailing: Text('₹${total.toStringAsFixed(2)}'),
                    ),
                  ),
                  const SizedBox(height: 10),
                  ..._rows.map((r) => Card(
                        child: ListTile(
                          title: Text(r.number),
                          subtitle: Text(r.date.toLocal().toString().split(' ').first),
                          trailing: Text('₹${r.total.toStringAsFixed(2)}'),
                        ),
                      )),
                ],
              ),
      ),
    );
  }
}

