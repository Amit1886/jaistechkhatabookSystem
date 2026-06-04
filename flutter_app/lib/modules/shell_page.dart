import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../dynamic_ui/module_icon.dart';
import '../providers/erp_provider.dart';
import '../widgets/dashboard_view.dart';
import 'module_crud_page.dart';

class ShellPage extends StatefulWidget {
  const ShellPage({super.key});

  @override
  State<ShellPage> createState() => _ShellPageState();
}

class _ShellPageState extends State<ShellPage> {
  int index = 0;

  @override
  Widget build(BuildContext context) {
    final erp = context.watch<ErpProvider>();
    final navModules = erp.modules.take(4).toList();
    final current = index == 0 ? null : navModules[index - 1];

    return Scaffold(
      appBar: AppBar(
        title: Text(current?.name ?? 'JaisTech ERP'),
        actions: [
          IconButton(onPressed: () => erp.bootstrap(), icon: const Icon(Icons.sync_outlined), tooltip: 'Sync'),
          IconButton(onPressed: erp.toggleTheme, icon: const Icon(Icons.dark_mode_outlined), tooltip: 'Theme'),
        ],
      ),
      body: Row(
        children: [
          if (MediaQuery.sizeOf(context).width >= 900)
            NavigationRail(
              selectedIndex: index,
              onDestinationSelected: (value) => setState(() => index = value),
              labelType: NavigationRailLabelType.all,
              destinations: [
                const NavigationRailDestination(icon: Icon(Icons.dashboard_outlined), label: Text('Dashboard')),
                ...navModules.map((m) => NavigationRailDestination(icon: Icon(ModuleIcon.fromKey(m.key)), label: Text(m.name))),
              ],
            ),
          Expanded(child: index == 0 ? const DashboardView() : ModuleCrudPage(module: current!)),
        ],
      ),
      bottomNavigationBar: MediaQuery.sizeOf(context).width < 900
          ? NavigationBar(
              selectedIndex: index,
              onDestinationSelected: (value) => setState(() => index = value),
              destinations: [
                const NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Home'),
                ...navModules.map((m) => NavigationDestination(icon: Icon(ModuleIcon.fromKey(m.key)), label: m.name)),
              ],
            )
          : null,
    );
  }
}
