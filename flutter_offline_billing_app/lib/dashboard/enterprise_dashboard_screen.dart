import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/enterprise_app_controller.dart';
import '../core/responsive/enterprise_breakpoints.dart';
import '../models/enterprise_app_config.dart';
import '../permissions/permission_engine.dart';
import '../widgets/enterprise/enterprise_glass.dart';
import '../widgets/enterprise/enterprise_runtime_components.dart';

class EnterpriseDashboardScreen extends StatelessWidget {
  const EnterpriseDashboardScreen({
    super.key,
    required this.config,
    required this.permissionEngine,
  });

  final EnterpriseAppConfig config;
  final PermissionEngine permissionEngine;

  @override
  Widget build(BuildContext context) {
    final padding = EnterpriseBreakpoints.pagePadding(context);
    final controller = Get.find<EnterpriseAppController>();
    final liveMetrics = _liveMetrics(config);
    final activeProfile = controller.activeProfile.value;
    final filteredMetrics = liveMetrics.isNotEmpty
        ? liveMetrics
        : _metrics.where((m) => m.profile == activeProfile).toList();

    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: padding.copyWith(bottom: 8),
          sliver: SliverToBoxAdapter(child: _CommandHero(config: config)),
        ),
        SliverPadding(
          padding: padding.copyWith(top: 8, bottom: 8),
          sliver: SliverToBoxAdapter(
            child: EnterpriseActionStrip(
              buttons: config.buttons,
              onPressed: (button) => _runButton(controller, config, button),
            ),
          ),
        ),
        SliverPadding(
          padding: padding.copyWith(top: 8, bottom: 8),
          sliver: SliverGrid(
            delegate: SliverChildBuilderDelegate(
              (context, index) => _MetricCard(metric: filteredMetrics[index]),
              childCount: filteredMetrics.length,
            ),
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: EnterpriseBreakpoints.gridColumns(context)
                  .clamp(1, 4)
                  .toInt(),
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              mainAxisExtent: 118,
            ),
          ),
        ),
        SliverPadding(
          padding: padding.copyWith(top: 8, bottom: 110),
          sliver: SliverToBoxAdapter(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 980;
                final left = Column(
                  children: [
                    _AnalyticsPanel(config: config),
                    const SizedBox(height: 14),
                    _ModuleLauncherPreview(config: config),
                  ],
                );
                final right = Column(
                  children: const [
                    _AiSummaryPanel(),
                    SizedBox(height: 14),
                    _ActivityPanel(),
                    SizedBox(height: 14),
                    _AlertPanel(),
                  ],
                );
                return compact
                    ? Column(
                        children: [left, const SizedBox(height: 14), right])
                    : Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 7, child: left),
                          const SizedBox(width: 14),
                          Expanded(flex: 5, child: right),
                        ],
                      );
              },
            ),
          ),
        ),
      ],
    );
  }

  void _runButton(
    EnterpriseAppController controller,
    EnterpriseAppConfig config,
    EnterpriseActionButton button,
  ) {
    EnterpriseModule? module;
    for (final item in config.visibleModules) {
      if (item.key == button.module || item.route == button.route) {
        module = item;
        break;
      }
    }
    if (module != null) {
      controller.selectModule(module);
    }
  }
}

