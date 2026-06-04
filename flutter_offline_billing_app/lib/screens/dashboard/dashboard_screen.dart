import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/dashboard_controller.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    // Load once when tab opens.
    WidgetsBinding.instance
        .addPostFrameCallback((_) => Get.find<DashboardController>().load());
  }

  @override
  Widget build(BuildContext context) {
    final c = Get.find<DashboardController>();
    final scheme = Theme.of(context).colorScheme;

    return RefreshIndicator(
      onRefresh: c.load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Obx(() {
            final s = c.summary.value;
            if (c.isLoading.value && s == null) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: CircularProgressIndicator()),
              );
            }
            if (c.error.value.isNotEmpty && s == null) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child:
                    Text(c.error.value, style: TextStyle(color: scheme.error)),
              );
            }
            if (s == null) return const SizedBox.shrink();

            return Column(
              children: [
                _StatsGrid(
                  cards: [
                    _StatCard(
                      title: 'Sales',
                      value: s.salesTotal,
                      subtitle: 'Total',
                      icon: Icons.trending_up,
                    ),
                    _StatCard(
                      title: 'Paid',
                      value: s.salesPaid,
                      subtitle: 'Received',
                      icon: Icons.payments,
                    ),
                    _StatCard(
                      title: 'Balance',
                      value: s.salesBalance,
                      subtitle: 'Due',
                      icon: Icons.pending_actions,
                    ),
                    _StatCard(
                      title: 'Purchase',
                      value: s.purchaseTotal,
                      subtitle: 'Total',
                      icon: Icons.shopping_cart,
                    ),
                    _StatCard(
                      title: 'Expenses',
                      value: s.expenseTotal,
                      subtitle: 'Total',
                      icon: Icons.receipt,
                    ),
                    _StatCard(
                      title: 'Stock',
                      value: s.stockValue,
                      subtitle: '${s.stockCount} products',
                      icon: Icons.inventory_2,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            Text(
                              'Sales Snapshot',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.w900),
                            ),
                            const Spacer(),
                            Icon(Icons.bar_chart, color: scheme.primary),
                          ],
                        ),
                        const SizedBox(height: 14),
                        SizedBox(
                          height: 180,
                          child: BarChart(
                            BarChartData(
                              gridData: FlGridData(
                                show: true,
                                drawVerticalLine: false,
                                getDrawingHorizontalLine: (_) => FlLine(
                                  color: scheme.outlineVariant
                                      .withValues(alpha: 0.6),
                                  strokeWidth: 1,
                                ),
                              ),
                              borderData: FlBorderData(show: false),
                              titlesData: const FlTitlesData(show: false),
                              barGroups: _demoBars(s.salesTotal),
                            ),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Demo chart - backend analytics connect hote hi real trend dikhega.',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            );
          }),
        ],
      ),
    );
  }

  static List<BarChartGroupData> _demoBars(double base) {
    final values = <double>[
      (base * 0.2).clamp(0, 100000),
      (base * 0.1).clamp(0, 100000),
      (base * 0.25).clamp(0, 100000),
      (base * 0.15).clamp(0, 100000),
      (base * 0.3).clamp(0, 100000),
    ];
    return [
      for (var i = 0; i < values.length; i++)
        BarChartGroupData(
          x: i,
          barRods: [BarChartRodData(toY: values[i] == 0 ? 1 : values[i])],
        ),
    ];
  }
}

class _StatsGrid extends StatelessWidget {
  const _StatsGrid({required this.cards});
  final List<_StatCard> cards;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final cols = width >= 900
            ? 3
            : width >= 600
                ? 3
                : 2;
        return GridView.count(
          crossAxisCount: cols,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 1.38,
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          children: cards,
        );
      },
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.title,
    required this.value,
    required this.subtitle,
    required this.icon,
  });

  final String title;
  final double value;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final tone = switch (title) {
      'Sales' => const Color(0xFF0F766E),
      'Paid' => const Color(0xFF2563EB),
      'Balance' => const Color(0xFFD97706),
      'Purchase' => const Color(0xFF7C3AED),
      'Expenses' => const Color(0xFFDC2626),
      _ => scheme.primary,
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: tone.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: tone, size: 20),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context)
                        .textTheme
                        .titleSmall
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                ),
              ],
            ),
            const Spacer(),
            Text(
              value.toStringAsFixed(2),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 2),
            Text(subtitle,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: scheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}
