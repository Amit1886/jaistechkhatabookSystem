import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../core/responsive/enterprise_breakpoints.dart';
import '../../models/enterprise_app_config.dart';
import '../../permissions/permission_engine.dart';
import '../../screens/settings/settings_screen.dart';
import '../../widgets/enterprise/enterprise_glass.dart';
import '../../widgets/enterprise/enterprise_icons.dart';

class SuperAppModuleWorkspace extends StatelessWidget {
  const SuperAppModuleWorkspace({
    super.key,
    required this.module,
    required this.permissionEngine,
    required this.workspace,
  });

  final EnterpriseModule module;
  final PermissionEngine permissionEngine;
  final EnterpriseWorkspace workspace;

  @override
  Widget build(BuildContext context) {
    if (!permissionEngine.can(module.permission, PermissionAction.view)) {
      return const Center(
          child: Text('This module is not available for your role.'));
    }
    return switch (module.key) {
      'pos' || 'billing' || 'sales' => PosWorkspace(module: module),
      'selfcheckout' => SelfCheckoutWorkspace(module: module),
      'ledger' || 'accounting' => AccountingWorkspace(module: module),
      'products' || 'inventory' => InventoryWorkspace(module: module),
      'crm' => CrmWorkspace(module: module),
      'ecommerce' || 'website' => EcommerceWorkspace(module: module),
      'suppliers' ||
      'purchases' ||
      'vendor_portal' =>
        ProcurementWorkspace(module: module),
      'hrm' => HrmWorkspace(module: module),
      'reports' => ReportsWorkspace(module: module),
      'admin_panel' || 'builder' => AdminBuilderWorkspace(module: module),
      'api_management' => ApiManagementWorkspace(module: module),
      'apk_builder' ||
      'delivery_app' ||
      'customer_app' ||
      'b2b' ||
      'b2c' =>
        PortalWorkspace(module: module),
      'settings' => const SettingsScreen(),
      _ => GenericWorkspace(module: module, workspace: workspace),
    };
  }
}

class PosWorkspace extends StatefulWidget {
  const PosWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<PosWorkspace> createState() => _PosWorkspaceState();
}

class _PosWorkspaceState extends State<PosWorkspace> {
  final List<_CartLine> _cart = [
    _CartLine(_demoProducts[0], 1),
    _CartLine(_demoProducts[2], 2),
  ];
  bool _syncing = false;

  double get _subtotal =>
      _cart.fold<double>(0, (sum, line) => sum + line.total);
  double get _tax => _subtotal * 0.18;
  double get _discount => _subtotal > 25000 ? 1499 : 120;
  double get _total => _subtotal + _tax - _discount;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'POS Command Terminal',
          subtitle:
              'Barcode scan, split payment, hold bill, refund, QR payment and thermal receipt.',
          actions: [
            _HeaderAction(
                icon: Icons.pause_circle_outline,
                label: 'Hold',
                onTap: () => _toast('Bill held for counter 2')),
            _HeaderAction(
                icon: Icons.assignment_return,
                label: 'Refund',
                onTap: () => _toast('Refund workflow opened')),
            _HeaderAction(
                icon: Icons.print,
                label: 'Print',
                onTap: () => _toast('Thermal print queued')),
          ],
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 980;
            final catalog = _GlassPanel(
              title: 'Touch Catalog',
              trailing: _LiveChip(
                  label: _syncing ? 'Syncing' : 'Offline ready',
                  color: const Color(0xFF10B981)),
              child: Column(
                children: [
                  TextField(
                    onSubmitted: (_) => _addProduct(_demoProducts.first),
                    decoration: InputDecoration(
                      hintText: 'Search product / Scan barcode',
                      prefixIcon: const Icon(Icons.qr_code_scanner),
                      suffixIcon: IconButton(
                        tooltip: 'Scan barcode',
                        onPressed: () => _addProduct(_demoProducts.first),
                        icon: const Icon(Icons.center_focus_strong),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  _ProductGrid(onAdd: _addProduct),
                ],
              ),
            );
            final cart = _GlassPanel(
              title: 'Cart',
              trailing: Text('${_cart.length} lines',
                  style: const TextStyle(fontWeight: FontWeight.w800)),
              child: Column(
                children: [
                  for (final line in _cart)
                    _CartLineTile(
                      line: line,
                      onMinus: () => _changeQty(line, -1),
                      onPlus: () => _changeQty(line, 1),
                      onRemove: () => setState(() => _cart.remove(line)),
                    ),
                  const Divider(height: 26),
                  _TotalRow(label: 'Subtotal', value: _money(_subtotal)),
                  _TotalRow(label: 'Discount', value: '-${_money(_discount)}'),
                  _TotalRow(label: 'GST 18%', value: _money(_tax)),
                  _TotalRow(
                      label: 'Total', value: _money(_total), strong: true),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: _checkout,
                          icon: const Icon(Icons.qr_code_2),
                          label: const Text('Pay Now'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      IconButton.filledTonal(
                        tooltip: 'Split payment',
                        onPressed: () =>
                            _toast('Cash + UPI split payment ready'),
                        icon: const Icon(Icons.call_split),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filledTonal(
                        tooltip: 'Customer display',
                        onPressed: () => _toast('Customer display updated'),
                        icon: const Icon(Icons.desktop_windows_outlined),
                      ),
                    ],
                  ),
                ],
              ),
            );
            if (compact)
              return Column(
                  children: [catalog, const SizedBox(height: 14), cart]);
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(flex: 7, child: catalog),
                const SizedBox(width: 14),
                Expanded(flex: 4, child: cart),
              ],
            );
          },
        ),
      ],
    );
  }

  void _addProduct(_DemoProduct product) {
    setState(() {
      final existing =
          _cart.where((line) => line.product.sku == product.sku).toList();
      if (existing.isEmpty) {
        _cart.add(_CartLine(product, 1));
      } else {
        existing.first.qty += 1;
      }
    });
    _toast('${product.name} added');
  }

  void _changeQty(_CartLine line, int delta) {
    setState(() {
      line.qty += delta;
      if (line.qty <= 0) _cart.remove(line);
    });
  }

  Future<void> _checkout() async {
    setState(() => _syncing = true);
    await Future<void>.delayed(const Duration(milliseconds: 650));
    setState(() => _syncing = false);
    _toast('Paid ${_money(_total)}. Receipt and stock sync created.');
  }
}