class _CommandHero extends StatelessWidget {
  const _CommandHero({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.82,
      padding: const EdgeInsets.all(20),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 780;
          return Flex(
            direction: compact ? Axis.vertical : Axis.horizontal,
            crossAxisAlignment:
                compact ? CrossAxisAlignment.start : CrossAxisAlignment.center,
            children: [
              if (compact)
                _HeroCopy(config: config)
              else
                Expanded(child: _HeroCopy(config: config)),
              SizedBox(width: compact ? 0 : 18, height: compact ? 18 : 0),
              SizedBox(
                width: compact ? double.infinity : 330,
                child: _BankingBalanceCard(config: config),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _HeroCopy extends StatelessWidget {
  const _HeroCopy({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() {
      final active = controller.activeProfile.value;

      final headline = switch (active) {
        'Retail Billing' => 'Retail POS Terminal',
        'E-Commerce Hub' => 'Digital E-Commerce Hub',
        'AI Business Copilot' => 'AI Copilot Control Room',
        _ => 'Business Command Center',
      };

      final desc = switch (active) {
        'Retail Billing' =>
          'Instant local barcoded checkout, split digital payments, cash drawers, and thermal printer controls for ${config.workspace.name}.',
        'E-Commerce Hub' =>
          'Manage digital storefronts, synchronize active product catalogs, view active online orders, and check supplier SLAs.',
        'AI Business Copilot' =>
          'Unlock business intelligence insights, run predictive cash-flow assessments, and execute automated workflows through AI.',
        _ =>
          'Live banking view, ERP control, POS billing, ecommerce operations, stock risk, accounting and AI actions for ${config.workspace.name}.',
      };

      final chips = switch (active) {
        'Retail Billing' => const [
            _HeroChip(icon: Icons.qr_code_scanner, label: 'Fast Checkout'),
            _HeroChip(icon: Icons.print, label: 'Thermal Print'),
            _HeroChip(icon: Icons.offline_bolt, label: '100% Offline-first'),
          ],
        'E-Commerce Hub' => const [
            _HeroChip(icon: Icons.store, label: 'Live Storefront'),
            _HeroChip(icon: Icons.sync, label: 'Cloud Sync'),
            _HeroChip(icon: Icons.local_shipping, label: 'SLA Tracking'),
          ],
        'AI Business Copilot' => const [
            _HeroChip(icon: Icons.auto_awesome, label: 'Smart Insights'),
            _HeroChip(icon: Icons.query_stats, label: 'Anomaly Alert'),
            _HeroChip(icon: Icons.chat_bubble_outline, label: 'Natural Voice'),
          ],
        _ => const [
            _HeroChip(icon: Icons.account_tree, label: 'Dynamic permissions'),
            _HeroChip(icon: Icons.bolt, label: 'Quick launch'),
            _HeroChip(icon: Icons.offline_bolt, label: 'Offline billing'),
            _HeroChip(icon: Icons.auto_awesome, label: 'AI summaries'),
          ],
      };

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            headline,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w900, color: controller.profileColor),
          ),
          const SizedBox(height: 8),
          Text(
            desc,
            style: Theme.of(context)
                .textTheme
                .bodyLarge
                ?.copyWith(color: Colors.white70, height: 1.35),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: chips,
          ),
        ],
      );
    });
  }
}

class _BankingBalanceCard extends StatelessWidget {
  const _BankingBalanceCard({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() {
      final activeColor = controller.profileColor;

      final darkAccent = switch (controller.activeProfile.value) {
        'Retail Billing' => const Color(0xFF043E33),
        'E-Commerce Hub' => const Color(0xFF4C0519),
        'AI Business Copilot' => const Color(0xFF78350F),
        _ => const Color(0xFF1E1B4B),
      };

      return AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              activeColor.withValues(alpha: 0.8),
              darkAccent,
              const Color(0xFF040A12),
            ],
          ),
          border: Border.all(color: activeColor.withValues(alpha: 0.3)),
          boxShadow: [
            BoxShadow(
              color: activeColor.withValues(alpha: 0.16),
              blurRadius: 12,
              spreadRadius: 1,
            )
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.account_balance_wallet, color: Colors.white),
                const Spacer(),
                Text(config.theme.brandName,
                    style:
                        const TextStyle(color: Colors.white70, fontSize: 12)),
              ],
            ),
            const SizedBox(height: 22),
            const Text('Net Business Position',
                style: TextStyle(color: Colors.white70, fontSize: 12)),
            const SizedBox(height: 4),
            Text(_moneyText(_liveSales(config)['revenue'] ?? '1842560'),
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 28,
                    fontWeight: FontWeight.w900)),
            const SizedBox(height: 14),
            Row(
              children: [
                _TinyBalance(
                    label: 'Orders',
                    value: '${_liveSales(config)['orders'] ?? 0}'),
                _TinyBalance(
                    label: 'Invoices',
                    value: '${_liveSales(config)['invoices'] ?? 0}'),
                _TinyBalance(
                    label: 'Products',
                    value: '${_liveSales(config)['products'] ?? 0}'),
              ],
            ),
          ],
        ),
      );
    });
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.metric});

  final _Metric metric;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(metric.icon, color: metric.color),
              const Spacer(),
              Text(metric.delta,
                  style: TextStyle(
                      color: metric.color, fontWeight: FontWeight.w800)),
            ],
          ),
          const Spacer(),
          Text(metric.value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(color: metric.color, fontWeight: FontWeight.w900)),
          Text(metric.label,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: Colors.white70)),
        ],
      ),
    );
  }
}

