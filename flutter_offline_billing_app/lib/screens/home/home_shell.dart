import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/auth_controller.dart';
import '../../widgets/sync_status_chip.dart';
import '../dashboard/dashboard_screen.dart';
import '../expenses/expense_list_screen.dart';
import '../invoices/invoice_list_screen.dart';
import '../parties/party_list_screen.dart';
import '../products/product_list_screen.dart';
import '../reports/reports_hub_screen.dart';
import '../settings/settings_screen.dart';
import '../transactions/transactions_screen.dart';

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final tabs = <_Tab>[
      const _Tab(label: 'Dashboard', icon: Icons.dashboard, child: DashboardScreen()),
      const _Tab(label: 'Parties', icon: Icons.people, child: PartyListScreen()),
      const _Tab(label: 'Products', icon: Icons.inventory_2, child: ProductListScreen()),
      const _Tab(label: 'Invoices', icon: Icons.receipt_long, child: InvoiceListScreen()),
      const _Tab(label: 'More', icon: Icons.more_horiz, child: SizedBox()),
    ];

    final current = tabs[_index];

    return Scaffold(
      appBar: AppBar(
        title: Text(current.label),
        actions: [
          const SyncStatusChip(),
          const SizedBox(width: 8),
          if (_index == 4)
            PopupMenuButton<String>(
              onSelected: (v) async {
                if (v == 'transactions') Get.to(() => const TransactionsScreen());
                if (v == 'expenses') Get.to(() => const ExpenseListScreen());
                if (v == 'reports') Get.to(() => const ReportsHubScreen());
                if (v == 'settings') Get.to(() => const SettingsScreen());
                if (v == 'logout') await Get.find<AuthController>().logout();
              },
              itemBuilder: (context) => const [
                PopupMenuItem(value: 'transactions', child: Text('Transactions')),
                PopupMenuItem(value: 'expenses', child: Text('Expenses')),
                PopupMenuItem(value: 'reports', child: Text('Reports')),
                PopupMenuItem(value: 'settings', child: Text('Settings')),
                PopupMenuDivider(),
                PopupMenuItem(value: 'logout', child: Text('Logout')),
              ],
            ),
        ],
      ),
      body: SafeArea(
        child: _index == 4
            ? _MoreContent(
                onOpenTransactions: () => Get.to(() => const TransactionsScreen()),
                onOpenExpenses: () => Get.to(() => const ExpenseListScreen()),
                onOpenReports: () => Get.to(() => const ReportsHubScreen()),
                onOpenSettings: () => Get.to(() => const SettingsScreen()),
                onLogout: () => Get.find<AuthController>().logout(),
              )
            : current.child,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          for (final t in tabs)
            NavigationDestination(
              icon: Icon(t.icon),
              label: t.label,
            ),
        ],
      ),
    );
  }
}

class _Tab {
  const _Tab({required this.label, required this.icon, required this.child});
  final String label;
  final IconData icon;
  final Widget child;
}

class _MoreContent extends StatelessWidget {
  const _MoreContent({
    required this.onOpenTransactions,
    required this.onOpenExpenses,
    required this.onOpenReports,
    required this.onOpenSettings,
    required this.onLogout,
  });

  final VoidCallback onOpenTransactions;
  final VoidCallback onOpenExpenses;
  final VoidCallback onOpenReports;
  final VoidCallback onOpenSettings;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Card(
          child: Column(
            children: [
              ListTile(
                leading: const Icon(Icons.payments),
                title: const Text('Transactions'),
                subtitle: const Text('Payment In / Payment Out'),
                onTap: onOpenTransactions,
              ),
              const Divider(height: 0),
              ListTile(
                leading: const Icon(Icons.receipt),
                title: const Text('Expenses'),
                subtitle: const Text('Track business expenses'),
                onTap: onOpenExpenses,
              ),
              const Divider(height: 0),
              ListTile(
                leading: const Icon(Icons.bar_chart),
                title: const Text('Reports'),
                subtitle: const Text('Sales, stock, party ledger'),
                onTap: onOpenReports,
              ),
              const Divider(height: 0),
              ListTile(
                leading: const Icon(Icons.settings),
                title: const Text('Settings'),
                subtitle: const Text('API Base URL, Sync Token'),
                onTap: onOpenSettings,
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Logout'),
            onTap: onLogout,
          ),
        ),
      ],
    );
  }
}