class SelfCheckoutWorkspace extends StatefulWidget {
  const SelfCheckoutWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<SelfCheckoutWorkspace> createState() => _SelfCheckoutWorkspaceState();
}

class _SelfCheckoutWorkspaceState extends State<SelfCheckoutWorkspace> {
  int _step = 0;
  final List<_CartLine> _cart = [
    _CartLine(_demoProducts[2], 1),
    _CartLine(_demoProducts[4], 1)
  ];

  @override
  Widget build(BuildContext context) {
    final total = _cart.fold<double>(0, (sum, line) => sum + line.total);
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'Self Checkout Kiosk',
          subtitle:
              'Scan and pay kiosk with QR payment, language selector and assisted search.',
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 820;
            final welcome = _GlassPanel(
              title: _step == 0 ? 'Welcome' : 'Scan Active',
              child: Column(
                children: [
                  AnimatedScale(
                    duration: const Duration(milliseconds: 260),
                    scale: _step == 0 ? 1 : 0.92,
                    child: Icon(
                      _step == 0 ? Icons.check_circle : Icons.qr_code_scanner,
                      color: const Color(0xFF22C55E),
                      size: 94,
                    ),
                  ),
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: () => setState(() => _step = 1),
                    icon: const Icon(Icons.center_focus_strong),
                    label:
                        Text(_step == 0 ? 'Start Scanning' : 'Scan Next Item'),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: () => _toast('Search product opened'),
                    icon: const Icon(Icons.search),
                    label: const Text('Tap To Search Product'),
                  ),
                ],
              ),
            );
            final cart = _GlassPanel(
              title: 'Your Cart',
              child: Column(
                children: [
                  for (final line in _cart)
                    _CartLineTile(
                      line: line,
                      onMinus: () => setState(
                          () => line.qty = line.qty > 1 ? line.qty - 1 : 1),
                      onPlus: () => setState(() => line.qty++),
                      onRemove: () => setState(() => _cart.remove(line)),
                    ),
                  const Divider(),
                  _TotalRow(
                      label: 'Total Items',
                      value:
                          '${_cart.fold<int>(0, (sum, line) => sum + line.qty)}'),
                  _TotalRow(
                      label: 'Total Amount',
                      value: _money(total),
                      strong: true),
                  const SizedBox(height: 12),
                  FilledButton.icon(
                    onPressed: () => _toast('QR payment link generated'),
                    icon: const Icon(Icons.qr_code_2),
                    label: const Text('Proceed To Pay'),
                  ),
                ],
              ),
            );
            if (compact)
              return Column(
                  children: [welcome, const SizedBox(height: 14), cart]);
            return Row(children: [
              Expanded(child: welcome),
              const SizedBox(width: 14),
              Expanded(child: cart)
            ]);
          },
        ),
      ],
    );
  }
}

class AccountingWorkspace extends StatefulWidget {
  const AccountingWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<AccountingWorkspace> createState() => _AccountingWorkspaceState();
}