class _AnalyticsPanel extends StatelessWidget {
  const _AnalyticsPanel({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() => EnterpriseGlass(
          radius: 10,
          opacity: 0.76,
          child: SizedBox(
            height: 310,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text('Revenue and Cash Flow',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(fontWeight: FontWeight.w900)),
                    const Spacer(),
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'day', label: Text('Day')),
                        ButtonSegment(value: 'week', label: Text('Week')),
                        ButtonSegment(value: 'month', label: Text('Month')),
                      ],
                      selected: const {'week'},
                      onSelectionChanged: (_) {},
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Expanded(
                  child: LineChart(
                    LineChartData(
                      gridData: const FlGridData(show: false),
                      titlesData: const FlTitlesData(show: false),
                      borderData: FlBorderData(show: false),
                      lineBarsData: [
                        LineChartBarData(
                          isCurved: true,
                          color: controller.profileColor,
                          barWidth: 3,
                          dotData: const FlDotData(show: false),
                          spots: const [
                            FlSpot(0, 2),
                            FlSpot(1, 3.2),
                            FlSpot(2, 2.7),
                            FlSpot(3, 4.8),
                            FlSpot(4, 4.1),
                            FlSpot(5, 6.2),
                            FlSpot(6, 5.7),
                          ],
                        ),
                        LineChartBarData(
                          isCurved: true,
                          color: const Color(0xFF5EEAD4),
                          barWidth: 3,
                          dotData: const FlDotData(show: false),
                          spots: const [
                            FlSpot(0, 1.2),
                            FlSpot(1, 1.8),
                            FlSpot(2, 2.9),
                            FlSpot(3, 3.1),
                            FlSpot(4, 3.9),
                            FlSpot(5, 4.4),
                            FlSpot(6, 5.2),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ));
  }
}

class _ModuleLauncherPreview extends StatelessWidget {
  const _ModuleLauncherPreview({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Universal Module Grid',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 12),
          EnterpriseLauncherGrid(
            items: config.launcher,
            onLaunch: (item) {
              final controller = Get.find<EnterpriseAppController>();
              for (final module in config.visibleModules) {
                if (module.key == item.key || module.route == item.route) {
                  controller.selectModule(module);
                  break;
                }
              }
            },
          ),
        ],
      ),
    );
  }
}

class _AiSummaryPanel extends StatelessWidget {
  const _AiSummaryPanel();

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() {
      final active = controller.activeProfile.value;
      final lines = switch (active) {
        'Retail Billing' => const [
            'Reorder 12 SKUs before Friday to avoid stockout.',
            'Cash drawer 2 is over threshold by Rs 5,000.',
            'Peak hours predicted between 4 PM and 7 PM.',
          ],
        'E-Commerce Hub' => const [
            '3 abandoned carts worth Rs 12,000 can be recovered.',
            'Supplier SLA breach warning for "Electronics".',
            'Organic traffic up 15% this week.',
          ],
        'AI Business Copilot' => const [
            'Your overall business health score is 92/100.',
            'Suggested cash transfer to high-yield account.',
            'No severe anomalies detected in recent logs.',
          ],
        _ => const [
            'Trust Fund-c has 3 open invoices and high repayment confidence.',
            'Marketing spend is 8 percent above weekly target.',
            '2 employees have pending leave approvals.',
          ],
      };
      return _Panel(
        icon: Icons.auto_awesome,
        title: 'AI Workspace Summary',
        lines: lines,
      );
    });
  }
}

class _ActivityPanel extends StatelessWidget {
  const _ActivityPanel();

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() {
      final active = controller.activeProfile.value;
      final activities = switch (active) {
        'Retail Billing' => _retailActivity,
        'E-Commerce Hub' => _ecomActivity,
        'AI Business Copilot' => _aiActivity,
        _ => _erpActivity,
      };

      return EnterpriseGlass(
        radius: 10,
        opacity: 0.76,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Realtime Activity',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 10),
            for (final row in activities)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: CircleAvatar(
                  radius: 17,
                  backgroundColor: row.color.withValues(alpha: 0.16),
                  child: Icon(row.icon, size: 17, color: row.color),
                ),
                title: Text(row.title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                subtitle: Text(row.subtitle),
                trailing: Text(row.amount),
              ),
          ],
        ),
      );
    });
  }
}

