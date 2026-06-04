import 'package:flutter/material.dart';

import '../../core/responsive/enterprise_breakpoints.dart';
import '../../models/enterprise_app_config.dart';
import '../../permissions/permission_engine.dart';
import '../../screens/settings/settings_screen.dart';
import '../../widgets/enterprise/enterprise_glass.dart';
import '../../widgets/enterprise/enterprise_icons.dart';
import 'dynamic_runtime_module_screen.dart';

class DynamicModuleScreen extends StatelessWidget {
  const DynamicModuleScreen({
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
      return const Center(child: Text('This module is not available for your role.'));
    }
    final runtimeMode = (module.settings['mode'] ?? '').toString();
    final modelKey = (module.settings['model_key'] ?? module.settings['model'] ?? '').toString();
    final specialized = {'dashboard', 'pos', 'selfcheckout', 'reports', 'settings'}.contains(module.key) ||
        {'dashboard', 'pos', 'kiosk', 'reports'}.contains(runtimeMode);
    if (!specialized && (modelKey.isNotEmpty ||
        runtimeMode == 'dynamic' ||
        !{'dashboard', 'pos', 'billing', 'selfcheckout', 'reports', 'settings'}.contains(module.key))) {
      return DynamicRuntimeModuleScreen(
        module: module,
        permissionEngine: permissionEngine,
      );
    }
    return switch (module.key) {
      'company' => _CompanyWorkspace(module: module),
      'products' || 'inventory' => _InventoryWorkspace(module: module),
      'ledger' => _LedgerWorkspace(module: module),
      'website' => _WebsiteWorkspace(module: module),
      'pos' || 'billing' || 'selfcheckout' => _PosBillingWorkspace(module: module),
      'crm' => _PipelineWorkspace(
          module: module,
          title: 'CRM Relationship Desk',
          columns: const ['New', 'Qualified', 'Proposal', 'Won'],
          accent: const Color(0xFF38BDF8),
        ),
      'ecommerce' => _PipelineWorkspace(
          module: module,
          title: 'Ecommerce Control Room',
          columns: const ['Storefront', 'Catalog', 'Orders', 'Returns'],
          accent: const Color(0xFFFB7185),
        ),
      'suppliers' || 'purchases' => _PipelineWorkspace(
          module: module,
          title: 'Supplier and Procurement Hub',
          columns: const ['Requests', 'Quotes', 'POs', 'Receipts'],
          accent: const Color(0xFFF59E0B),
        ),
      'hrm' => _PipelineWorkspace(
          module: module,
          title: 'HRM Staff Workspace',
          columns: const ['Attendance', 'Payroll', 'Roles', 'Tasks'],
          accent: const Color(0xFFF472B6),
        ),
      'settings' => const SettingsScreen(),
      _ => _GenericEnterpriseWorkspace(module: module, workspace: workspace),
    };
  }
}

class _WorkspaceList extends StatelessWidget {
  const _WorkspaceList({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: EnterpriseBreakpoints.pagePadding(context).copyWith(bottom: 110),
      itemCount: children.length,
      separatorBuilder: (_, __) => const SizedBox(height: 14),
      itemBuilder: (context, index) => children[index],
    );
  }
}

class _CompanyWorkspace extends StatelessWidget {
  const _CompanyWorkspace({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _WorkspaceList(
      children: [
        _ModuleHeader(
          module: module,
          title: 'Organization Company',
          subtitle: 'Company profile, branches, employees, websites, taxes and payment methods.',
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 900;
            final profile = _ProfileForm(module: module);
            final settings = _SettingsStack(module: module);
            return compact
                ? Column(children: [profile, const SizedBox(height: 14), settings])
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 6, child: profile),
                      const SizedBox(width: 14),
                      Expanded(flex: 5, child: settings),
                    ],
                  );
          },
        ),
      ],
    );
  }
}