class _AccountingWorkspaceState extends State<AccountingWorkspace> {
  bool _posting = false;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'Accounting and GST',
          subtitle:
              'Ledger, journal entries, balance sheet, GST, expenses, invoices and financial reports.',
          actions: [
            _HeaderAction(icon: Icons.save, label: 'Post', onTap: _postJournal),
            _HeaderAction(
                icon: Icons.picture_as_pdf,
                label: 'PDF',
                onTap: () => _toast('Profit and loss PDF generated')),
          ],
        ),
        _MetricGrid(metrics: const [
          _MetricData('Total Income', 'Rs 12,45,320', '+16.2%',
              Icons.trending_up, Color(0xFF22C55E)),
          _MetricData('Expenses', 'Rs 8,25,100', '-3.1%', Icons.trending_down,
              Color(0xFFFB7185)),
          _MetricData('Net Profit', 'Rs 4,20,220', '+18.4%',
              Icons.account_balance_wallet, Color(0xFF38BDF8)),
          _MetricData('GST Payable', 'Rs 86,440', 'due', Icons.receipt,
              Color(0xFFF59E0B)),
        ]),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 980;
            final journal = _GlassPanel(
              title: 'Journal Entry',
              trailing: _posting
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : null,
              child: const _EnterpriseTable(
                columns: ['Account', 'Debit', 'Credit'],
                rows: [
                  ['Cash In Hand', 'Rs 2,00,000', '-'],
                  ['Sales Account', '-', 'Rs 2,00,000'],
                  ['CGST', '-', 'Rs 18,000'],
                  ['SGST', '-', 'Rs 18,000'],
                  ['Total', 'Rs 2,36,000', 'Rs 2,36,000'],
                ],
              ),
            );
            final reports = _GlassPanel(
              title: 'Financial Reports',
              child: Column(
                children: [
                  _ReportTile(
                      'Profit and Loss',
                      'Revenue, COGS and operating expenses',
                      Icons.query_stats),
                  _ReportTile('Balance Sheet', 'Assets, liabilities and equity',
                      Icons.account_balance),
                  _ReportTile('GST Filing', 'GSTR summary and tax ledger',
                      Icons.assignment_turned_in),
                ],
              ),
            );
            if (compact)
              return Column(
                  children: [journal, const SizedBox(height: 14), reports]);
            return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(flex: 7, child: journal),
              const SizedBox(width: 14),
              Expanded(flex: 4, child: reports),
            ]);
          },
        ),
      ],
    );
  }

  Future<void> _postJournal() async {
    setState(() => _posting = true);
    await Future<void>.delayed(const Duration(milliseconds: 600));
    setState(() => _posting = false);
    _toast('Journal posted and GST ledger updated');
  }
}

class InventoryWorkspace extends StatefulWidget {
  const InventoryWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<InventoryWorkspace> createState() => _InventoryWorkspaceState();
}

class _InventoryWorkspaceState extends State<InventoryWorkspace> {
  String _filter = 'All';

  @override
  Widget build(BuildContext context) {
    final products = _filter == 'Low Stock'
        ? _demoProducts.where((p) => p.stock < 10).toList()
        : _demoProducts;
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'Inventory and Warehouses',
          subtitle:
              'Products, variants, batches, barcode labels, stock transfer and low stock alerts.',
          actions: [
            _HeaderAction(
                icon: Icons.swap_horiz,
                label: 'Transfer',
                onTap: () => _toast('Stock transfer created')),
            _HeaderAction(
                icon: Icons.label,
                label: 'Barcode',
                onTap: () => _toast('Barcode labels sent to printer')),
          ],
        ),
        _FilterBar(
          selected: _filter,
          filters: const ['All', 'Low Stock', 'Warehouse A', 'Batch Tracking'],
          onChanged: (value) => setState(() => _filter = value),
        ),
        _ProductGrid(
            products: products,
            onAdd: (product) => _toast('${product.name} opened')),
        const _GlassPanel(
          title: 'Warehouse Movement',
          child: _EnterpriseTable(
            columns: ['SKU', 'Product', 'Batch', 'Warehouse', 'Qty', 'Alert'],
            rows: [
              ['P-1001', 'iPhone 15 Pro', 'IP15-2605', 'Main', '24', 'Healthy'],
              ['P-1002', 'Boot Headphone', 'BH-991', 'Retail', '6', 'Low'],
              ['P-1003', 'Coca Cola', 'CC-0426', 'Kiosk', '84', 'Healthy'],
              ['P-1004', 'Nike Shoes', 'NS-7', 'Outlet', '4', 'Low'],
            ],
          ),
        ),
      ],
    );
  }
}

class CrmWorkspace extends StatefulWidget {
  const CrmWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<CrmWorkspace> createState() => _CrmWorkspaceState();
}

class _CrmWorkspaceState extends State<CrmWorkspace> {
  int _won = 2;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'CRM Relationship Desk',
          subtitle:
              'Leads, customers, followups, tasks, notes and sales pipeline.',
          actions: [
            _HeaderAction(
                icon: Icons.person_add,
                label: 'Lead',
                onTap: () => setState(() => _won++)),
            _HeaderAction(
                icon: Icons.task_alt,
                label: 'Task',
                onTap: () => _toast('Followup task scheduled')),
          ],
        ),
        _MetricGrid(metrics: [
          const _MetricData('Total Leads', '1,245', '+12.5%', Icons.groups,
              Color(0xFF22C55E)),
          const _MetricData('Conversions', '366', '+10.3%', Icons.check_circle,
              Color(0xFF38BDF8)),
          _MetricData('Won Deals', '$_won', 'live', Icons.workspace_premium,
              const Color(0xFFF59E0B)),
          const _MetricData('Revenue', 'Rs 25,43,210', '+8%', Icons.payments,
              Color(0xFF6366F1)),
        ]),
        _Kanban(
            columns: const ['New', 'Contacted', 'Qualified', 'Won'],
            accent: const Color(0xFF22C55E)),
      ],
    );
  }
}