class _AlertPanel extends StatelessWidget {
  const _AlertPanel();

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() {
      final active = controller.activeProfile.value;
      final lines = switch (active) {
        'Retail Billing' => const [
            'Low stock: Coffee Mug, Hoodie, Rice 1kg.',
            'Terminal 3 disconnected.',
          ],
        'E-Commerce Hub' => const [
            'Payment gateway timeout rate > 2%.',
            '3 pending return requests.',
          ],
        'AI Business Copilot' => const [
            'Data sync delayed by 5 minutes.',
            'High API latency detected.',
          ],
        _ => const [
            'GST report needs review before filing.',
            'Two branches have disabled payment methods.',
          ],
      };

      return _Panel(
        icon: Icons.warning_amber,
        title: 'Operations Alerts',
        lines: lines,
      );
    });
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.icon, required this.title, required this.lines});

  final IconData icon;
  final String title;
  final List<String> lines;

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: controller.profileColor),
              const SizedBox(width: 10),
              Expanded(
                child: Text(title,
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.w900)),
              ),
            ],
          ),
          const SizedBox(height: 12),
          for (final line in lines)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.check_circle,
                      size: 16, color: controller.profileColor),
                  const SizedBox(width: 8),
                  Expanded(child: Text(line)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _HeroChip extends StatelessWidget {
  const _HeroChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Chip(avatar: Icon(icon, size: 16), label: Text(label));
  }
}

