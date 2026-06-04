import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'expense_report_screen.dart';
import 'party_ledger_screen.dart';
import 'sales_report_screen.dart';
import 'stock_report_screen.dart';

class ReportsHubScreen extends StatelessWidget {
  const ReportsHubScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reports')),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.trending_up),
                  title: const Text('Sales Report'),
                  onTap: () => Get.to(() => const SalesReportScreen()),
                ),
                const Divider(height: 0),
                ListTile(
                  leading: const Icon(Icons.inventory_2),
                  title: const Text('Stock Report'),
                  onTap: () => Get.to(() => const StockReportScreen()),
                ),
                const Divider(height: 0),
                ListTile(
                  leading: const Icon(Icons.people),
                  title: const Text('Party Ledger'),
                  onTap: () => Get.to(() => const PartyLedgerScreen()),
                ),
                const Divider(height: 0),
                ListTile(
                  leading: const Icon(Icons.receipt),
                  title: const Text('Expense Report'),
                  onTap: () => Get.to(() => const ExpenseReportScreen()),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