class EcommerceWorkspace extends StatefulWidget {
  const EcommerceWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<EcommerceWorkspace> createState() => _EcommerceWorkspaceState();
}

class _EcommerceWorkspaceState extends State<EcommerceWorkspace> {
  int _cart = 1;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'eCommerce Storefront',
          subtitle:
              'Product listing, cart, wishlist, coupons, checkout, orders, tracking and reviews.',
          actions: [
            _HeaderAction(
                icon: Icons.local_offer,
                label: 'Coupon',
                onTap: () => _toast('SUMMER20 coupon enabled')),
            _HeaderAction(
                icon: Icons.storefront,
                label: 'Preview',
                onTap: () => _toast('Customer storefront preview opened')),
          ],
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 900;
            final store = _GlassPanel(
              title: 'Customer App',
              trailing: _LiveChip(
                  label: 'Cart $_cart', color: const Color(0xFFF43F5E)),
              child: Column(
                children: [
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF43F5E).withValues(alpha: 0.18),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text('Summer Sale - up to 30% off',
                        style: TextStyle(
                            fontSize: 22, fontWeight: FontWeight.w900)),
                  ),
                  const SizedBox(height: 14),
                  _ProductGrid(onAdd: (_) => setState(() => _cart++)),
                ],
              ),
            );
            final order = _GlassPanel(
              title: 'Live Orders',
              child: Column(
                children: [
                  _ReportTile(
                      'Order #1052',
                      'Packed - BlueDart tracking assigned',
                      Icons.local_shipping),
                  _ReportTile('Order #1053', 'Paid - waiting for invoice',
                      Icons.receipt_long),
                  _ReportTile('Return #88', 'Review requested by customer',
                      Icons.assignment_return),
                ],
              ),
            );
            if (compact)
              return Column(
                  children: [store, const SizedBox(height: 14), order]);
            return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(flex: 7, child: store),
              const SizedBox(width: 14),
              Expanded(flex: 4, child: order),
            ]);
          },
        ),
      ],
    );
  }
}

class ProcurementWorkspace extends StatelessWidget {
  const ProcurementWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: module,
          title: 'B2B Vendor and Purchase Portal',
          subtitle:
              'Supplier quotes, purchase orders, invoices, payments, vendor portal and stock receipts.',
        ),
        _Kanban(
            columns: const ['Requests', 'Quotes', 'POs', 'Receipts'],
            accent: const Color(0xFFF59E0B)),
        const _GlassPanel(
          title: 'Supplier Price Comparison',
          child: _EnterpriseTable(
            columns: ['Product', 'Vendor A', 'Vendor B', 'Best', 'ETA'],
            rows: [
              ['iPhone 15 Pro', 'Rs 1,29,000', 'Rs 1,27,500', 'Vendor B', '2d'],
              ['Boat Headphone', 'Rs 2,199', 'Rs 2,099', 'Vendor B', '1d'],
              ['MacBook Air M2', 'Rs 94,000', 'Rs 95,500', 'Vendor A', '3d'],
            ],
          ),
        ),
      ],
    );
  }
}

class HrmWorkspace extends StatelessWidget {
  const HrmWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
            module: module,
            title: 'HRM Workforce',
            subtitle:
                'Attendance, payroll, roles, permissions, shifts, leave and employee tasks.'),
        _MetricGrid(metrics: const [
          _MetricData('Employees', '86', '+4', Icons.badge, Color(0xFFF472B6)),
          _MetricData(
              'Present', '72', 'live', Icons.how_to_reg, Color(0xFF22C55E)),
          _MetricData(
              'Payroll', 'Rs 8.2L', 'ready', Icons.payments, Color(0xFF6366F1)),
          _MetricData('Leave Requests', '9', 'review', Icons.event_busy,
              Color(0xFFF59E0B)),
        ]),
        _Kanban(
            columns: const ['Attendance', 'Payroll', 'Hiring', 'Tasks'],
            accent: const Color(0xFFF472B6)),
      ],
    );
  }
}