class _TinyBalance extends StatelessWidget {
  const _TinyBalance({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label,
              style: const TextStyle(color: Colors.white54, fontSize: 11)),
          Text(value,
              style: const TextStyle(
                  color: Colors.white, fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}

class _Metric {
  const _Metric(
      this.profile, this.label, this.value, this.delta, this.icon, this.color);

  final String profile;
  final String label;
  final String value;
  final String delta;
  final IconData icon;
  final Color color;
}

class _Activity {
  const _Activity(
      this.title, this.subtitle, this.amount, this.icon, this.color);

  final String title;
  final String subtitle;
  final String amount;
  final IconData icon;
  final Color color;
}

Map<String, dynamic> _liveSales(EnterpriseAppConfig config) {
  final sales = config.liveData['sales'];
  if (sales is Map<String, dynamic>) return sales;
  if (sales is Map) {
    return sales.map((key, value) => MapEntry(key.toString(), value));
  }
  return const {};
}

List<_Metric> _liveMetrics(EnterpriseAppConfig config) {
  final sales = _liveSales(config);
  if (sales.isEmpty) return const [];
  return [
    _Metric('Live', 'Revenue', _moneyText(sales['revenue']), 'live',
        Icons.payments, const Color(0xFF22C55E)),
    _Metric('Live', 'Orders', '${sales['orders'] ?? 0}', 'API',
        Icons.shopping_cart_checkout, const Color(0xFF38BDF8)),
    _Metric('Live', 'Customers', '${sales['customers'] ?? 0}', 'API',
        Icons.groups, const Color(0xFFF59E0B)),
    _Metric('Live', 'Stock Units', '${sales['stock_units'] ?? 0}', 'API',
        Icons.inventory_2, const Color(0xFF6366F1)),
  ];
}

String _moneyText(Object? value) {
  final raw = value?.toString() ?? '0';
  if (raw.startsWith('Rs')) return raw;
  final parsed = num.tryParse(raw) ?? 0;
  return 'Rs ${parsed.toStringAsFixed(0)}';
}

const _metrics = [
  // Retail Billing
  _Metric('Retail Billing', 'Today sales', 'Rs 86,420', '+18%',
      Icons.point_of_sale, Color(0xFF10B981)),
  _Metric('Retail Billing', 'Checkout Count', '241', '+12%',
      Icons.shopping_cart_checkout, Color(0xFF10B981)),
  _Metric('Retail Billing', 'Inventory value', 'Rs 12.8L', '+4%',
      Icons.inventory_2, Color(0xFF10B981)),

  // Enterprise ERP
  _Metric('Enterprise ERP', 'Open receivables', 'Rs 4.2L', '-6%',
      Icons.receipt_long, Color(0xFF6366F1)),
  _Metric('Enterprise ERP', 'Capital Position', 'Rs 18.4L', '+2%',
      Icons.account_balance, Color(0xFF6366F1)),
  _Metric('Enterprise ERP', 'Payroll tasks', '12 pending', 'due', Icons.badge,
      Color(0xFF6366F1)),

  // E-Commerce Hub
  _Metric('E-Commerce Hub', 'Online orders', '128', '+31%', Icons.storefront,
      Color(0xFFF43F5E)),
  _Metric('E-Commerce Hub', 'Website traffic', '1,492', '+5%', Icons.language,
      Color(0xFFF43F5E)),
  _Metric('E-Commerce Hub', 'Supplier SLAs', '3 alerts', 'warn',
      Icons.local_shipping, Color(0xFFF43F5E)),

  // AI Business Copilot
  _Metric('AI Business Copilot', 'AI actions', '9', 'ready', Icons.auto_awesome,
      Color(0xFFF59E0B)),
  _Metric('AI Business Copilot', 'Auto-sync logs', 'Syncing', 'live',
      Icons.sync, Color(0xFFF59E0B)),
  _Metric('AI Business Copilot', 'Anomaly alert', '0 issues', 'safe',
      Icons.health_and_safety, Color(0xFFF59E0B)),
];

const _retailActivity = [
  _Activity('Invoice created', 'POS terminal 02', 'Rs 2,430',
      Icons.receipt_long, Color(0xFF10B981)),
  _Activity('Cash settlement', 'End of shift', 'Rs 42,000', Icons.payments,
      Color(0xFF10B981)),
  _Activity('Refund processed', 'Order #892', '-Rs 450',
      Icons.assignment_return, Color(0xFFF43F5E)),
  _Activity('Stock adjust', 'Damaged goods', '-3 pcs', Icons.inventory,
      Color(0xFFF59E0B)),
];

const _erpActivity = [
  _Activity('Lead moved', 'CRM: Proposal', 'Rs 1.2L', Icons.groups,
      Color(0xFF6366F1)),
  _Activity('Payroll run', 'Salary disburse', 'Rs 4.8L', Icons.account_balance,
      Color(0xFF6366F1)),
  _Activity('Vendor payment', 'Office Supplies', '-Rs 12k', Icons.payment,
      Color(0xFFF43F5E)),
  _Activity('Asset acquired', 'New MacBooks', 'Rs 2.4L', Icons.computer,
      Color(0xFF6366F1)),
];

const _ecomActivity = [
  _Activity('Order shipped', 'Tracking generated', 'Rs 1,490',
      Icons.local_shipping, Color(0xFFF43F5E)),
  _Activity(
      'New review', '5 stars on Mug', 'View', Icons.star, Color(0xFFF59E0B)),
  _Activity('Promo code', 'WINTER20 applied', '-Rs 200', Icons.local_offer,
      Color(0xFF10B981)),
  _Activity('Cart abandoned', 'john@example', 'Rs 4,200',
      Icons.shopping_cart_checkout, Color(0xFF6366F1)),
];

const _aiActivity = [
  _Activity('Anomaly detected', 'Unusual login', 'Resolved', Icons.security,
      Color(0xFFF59E0B)),
  _Activity(
      'Auto-sync', 'CRM to ERP sync', 'Success', Icons.sync, Color(0xFF10B981)),
  _Activity('Report generated', 'Weekly summary', 'View', Icons.analytics,
      Color(0xFF6366F1)),
  _Activity('Model trained', 'Demand forecast', 'v2.4', Icons.model_training,
      Color(0xFF10B981)),
];