class _ProfileForm extends StatelessWidget {
  const _ProfileForm({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 116,
                height: 92,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Center(
                  child: Text('GrowERP',
                      style: TextStyle(
                          color: Color(0xFF166534),
                          fontSize: 20,
                          fontWeight: FontWeight.w900)),
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: const [
                    _QuickIcon(icon: Icons.image, label: 'Logo'),
                    _QuickIcon(icon: Icons.camera_alt, label: 'Capture'),
                    _QuickIcon(icon: Icons.palette, label: 'Brand'),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          const _FieldRow(label: 'ID', value: '100001'),
          const _FieldRow(label: 'Company Name', value: 'Test Company'),
          const _FieldRow(label: 'Telephone', value: 'United States / +1'),
          const _FieldRow(label: 'Email address', value: 'test13@example.com'),
          const _FieldRow(label: 'Web address', value: '100459.localhost:8080'),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _MiniSetting(title: 'VAT percentage', value: '0')),
              const SizedBox(width: 10),
              Expanded(child: _MiniSetting(title: 'Sales Tax', value: '0')),
            ],
          ),
        ],
      ),
    );
  }
}

class _SettingsStack extends StatelessWidget {
  const _SettingsStack({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: const [
        _PanelList(
          title: 'Enterprise Control',
          items: ['Employees and roles', 'Branches and warehouses', 'Billing settings'],
        ),
        SizedBox(height: 14),
        _PanelList(
          title: 'Finance Setup',
          items: ['Tax rules', 'Payment methods', 'API keys and webhooks'],
        ),
      ],
    );
  }
}

class _InventoryWorkspace extends StatelessWidget {
  const _InventoryWorkspace({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _WorkspaceList(
      children: [
        _ModuleHeader(
          module: module,
          title: 'Catalog Products',
          subtitle: 'Barcode-ready product grid, stock alerts, warehouses and bulk actions.',
        ),
        _SearchActionBar(module: module, hint: 'Search products, SKU, barcode...'),
        LayoutBuilder(
          builder: (context, constraints) {
            final count = constraints.maxWidth > 1000
                ? 4
                : constraints.maxWidth > 720
                    ? 3
                    : 2;
            return GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: _products.length,
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: count,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                mainAxisExtent: 196,
              ),
              itemBuilder: (context, index) => _ProductTile(product: _products[index]),
            );
          },
        ),
        _DataTablePanel(
          title: 'Warehouse Stock Movement',
          columns: const ['SKU', 'Product', 'Warehouse', 'Qty', 'Alert'],
          rows: const [
            ['100007', '32GB USB Drive', 'Main', '42', 'Healthy'],
            ['100008', 'Coffee Mug', 'Retail', '3', 'Low'],
            ['100002', 'Deluxe room', 'Online', '8', 'Watch'],
            ['100005', 'Hoodie', 'Outlet', '2', 'Low'],
          ],
        ),
      ],
    );
  }
}

class _LedgerWorkspace extends StatelessWidget {
  const _LedgerWorkspace({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _WorkspaceList(
      children: [
        _ModuleHeader(
          module: module,
          title: 'Acct Ledger',
          subtitle: 'Ledger tree, account groups, transactions, GST reports and cash flow.',
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 900;
            final tree = _LedgerTree(module: module);
            final tx = _DataTablePanel(
              title: 'Realtime Transactions',
              columns: const ['Date', 'Account', 'Type', 'Amount', 'Status'],
              rows: const [
                ['2026-02-10', 'Trust Fund-c', 'Credit', 'Rs 0.00', 'Created'],
                ['2026-02-10', 'Academic Advantage-I', 'Debit', 'Rs 0.00', 'Created'],
                ['2026-02-10', 'Cash Drawer', 'Receipt', 'Rs 2,430', 'Posted'],
                ['2026-02-10', 'UPI Settlement', 'Bank', 'Rs 9,800', 'Posted'],
              ],
            );
            return compact
                ? Column(children: [tree, const SizedBox(height: 14), tx])
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(flex: 5, child: tree),
                      const SizedBox(width: 14),
                      Expanded(flex: 7, child: tx),
                    ],
                  );
          },
        ),
      ],
    );
  }
}