class ReportsWorkspace extends StatelessWidget {
  const ReportsWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: module,
          title: 'Reports and Analytics',
          subtitle:
              'Sales, GST, expenses, inventory, CRM, HRM and downloadable PDF/Excel reports.',
          actions: [
            _HeaderAction(
                icon: Icons.picture_as_pdf,
                label: 'PDF',
                onTap: () => _toast('PDF export generated')),
            _HeaderAction(
                icon: Icons.table_view,
                label: 'Excel',
                onTap: () => _toast('Excel export generated')),
          ],
        ),
        LayoutBuilder(builder: (context, constraints) {
          final compact = constraints.maxWidth < 980;
          final chart = const _GlassPanel(
              title: 'Sales By Category', child: _DonutChart());
          final table = const _GlassPanel(
            title: 'Top Reports',
            child: _EnterpriseTable(
              columns: ['Report', 'Period', 'Status', 'Export'],
              rows: [
                ['Sales Summary', 'This Month', 'Ready', 'PDF/XLS'],
                ['GST Report', 'Q1', 'Review', 'PDF/XLS'],
                ['Inventory Valuation', 'Today', 'Ready', 'PDF/XLS'],
                ['Expense Report', 'This Week', 'Ready', 'PDF/XLS'],
              ],
            ),
          );
          if (compact)
            return Column(children: [chart, const SizedBox(height: 14), table]);
          return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(flex: 4, child: chart),
            const SizedBox(width: 14),
            Expanded(flex: 7, child: table),
          ]);
        }),
      ],
    );
  }
}

class AdminBuilderWorkspace extends StatefulWidget {
  const AdminBuilderWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<AdminBuilderWorkspace> createState() => _AdminBuilderWorkspaceState();
}

class _AdminBuilderWorkspaceState extends State<AdminBuilderWorkspace> {
  final List<String> _blocks = ['KPI Cards', 'Sales Chart', 'Realtime Orders'];
  bool _posEnabled = true;
  bool _crmEnabled = true;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'Super Admin Builder',
          subtitle:
              'Drag-drop dashboard, widgets, dynamic pages, forms, tables, themes and feature toggles.',
          actions: [
            _HeaderAction(
                icon: Icons.visibility,
                label: 'Preview',
                onTap: () => _toast('Live preview refreshed')),
            _HeaderAction(
                icon: Icons.save,
                label: 'Publish',
                onTap: () => _toast('Runtime config published')),
          ],
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 900;
            final builder = _GlassPanel(
              title: 'Dashboard Builder',
              child: Column(
                children: [
                  for (final block in _blocks)
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.drag_indicator),
                        title: Text(block,
                            style:
                                const TextStyle(fontWeight: FontWeight.w900)),
                        trailing: IconButton(
                          tooltip: 'Remove block',
                          onPressed: () =>
                              setState(() => _blocks.remove(block)),
                          icon: const Icon(Icons.close),
                        ),
                      ),
                    ),
                  const SizedBox(height: 10),
                  FilledButton.icon(
                    onPressed: () => setState(() =>
                        _blocks.add('Dynamic Table ${_blocks.length + 1}')),
                    icon: const Icon(Icons.add_box),
                    label: const Text('Add Block'),
                  ),
                ],
              ),
            );
            final toggles = _GlassPanel(
              title: 'Feature Control',
              child: Column(
                children: [
                  SwitchListTile(
                    value: _posEnabled,
                    onChanged: (value) => setState(() => _posEnabled = value),
                    title: const Text('POS Module',
                        style: TextStyle(fontWeight: FontWeight.w900)),
                    subtitle:
                        const Text('Enable retail checkout for all stores'),
                  ),
                  SwitchListTile(
                    value: _crmEnabled,
                    onChanged: (value) => setState(() => _crmEnabled = value),
                    title: const Text('CRM Module',
                        style: TextStyle(fontWeight: FontWeight.w900)),
                    subtitle: const Text(
                        'Enable leads, followups and customer notes'),
                  ),
                  _ReportTile(
                      'Theme Builder',
                      'Brand color, radius, density and dark/light mode',
                      Icons.palette),
                  _ReportTile(
                      'Role Manager',
                      'RBAC permissions and store access',
                      Icons.admin_panel_settings),
                ],
              ),
            );
            if (compact)
              return Column(
                  children: [builder, const SizedBox(height: 14), toggles]);
            return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(flex: 7, child: builder),
              const SizedBox(width: 14),
              Expanded(flex: 4, child: toggles),
            ]);
          },
        ),
      ],
    );
  }
}

class ApiManagementWorkspace extends StatefulWidget {
  const ApiManagementWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  State<ApiManagementWorkspace> createState() => _ApiManagementWorkspaceState();
}

