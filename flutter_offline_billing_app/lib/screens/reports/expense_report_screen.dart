import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../models/expense_model.dart';
import '../../services/expense_service.dart';
import '../../services/settings_service.dart';

class ExpenseReportScreen extends StatefulWidget {
  const ExpenseReportScreen({super.key});

  @override
  State<ExpenseReportScreen> createState() => _ExpenseReportScreenState();
}

class _ExpenseReportScreenState extends State<ExpenseReportScreen> {
  bool _loading = true;
  List<ExpenseModel> _rows = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final businessId = Get.find<SettingsService>().selectedBusinessId;
      _rows = await Get.find<ExpenseService>().list(businessId: businessId);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = _rows.fold<double>(0, (s, r) => s + r.amount);
    return Scaffold(
      appBar: AppBar(title: const Text('Expense Report')),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(
                padding: const EdgeInsets.all(12),
                children: [
                  Card(
                    child: ListTile(
                      leading: const Icon(Icons.receipt),
                      title: const Text('Total Expenses'),
                      trailing: Text('₹${total.toStringAsFixed(2)}'),
                    ),
                  ),
                  const SizedBox(height: 10),
                  ..._rows.map(
                    (e) => Card(
                      child: ListTile(
                        title: Text('₹${e.amount.toStringAsFixed(2)}'),
                        subtitle: Text('${e.category ?? 'Expense'} • ${e.date.toLocal().toString().split(' ').first}'),
                      ),
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