class _WebsiteWorkspace extends StatelessWidget {
  const _WebsiteWorkspace({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return _WorkspaceList(
      children: [
        _ModuleHeader(
          module: module,
          title: 'Organization Website',
          subtitle: 'Website settings, content blocks, dynamic menus, ecommerce links and SEO.',
        ),
        _SearchActionBar(module: module, hint: 'Search pages, content blocks, menus...'),
        const _PanelList(
          title: 'Website URLs',
          items: ['100459.localhost:8080', 'localhost:8080', 'Update domain mapping'],
        ),
        const _DataTablePanel(
          title: 'Pages and Quick Links',
          columns: ['Page', 'Route', 'Type', 'SEO', 'Status'],
          rows: [
            ['Admin', '/admin', 'Quick Link', 'Noindex', 'Active'],
            ['Assessment Landing', '/assessment-landing', 'Landing', 'Ready', 'Active'],
            ['Checkout Page', '/checkoutOnePage', 'Ecommerce', 'Ready', 'Active'],
            ['Help Center', '/help', 'Support', 'Draft', 'Review'],
          ],
        ),
      ],
    );
  }
}

class _PosBillingWorkspace extends StatelessWidget {
  const _PosBillingWorkspace({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EnterpriseBreakpoints.pagePadding(context).copyWith(bottom: 110),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 980;
          final catalog = _TouchCatalog(module: module);
          final cart = _CartPanel(module: module);
          return compact
              ? ListView(children: [catalog, const SizedBox(height: 14), cart])
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 7, child: catalog),
                    const SizedBox(width: 14),
                    Expanded(flex: 4, child: cart),
                  ],
                );
        },
      ),
    );
  }
}

class _PipelineWorkspace extends StatelessWidget {
  const _PipelineWorkspace({
    required this.module,
    required this.title,
    required this.columns,
    required this.accent,
  });

  final EnterpriseModule module;
  final String title;
  final List<String> columns;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return _WorkspaceList(
      children: [
        _ModuleHeader(module: module, title: title, subtitle: 'Drag workflow cards across backend-controlled states.'),
        SizedBox(
          height: 460,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: columns.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (context, index) => SizedBox(
              width: 292,
              child: EnterpriseGlass(
                radius: 10,
                opacity: 0.76,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(columns[index],
                              style: const TextStyle(fontWeight: FontWeight.w900)),
                        ),
                        CircleAvatar(
                          radius: 13,
                          backgroundColor: accent.withValues(alpha: 0.16),
                          child: Text('${index + 2}',
                              style: TextStyle(color: accent, fontSize: 12)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    for (var i = 0; i < 3; i++)
                      _PipelineCard(
                        title: '${columns[index]} record ${i + 1}',
                        subtitle: 'Owner: Demotest3 - SLA ${i + 1}h',
                        accent: accent,
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _GenericEnterpriseWorkspace extends StatelessWidget {
  const _GenericEnterpriseWorkspace({required this.module, required this.workspace});

  final EnterpriseModule module;
  final EnterpriseWorkspace workspace;

  @override
  Widget build(BuildContext context) {
    return _WorkspaceList(
      children: [
        _ModuleHeader(
          module: module,
          title: module.title,
          subtitle: '${workspace.name} uses ${module.route} and ${module.webUrl}.',
        ),
        _SearchActionBar(module: module, hint: 'Search records...'),
        _DataTablePanel(
          title: '${module.title} Records',
          columns: const ['ID', 'Name', 'Owner', 'Status', 'Updated'],
          rows: const [
            ['100000', 'Trust Fund-c', 'Demotest3', 'Created', '10:25'],
            ['100001', 'Academic Advantage-I', 'Staff', 'Active', '10:26'],
            ['100002', 'Retail branch task', 'Agent', 'Review', '10:29'],
          ],
        ),
      ],
    );
  }
}

class _ModuleHeader extends StatelessWidget {
  const _ModuleHeader({
    required this.module,
    required this.title,
    required this.subtitle,
  });

  final EnterpriseModule module;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.78,
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: module.color.withValues(alpha: 0.16),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(EnterpriseIcons.fromName(module.icon), color: module.color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.w900)),
                Text(subtitle,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white70)),
              ],
            ),
          ),
          IconButton.filledTonal(
            tooltip: 'Create',
            onPressed: () {},
            icon: const Icon(Icons.add),
          ),
        ],
      ),
    );
  }
}

class _SearchActionBar extends StatelessWidget {
  const _SearchActionBar({required this.module, required this.hint});