class _ApiManagementWorkspaceState extends State<ApiManagementWorkspace> {
  bool _mock = false;
  String _env = 'Local';
  String _status = 'Idle';

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
          module: widget.module,
          title: 'API Management',
          subtitle:
              'Switch live/local API, test endpoints, inspect responses, view logs and WebSocket sync.',
        ),
        _GlassPanel(
          title: 'Environment Switcher',
          child: Column(
            children: [
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                      value: 'Local',
                      label: Text('Local'),
                      icon: Icon(Icons.laptop)),
                  ButtonSegment(
                      value: 'Production',
                      label: Text('Prod'),
                      icon: Icon(Icons.cloud_done)),
                  ButtonSegment(
                      value: 'Staging',
                      label: Text('Stage'),
                      icon: Icon(Icons.science)),
                ],
                selected: {_env},
                onSelectionChanged: (value) =>
                    setState(() => _env = value.first),
              ),
              SwitchListTile(
                value: _mock,
                onChanged: (value) => setState(() => _mock = value),
                title: const Text('Mock API',
                    style: TextStyle(fontWeight: FontWeight.w900)),
                subtitle:
                    const Text('Use demo payloads while backend is offline'),
              ),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _testApi,
                      icon: const Icon(Icons.bolt),
                      label: const Text('Test API'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => setState(() => _status =
                          'WebSocket connected: ws://localhost:8000/ws/enterprise/'),
                      icon: const Icon(Icons.settings_input_antenna),
                      label: const Text('Test WebSocket'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        _GlassPanel(
          title: 'Response Inspector',
          trailing: _LiveChip(label: _env, color: const Color(0xFF38BDF8)),
          child: Text(
            '{\n  "environment": "$_env",\n  "mock": $_mock,\n  "status": "$_status",\n  "latency_ms": 42,\n  "sync": "realtime-ready"\n}',
            style: const TextStyle(fontFamily: 'monospace', height: 1.45),
          ),
        ),
      ],
    );
  }

  Future<void> _testApi() async {
    setState(() => _status = 'Testing /api/system/app-config/');
    await Future<void>.delayed(const Duration(milliseconds: 620));
    setState(() => _status = '200 OK - 18 modules, 9 widgets, 4 roles');
    _toast('API test successful');
  }
}

class PortalWorkspace extends StatelessWidget {
  const PortalWorkspace({super.key, required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    final isBuild = module.key == 'apk_builder';
    return _ModuleScroll(
      children: [
        _Header(
          module: module,
          title: isBuild ? 'APK Build and OTA Center' : module.title,
          subtitle: isBuild
              ? 'Generate APK, release builds, version control, downloads and OTA update rollout.'
              : 'Role-specific portal with connected orders, payments, tracking and notifications.',
          actions: [
            _HeaderAction(
              icon: isBuild ? Icons.android : Icons.open_in_new,
              label: isBuild ? 'Build' : 'Open',
              onTap: () => _toast(isBuild
                  ? 'APK build queued: v1.0.1+2'
                  : '${module.title} opened'),
            ),
          ],
        ),
        _MetricGrid(metrics: [
          _MetricData(isBuild ? 'Builds' : 'Active Users',
              isBuild ? '18' : '4,208', '+12%', Icons.groups, module.color),
          _MetricData(
              isBuild ? 'Latest APK' : 'Orders',
              isBuild ? 'v1.0.1' : '286',
              'live',
              Icons.shopping_bag,
              const Color(0xFF22C55E)),
          _MetricData(
              isBuild ? 'OTA Cohort' : 'Payments',
              isBuild ? '25%' : 'Rs 9.2L',
              'ready',
              Icons.system_update_alt,
              const Color(0xFFF59E0B)),
        ]),
        _Kanban(
          columns: isBuild
              ? const ['Queued', 'Building', 'Signed', 'Released']
              : const ['New', 'Active', 'Waiting', 'Done'],
          accent: module.color,
        ),
      ],
    );
  }
}

class GenericWorkspace extends StatelessWidget {
  const GenericWorkspace(
      {super.key, required this.module, required this.workspace});

  final EnterpriseModule module;
  final EnterpriseWorkspace workspace;

  @override
  Widget build(BuildContext context) {
    return _ModuleScroll(
      children: [
        _Header(
            module: module,
            title: module.title,
            subtitle: '${workspace.name} runtime route ${module.route}.'),
        _FilterBar(
            selected: 'All',
            filters: const ['All', 'Active', 'Draft', 'Archived'],
            onChanged: (_) {}),
        _GlassPanel(
          title: '${module.title} Records',
          child: const _EnterpriseTable(
            columns: ['ID', 'Name', 'Owner', 'Status', 'Updated'],
            rows: [
              ['100001', 'Multi business workspace', 'Admin', 'Active', 'now'],
              ['100002', 'Store setup', 'Manager', 'Review', '10:20'],
              ['100003', 'Realtime task', 'System', 'Synced', '10:24'],
            ],
          ),
        ),
      ],
    );
  }
}

class _ModuleScroll extends StatelessWidget {
  const _ModuleScroll({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: EnterpriseBreakpoints.pagePadding(context).copyWith(bottom: 112),
      itemCount: children.length,
      separatorBuilder: (_, __) => const SizedBox(height: 14),
      itemBuilder: (context, index) => children[index],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.module,
    required this.title,
    required this.subtitle,
    this.actions = const [],
  });

