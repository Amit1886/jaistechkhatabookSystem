import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../dynamic_ui/module_icon.dart';
import '../providers/erp_provider.dart';

class DashboardView extends StatelessWidget {
  const DashboardView({super.key});

  @override
  Widget build(BuildContext context) {
    final erp = context.watch<ErpProvider>();
    final metrics = Map<String, dynamic>.from(erp.dashboard['metrics'] ?? {});
    final modules = erp.modules;
    return RefreshIndicator(
      onRefresh: erp.bootstrap,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          LayoutBuilder(
            builder: (context, c) {
              final columns = c.maxWidth > 1100 ? 4 : c.maxWidth > 700 ? 3 : 2;
              return GridView.count(
                crossAxisCount: columns,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 1.75,
                children: [
                  _MetricCard(title: 'Sales', value: _money(metrics['sales']), icon: Icons.trending_up, colors: const [Color(0xFF176B87), Color(0xFF2D9CDB)]),
                  _MetricCard(title: 'Profit/Loss', value: _money(metrics['profit_loss']), icon: Icons.account_balance_wallet_outlined, colors: const [Color(0xFF27AE60), Color(0xFFF2994A)]),
                  _MetricCard(title: 'Invoices', value: '${metrics['invoice_count'] ?? 0}', icon: Icons.receipt_long_outlined, colors: const [Color(0xFF9B51E0), Color(0xFF2D9CDB)]),
                  _MetricCard(title: 'Low Stock', value: '${metrics['low_stock_count'] ?? 0}', icon: Icons.warning_amber_rounded, colors: const [Color(0xFFEB5757), Color(0xFFF2994A)]),
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                height: 220,
                child: BarChart(
                  BarChartData(
                    borderData: FlBorderData(show: false),
                    gridData: const FlGridData(show: false),
                    titlesData: const FlTitlesData(leftTitles: AxisTitles(), topTitles: AxisTitles(), rightTitles: AxisTitles()),
                    barGroups: List.generate(7, (i) => BarChartGroupData(x: i, barRods: [BarChartRodData(toY: (i + 2) * 9, width: 18, borderRadius: BorderRadius.circular(4))])),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('Modules', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, c) {
              final columns = c.maxWidth > 1100 ? 6 : c.maxWidth > 700 ? 4 : 2;
              return GridView.count(
                crossAxisCount: columns,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 1.25,
                children: modules.map((m) => Card(child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Icon(ModuleIcon.fromKey(m.key)), const SizedBox(height: 8), Text(m.name, textAlign: TextAlign.center)])))).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  static String _money(dynamic amount) {
    final value = num.tryParse('$amount') ?? 0;
    return NumberFormat.currency(locale: 'en_IN', symbol: 'Rs ', decimalDigits: 0).format(value);
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.title, required this.value, required this.icon, required this.colors});

  final String title;
  final String value;
  final IconData icon;
  final List<Color> colors;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), gradient: LinearGradient(colors: colors)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Icon(icon, color: Colors.white),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(color: Colors.white70)), Text(value, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800))]),
        ],
      ),
    );
  }
}