  final EnterpriseModule module;
  final String hint;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.72,
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              decoration: InputDecoration(
                hintText: hint,
                prefixIcon: const Icon(Icons.search),
              ),
            ),
          ),
          const SizedBox(width: 10),
          IconButton.filledTonal(
            tooltip: 'Barcode',
            onPressed: () {},
            icon: const Icon(Icons.qr_code_scanner),
          ),
          const SizedBox(width: 8),
          IconButton.filledTonal(
            tooltip: 'Bulk actions',
            onPressed: () {},
            icon: const Icon(Icons.select_all),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            tooltip: 'Add',
            onPressed: () {},
            icon: const Icon(Icons.add),
          ),
        ],
      ),
    );
  }
}

class _ProductTile extends StatelessWidget {
  const _ProductTile({required this.product});

  final _Product product;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.72,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 54,
                height: 44,
                decoration: BoxDecoration(
                  color: product.color.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(product.icon, color: product.color),
              ),
              const Spacer(),
              Text(product.price, style: const TextStyle(fontWeight: FontWeight.w900)),
            ],
          ),
          const Spacer(),
          Text(product.sku, style: const TextStyle(color: Colors.white54, fontSize: 12)),
          Text(product.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          LinearProgressIndicator(
            value: product.stock / 100,
            color: product.stock < 12 ? const Color(0xFFFB7185) : const Color(0xFF34D399),
            backgroundColor: Colors.white10,
          ),
          const SizedBox(height: 4),
          Text('${product.stock} in stock',
              style: TextStyle(
                  color: product.stock < 12 ? const Color(0xFFFB7185) : Colors.white60,
                  fontSize: 12)),
        ],
      ),
    );
  }
}

class _LedgerTree extends StatelessWidget {
  const _LedgerTree({required this.module});

  final EnterpriseModule module;

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
              Text('GL Account Tree',
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w900)),
              const Spacer(),
              OutlinedButton(onPressed: () {}, child: const Text('Expand All')),
            ],
          ),
          const SizedBox(height: 12),
          for (final row in const [
            ['10000', 'Asset Root', 'Rs 0.00'],
            ['20000', 'Liability', 'Rs 0.00'],
            ['30000', 'Owners Equity', 'Rs 0.00'],
            ['40000', 'Sales', 'Rs 0.00'],
            ['50000', 'Cost of Sales', 'Rs 0.00'],
            ['60000', 'General Expense', 'Rs 0.00'],
            ['70000', 'Other Expense', 'Rs 0.00'],
            ['80000', 'Other Income Root', 'Rs 0.00'],
          ])
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.chevron_right),
              title: Text('${row[0]} ${row[1]}',
                  style: const TextStyle(fontWeight: FontWeight.w800)),
              trailing: Text(row[2]),
            ),
        ],
      ),
    );
  }
}

class _DataTablePanel extends StatelessWidget {
  const _DataTablePanel({
    required this.title,
    required this.columns,
    required this.rows,
  });