  final EnterpriseModule module;
  final String title;
  final String subtitle;
  final List<_HeaderAction> actions;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 8,
      opacity: 0.78,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 640;
          final copy = Row(
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: module.color.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(EnterpriseIcons.fromName(module.icon),
                    color: module.color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w900),
                    ),
                    Text(
                      subtitle,
                      maxLines: compact ? 3 : 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ],
                ),
              ),
            ],
          );
          final actionRow = Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final action in actions)
                Tooltip(
                  message: action.label,
                  child: IconButton.filledTonal(
                      onPressed: action.onTap, icon: Icon(action.icon)),
                ),
              IconButton.filled(
                tooltip: 'Create',
                onPressed: () => _toast('${module.title} create action ready'),
                icon: const Icon(Icons.add),
              ),
            ],
          );
          if (compact) {
            return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [copy, const SizedBox(height: 12), actionRow]);
          }
          return Row(children: [
            Expanded(child: copy),
            const SizedBox(width: 12),
            actionRow
          ]);
        },
      ),
    );
  }
}

class _HeaderAction {
  const _HeaderAction(
      {required this.icon, required this.label, required this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback onTap;
}

class _GlassPanel extends StatelessWidget {
  const _GlassPanel({required this.title, required this.child, this.trailing});

  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 8,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w900),
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.metrics});

  final List<_MetricData> metrics;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final columns = constraints.maxWidth > 980
          ? 4
          : constraints.maxWidth > 560
              ? 2
              : 1;
      return GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: metrics.length,
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: columns,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          mainAxisExtent: 116,
        ),
        itemBuilder: (context, index) {
          final metric = metrics[index];
          return EnterpriseGlass(
            radius: 8,
            opacity: 0.74,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(metric.icon, color: metric.color),
                  const Spacer(),
                  Text(metric.delta,
                      style: TextStyle(
                          color: metric.color, fontWeight: FontWeight.w900))
                ]),
                const Spacer(),
                Text(metric.value,
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: metric.color, fontWeight: FontWeight.w900)),
                Text(metric.label,
                    style: const TextStyle(color: Colors.white70)),
              ],
            ),
          );
        },
      );
    });
  }
}

class _MetricData {
  const _MetricData(this.label, this.value, this.delta, this.icon, this.color);

  final String label;
  final String value;
  final String delta;
  final IconData icon;
  final Color color;
}

class _FilterBar extends StatelessWidget {
  const _FilterBar(
      {required this.selected, required this.filters, required this.onChanged});

  final String selected;
  final List<String> filters;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 42,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: filters.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final filter = filters[index];
          return ChoiceChip(
            selected: selected == filter,
            label: Text(filter),
            onSelected: (_) => onChanged(filter),
          );
        },
      ),
    );
  }
}

class _ProductGrid extends StatelessWidget {
  const _ProductGrid({this.products = _demoProducts, required this.onAdd});

  final List<_DemoProduct> products;
  final ValueChanged<_DemoProduct> onAdd;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final columns = constraints.maxWidth > 980
          ? 4
          : constraints.maxWidth > 620
              ? 3
              : 2;
      return GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: products.length,
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: columns,
          crossAxisSpacing: 10,
          mainAxisSpacing: 10,
          mainAxisExtent: 172,
        ),
        itemBuilder: (context, index) {
          final product = products[index];
          return Card(
            child: InkWell(
              onTap: () => onAdd(product),
              borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 46,
                          height: 42,
                          decoration: BoxDecoration(
                            color: product.color.withValues(alpha: 0.18),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Icon(product.icon, color: product.color),
                        ),
                        const Spacer(),
                        Text(_money(product.price),
                            style:
                                const TextStyle(fontWeight: FontWeight.w900)),
                      ],
                    ),
                    const Spacer(),
                    Text(product.sku,
                        style: const TextStyle(
                            color: Colors.white54, fontSize: 12)),
                    Text(product.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w900)),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: product.stock.clamp(0, 100) / 100,
                      color: product.stock < 10
                          ? const Color(0xFFFB7185)
                          : const Color(0xFF22C55E),
                      backgroundColor: Colors.white10,
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      );
    });
  }
}

class _CartLineTile extends StatelessWidget {
  const _CartLineTile(
      {required this.line,
      required this.onMinus,
      required this.onPlus,
      required this.onRemove});

  final _CartLine line;
  final VoidCallback onMinus;
  final VoidCallback onPlus;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
          backgroundColor: line.product.color.withValues(alpha: 0.16),
          child: Icon(line.product.icon, color: line.product.color)),
      title: Text(line.product.name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text(_money(line.product.price)),
      trailing: Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 4,
        children: [
          IconButton.filledTonal(
              tooltip: 'Decrease',
              onPressed: onMinus,
              icon: const Icon(Icons.remove)),
          Text('${line.qty}',
              style: const TextStyle(fontWeight: FontWeight.w900)),
          IconButton.filledTonal(
              tooltip: 'Increase',
              onPressed: onPlus,
              icon: const Icon(Icons.add)),
          IconButton(
              tooltip: 'Remove',
              onPressed: onRemove,
              icon: const Icon(Icons.close)),
        ],
      ),
    );
  }
}

class _EnterpriseTable extends StatelessWidget {
  const _EnterpriseTable({required this.columns, required this.rows});

  final List<String> columns;
  final List<List<String>> rows;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: DataTable(
        headingRowColor:
            WidgetStatePropertyAll(Colors.white.withValues(alpha: 0.06)),
        columns: [
          for (final column in columns) DataColumn(label: Text(column))
        ],
        rows: [
          for (final row in rows)
            DataRow(cells: [for (final cell in row) DataCell(Text(cell))]),
        ],
      ),
    );
  }
}

class _Kanban extends StatelessWidget {
  const _Kanban({required this.columns, required this.accent});

  final List<String> columns;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 430,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: columns.length,
        separatorBuilder: (_, __) => const SizedBox(width: 12),
        itemBuilder: (context, index) {
          final column = columns[index];
          return SizedBox(
            width: 292,
            child: _GlassPanel(
              title: column,
              trailing: CircleAvatar(
                  radius: 13,
                  backgroundColor: accent.withValues(alpha: 0.18),
                  child: Text('${index + 2}',
                      style: TextStyle(color: accent, fontSize: 12))),
              child: Column(
                children: [
                  for (var i = 0; i < 3; i++)
                    Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      child: ListTile(
                        title: Text('$column record ${i + 1}',
                            style:
                                const TextStyle(fontWeight: FontWeight.w900)),
                        subtitle: Text('Owner Admin - SLA ${i + 1}h'),
                        trailing: Icon(Icons.drag_indicator, color: accent),
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _DonutChart extends StatelessWidget {
  const _DonutChart();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 250,
      child: PieChart(
        PieChartData(
          centerSpaceRadius: 58,
          sections: [
            PieChartSectionData(
                value: 45, color: Color(0xFF6366F1), title: '45%'),
            PieChartSectionData(
                value: 25, color: Color(0xFF38BDF8), title: '25%'),
            PieChartSectionData(
                value: 20, color: Color(0xFFF59E0B), title: '20%'),
            PieChartSectionData(
                value: 10, color: Color(0xFF22C55E), title: '10%'),
          ],
        ),
      ),
    );
  }
}

class _ReportTile extends StatelessWidget {
  const _ReportTile(this.title, this.subtitle, this.icon);

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
      subtitle: Text(subtitle),
      trailing: IconButton(
          tooltip: 'Open',
          onPressed: () => _toast('$title opened'),
          icon: const Icon(Icons.chevron_right)),
    );
  }
}

class _LiveChip extends StatelessWidget {
  const _LiveChip({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(Icons.circle, size: 10, color: color),
      label: Text(label),
    );
  }
}

class _TotalRow extends StatelessWidget {
  const _TotalRow(
      {required this.label, required this.value, this.strong = false});

  final String label;
  final String value;
  final bool strong;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value,
              style: TextStyle(
                  fontSize: strong ? 22 : 14,
                  fontWeight: strong ? FontWeight.w900 : FontWeight.w700)),
        ],
      ),
    );
  }
}

class _DemoProduct {
  const _DemoProduct(
      this.sku, this.name, this.price, this.stock, this.icon, this.color);

  final String sku;
  final String name;
  final double price;
  final int stock;
  final IconData icon;
  final Color color;
}

class _CartLine {
  _CartLine(this.product, this.qty);

  final _DemoProduct product;
  int qty;

  double get total => product.price * qty;
}

const _demoProducts = [
  _DemoProduct('P-1001', 'iPhone 15 Pro', 135900, 24, Icons.phone_iphone,
      Color(0xFF94A3B8)),
  _DemoProduct('P-1002', 'Samsung S24 Ultra', 70999, 18, Icons.smartphone,
      Color(0xFF60A5FA)),
  _DemoProduct(
      'P-1003', 'Boot Headphone', 2499, 6, Icons.headphones, Color(0xFF38BDF8)),
  _DemoProduct(
      'P-1004', 'Fossil Watch', 5409, 12, Icons.watch, Color(0xFFF59E0B)),
  _DemoProduct(
      'P-1005', 'Coca Cola', 50, 84, Icons.local_drink, Color(0xFFEF4444)),
  _DemoProduct(
      'P-1006', 'Nike Shoes', 4009, 4, Icons.shopping_bag, Color(0xFF22C55E)),
];

String _money(num value) {
  final raw = value.round().toString();
  if (raw.length <= 3) return 'Rs $raw';
  final lastThree = raw.substring(raw.length - 3);
  var prefix = raw.substring(0, raw.length - 3);
  final groups = <String>[];
  while (prefix.length > 2) {
    groups.insert(0, prefix.substring(prefix.length - 2));
    prefix = prefix.substring(0, prefix.length - 2);
  }
  if (prefix.isNotEmpty) groups.insert(0, prefix);
  return 'Rs ${groups.join(',')},$lastThree';
}

void _toast(String message) {
  Get.snackbar(
    'Action complete',
    message,
    snackPosition: SnackPosition.BOTTOM,
    margin: const EdgeInsets.all(14),
    duration: const Duration(seconds: 2),
  );
}