  final String title;
  final List<String> columns;
  final List<List<String>> rows;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              headingRowColor:
                  WidgetStatePropertyAll(Colors.white.withValues(alpha: 0.06)),
              columns: [for (final c in columns) DataColumn(label: Text(c))],
              rows: [
                for (final row in rows)
                  DataRow(cells: [for (final cell in row) DataCell(Text(cell))]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TouchCatalog extends StatelessWidget {
  const _TouchCatalog({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _ModuleHeader(module: module, title: 'Touch Billing', subtitle: 'Barcode, split payment, QR, thermal print and customer display.'),
          const SizedBox(height: 14),
          TextField(
            decoration: InputDecoration(
              hintText: 'Scan barcode or search item',
              prefixIcon: const Icon(Icons.qr_code_scanner),
              suffixIcon: IconButton(
                tooltip: 'Voice search',
                onPressed: () {},
                icon: const Icon(Icons.mic_none),
              ),
            ),
          ),
          const SizedBox(height: 14),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _products.length,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 10,
              mainAxisSpacing: 10,
              mainAxisExtent: 142,
            ),
            itemBuilder: (context, index) {
              final product = _products[index];
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(product.icon, color: product.color),
                      const Spacer(),
                      Text(product.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w900)),
                      Row(
                        children: [
                          Expanded(child: Text(product.price)),
                          IconButton.filled(
                            onPressed: () {},
                            icon: const Icon(Icons.add),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _CartPanel extends StatelessWidget {
  const _CartPanel({required this.module});

  final EnterpriseModule module;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.8,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Invoice Cart',
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 12),
          for (final row in const [
            ['Coffee Mug', '2 x Rs 6.99'],
            ['32GB USB Drive', '1 x Rs 18.99'],
            ['Hoodie', '1 x Rs 39.99'],
          ])
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(row[0], style: const TextStyle(fontWeight: FontWeight.w800)),
              subtitle: Text(row[1]),
              trailing: IconButton(
                tooltip: 'Remove',
                onPressed: () {},
                icon: const Icon(Icons.close),
              ),
            ),
          const Divider(),
          const _TotalRow(label: 'Subtotal', value: 'Rs 72.96'),
          const _TotalRow(label: 'Tax', value: 'Rs 0.00'),
          const _TotalRow(label: 'Total', value: 'Rs 72.96', strong: true),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.qr_code_2),
                  label: const Text('QR Pay'),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(
                tooltip: 'Split payment',
                onPressed: () {},
                icon: const Icon(Icons.call_split),
              ),
              const SizedBox(width: 8),
              IconButton.filledTonal(
                tooltip: 'Thermal print',
                onPressed: () {},
                icon: const Icon(Icons.print),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PanelList extends StatelessWidget {
  const _PanelList({required this.title, required this.items});

  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return EnterpriseGlass(
      radius: 10,
      opacity: 0.76,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: Theme.of(context)
                  .textTheme
                  .titleLarge
                  ?.copyWith(fontWeight: FontWeight.w900)),
          const SizedBox(height: 10),
          for (final item in items)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.check_circle, color: Color(0xFF34D399)),
              title: Text(item, style: const TextStyle(fontWeight: FontWeight.w800)),
              trailing: const Icon(Icons.chevron_right),
            ),
        ],
      ),
    );
  }
}

class _PipelineCard extends StatelessWidget {
  const _PipelineCard({required this.title, required this.subtitle, required this.accent});

  final String title;
  final String subtitle;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
        subtitle: Text(subtitle),
        trailing: Icon(Icons.drag_indicator, color: accent),
      ),
    );
  }
}

class _FieldRow extends StatelessWidget {
  const _FieldRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(color: Colors.white54, fontSize: 12)),
          const SizedBox(height: 4),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.only(bottom: 8),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Colors.white12)),
            ),
            child: Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}

class _MiniSetting extends StatelessWidget {
  const _MiniSetting({required this.title, required this.value});

  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(color: Colors.white54, fontSize: 12)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}

class _QuickIcon extends StatelessWidget {
  const _QuickIcon({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      child: IconButton.filledTonal(onPressed: () {}, icon: Icon(icon)),
    );
  }
}

class _TotalRow extends StatelessWidget {
  const _TotalRow({required this.label, required this.value, this.strong = false});

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
                fontWeight: strong ? FontWeight.w900 : FontWeight.w700,
              )),
        ],
      ),
    );
  }
}

class _Product {
  const _Product(this.sku, this.name, this.price, this.stock, this.icon, this.color);

  final String sku;
  final String name;
  final String price;
  final int stock;
  final IconData icon;
  final Color color;
}

const _products = [
  _Product('100007', '32GB USB Drive', 'Rs 18.99', 42, Icons.usb, Color(0xFF5EEAD4)),
  _Product('100006', 'Baseball Cap', 'Rs 19.90', 18, Icons.style, Color(0xFF60A5FA)),
  _Product('100008', 'Coffee Mug', 'Rs 6.99', 3, Icons.coffee, Color(0xFFF59E0B)),
  _Product('100002', 'Deluxe room', 'Rs 90.00', 8, Icons.hotel, Color(0xFFA78BFA)),
  _Product('100003', 'GrowERP demo movie', 'Rs 0.00', 100, Icons.movie, Color(0xFF34D399)),
  _Product('100005', 'Hoodie', 'Rs 39.99', 2, Icons.checkroom, Color(0xFFFB7185)),
];
