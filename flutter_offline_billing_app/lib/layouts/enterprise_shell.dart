import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/auth_controller.dart';
import '../controllers/enterprise_app_controller.dart';
import '../core/responsive/enterprise_breakpoints.dart';
import '../models/enterprise_app_config.dart';
import '../permissions/permission_engine.dart';
import '../widgets/enterprise/enterprise_glass.dart';
import '../widgets/enterprise/enterprise_icons.dart';
import '../widgets/enterprise/enterprise_runtime_components.dart';
import '../widgets/sync_status_chip.dart';
import '../workspaces/enterprise_workspace_renderer.dart';

class EnterpriseShell extends StatefulWidget {
  const EnterpriseShell({super.key});

  @override
  State<EnterpriseShell> createState() => _EnterpriseShellState();
}

class _EnterpriseShellState extends State<EnterpriseShell> {
  final _controller = Get.find<EnterpriseAppController>();
  bool _collapsed = false;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final config = _controller.config.value ?? EnterpriseAppConfig.fallback();
      final modules = config.visibleModules;
      final selected = _controller.selectedModule ??
          (modules.isNotEmpty ? modules.first : null);
      final device = EnterpriseBreakpoints.classify(context);
      final desktop = device == EnterpriseDeviceClass.desktop ||
          device == EnterpriseDeviceClass.ultrawide;
      final permissionEngine = PermissionEngine(config.permissions);

      return Scaffold(
        extendBody: true,
        backgroundColor: config.theme.darkSurface,
        body: Stack(
          children: [
            _EnterpriseBackdrop(config: config),
            Row(
              children: [
                if (desktop)
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    curve: Curves.easeOutCubic,
                    width: _collapsed ? 92 : 286,
                    child: _EnterpriseRail(
                      config: config,
                      modules: modules,
                      selected: selected,
                      collapsed: _collapsed,
                      onToggle: () => setState(() => _collapsed = !_collapsed),
                      onSelect: _controller.selectModule,
                    ),
                  ),
                Expanded(
                  child: SafeArea(
                    bottom: false,
                    child: Column(
                      children: [
                        _WorkspaceTopbar(
                          config: config,
                          selected: selected,
                          isLoading: _controller.isLoading.value,
                          onRefresh: () => _controller.refreshConfig(),
                          onCommand: () =>
                              _showCommandCenter(context, config, modules),
                          onLauncher: () =>
                              _showModuleLauncher(context, config, modules),
                        ),
                        _WorkspaceTabs(
                          modules: modules.take(desktop ? 8 : 5).toList(),
                          selected: selected,
                          onSelect: _controller.selectModule,
                        ),
                        Expanded(
                          child: AnimatedSwitcher(
                            duration: const Duration(milliseconds: 260),
                            switchInCurve: Curves.easeOutCubic,
                            switchOutCurve: Curves.easeInCubic,
                            child: selected == null
                                ? const _EmptyWorkspace()
                                : EnterpriseWorkspaceRenderer(
                                    key: ValueKey(
                                        '${config.workspace.key}:${selected.key}'),
                                    config: config,
                                    module: selected,
                                    permissionEngine: permissionEngine,
                                  ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
        floatingActionButton: _FloatingActionStack(
          accent: config.theme.accent,
          onAi: () => _showAiAssistant(context, config),
          onLauncher: () => _showModuleLauncher(context, config, modules),
        ),
        bottomNavigationBar: desktop
            ? null
            : _FloatingNavigation(
                modules: modules.take(5).toList(),
                selected: selected,
                onSelect: _controller.selectModule,
              ),
      );
    });
  }

  void _showModuleLauncher(
    BuildContext context,
    EnterpriseAppConfig config,
    List<EnterpriseModule> modules,
  ) {
    showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.all(20),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: EnterpriseGlass(
            opacity: 0.93,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.apps),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text('Module Launcher',
                          style: Theme.of(context)
                              .textTheme
                              .titleLarge
                              ?.copyWith(fontWeight: FontWeight.w900)),
                    ),
                    IconButton(
                      tooltip: 'Close',
                      onPressed: () => Navigator.pop(context),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                EnterpriseLauncherGrid(
                  items: config.launcher,
                  onLaunch: (item) {
                    for (final module in modules) {
                      if (module.key == item.key ||
                          module.route == item.route) {
                        Navigator.pop(context);
                        _controller.selectModule(module);
                        break;
                      }
                    }
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showCommandCenter(
    BuildContext context,
    EnterpriseAppConfig config,
    List<EnterpriseModule> modules,
  ) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      backgroundColor: const Color(0xFF0B1715),
      builder: (context) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 6, 18, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              autofocus: true,
              decoration: InputDecoration(
                hintText:
                    'Search modules, customers, invoices, ledger accounts...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: IconButton(
                  tooltip: 'Keyboard shortcut',
                  onPressed: () {},
                  icon: const Icon(Icons.keyboard_command_key),
                ),
              ),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final module in modules.take(10))
                  ActionChip(
                    avatar:
                        Icon(EnterpriseIcons.fromName(module.icon), size: 16),
                    label: Text(module.title),
                    onPressed: () {
                      Navigator.pop(context);
                      _controller.selectModule(module);
                    },
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _showAiAssistant(BuildContext context, EnterpriseAppConfig config) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      backgroundColor: const Color(0xFF0B1715),
      builder: (context) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('AI Business Copilot',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w900)),
            const SizedBox(height: 10),
            const Text(
              'Today: cashflow is healthy, 12 SKUs need reorder, 4 CRM leads are stale, and GST filing tasks are waiting.',
            ),
            const SizedBox(height: 16),
            TextField(
              decoration: InputDecoration(
                hintText: 'Ask ${config.theme.brandName} AI...',
                prefixIcon: const Icon(Icons.auto_awesome),
                suffixIcon: IconButton(
                  tooltip: 'Send',
                  onPressed: () {},
                  icon: const Icon(Icons.arrow_upward),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EnterpriseBackdrop extends StatelessWidget {
  const _EnterpriseBackdrop({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<EnterpriseAppController>();
    return Obx(() {
      final activeColor = controller.profileColor;
      return DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              activeColor.withValues(alpha: 0.28),
              const Color(0xFF03070E),
              const Color(0xFF050D19),
            ],
          ),
        ),
        child: const SizedBox.expand(),
      );
    });
  }
}

class _EnterpriseRail extends StatelessWidget {
  const _EnterpriseRail({
    required this.config,
    required this.modules,
    required this.selected,
    required this.collapsed,
    required this.onToggle,
    required this.onSelect,
  });

  final EnterpriseAppConfig config;
  final List<EnterpriseModule> modules;
  final EnterpriseModule? selected;
  final bool collapsed;
  final VoidCallback onToggle;
  final ValueChanged<EnterpriseModule> onSelect;

  @override
  Widget build(BuildContext context) {
    final auth = Get.find<AuthController>();
    final controller = Get.find<EnterpriseAppController>();
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 14, 0, 14),
        child: Obx(() {
          final activeColor = controller.profileColor;
          return EnterpriseGlass(
            opacity: 0.16,
            borderOpacity: 0.22,
            radius: 10,
            padding: const EdgeInsets.all(10),
            child: Column(
              children: [
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [
                            activeColor,
                            activeColor.withValues(alpha: 0.4)
                          ],
                        ),
                        borderRadius: BorderRadius.circular(10),
                        boxShadow: [
                          BoxShadow(
                            color: activeColor.withValues(alpha: 0.3),
                            blurRadius: 10,
                            spreadRadius: 1,
                          )
                        ],
                      ),
                      child: const Icon(Icons.account_balance,
                          color: Colors.white),
                    ),
                    if (!collapsed) ...[
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(config.theme.brandName,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w900)),
                            Text(config.workspace.name,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    color: Colors.white54, fontSize: 11)),
                          ],
                        ),
                      ),
                    ],
                    if (!collapsed)
                      IconButton(
                        tooltip: 'Collapse sidebar',
                        onPressed: onToggle,
                        icon: const Icon(Icons.menu),
                      ),
                  ],
                ),
                if (collapsed) ...[
                  const SizedBox(height: 8),
                  IconButton.filledTonal(
                    tooltip: 'Expand sidebar',
                    onPressed: onToggle,
                    icon: const Icon(Icons.menu_open),
                  ),
                ],
                const SizedBox(height: 12),
                if (!collapsed)
                  _ProfileBlock(
                    name: auth.currentUser.value?.name ?? 'Enterprise User',
                    mode: auth.sessionMode.value,
                  ),
                const SizedBox(height: 12),
                Expanded(
                  child: ListView.separated(
                    itemCount: config.sidebar.isNotEmpty
                        ? config.sidebar.length
                        : modules.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 6),
                    itemBuilder: (context, index) {
                      if (config.sidebar.isNotEmpty) {
                        final item = config.sidebar[index];
                        return _MenuNodeTile(
                          item: item,
                          modules: modules,
                          selected: selected,
                          collapsed: collapsed,
                          onSelect: onSelect,
                        );
                      }
                      final module = modules[index];
                      final active = selected?.key == module.key;
                      return _ModuleTile(
                        module: module,
                        active: active,
                        collapsed: collapsed,
                        onTap: () => onSelect(module),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 10),
                if (!collapsed) const SyncStatusChip(),
                const SizedBox(height: 8),
                IconButton.filledTonal(
                  tooltip: 'Logout',
                  onPressed: () => auth.logout(),
                  icon: const Icon(Icons.logout),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }
}

class _MenuNodeTile extends StatelessWidget {
  const _MenuNodeTile({
    required this.item,
    required this.modules,
    required this.selected,
    required this.collapsed,
    required this.onSelect,
  });

  final EnterpriseMenuItem item;
  final List<EnterpriseModule> modules;
  final EnterpriseModule? selected;
  final bool collapsed;
  final ValueChanged<EnterpriseModule> onSelect;

  @override
  Widget build(BuildContext context) {
    final module = _resolveModule(item, modules);
    final active = module != null && selected?.key == module.key;
    if (item.children.isEmpty || collapsed) {
      return Tooltip(
        message: item.title,
        child: InkWell(
          onTap: module == null ? null : () => onSelect(module),
          borderRadius: BorderRadius.circular(8),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            decoration: BoxDecoration(
              color: active ? item.color : Colors.white.withValues(alpha: 0.04),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                  color: active
                      ? item.color
                      : Colors.white.withValues(alpha: 0.06)),
            ),
            child: Row(
              mainAxisAlignment: collapsed
                  ? MainAxisAlignment.center
                  : MainAxisAlignment.start,
              children: [
                Icon(EnterpriseIcons.fromName(item.icon),
                    color: active ? Colors.black : item.color, size: 20),
                if (!collapsed) ...[
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      item.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: active ? Colors.black : Colors.white,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  if (item.badge.isNotEmpty)
                    Badge(
                        label: Text(item.badge),
                        child: const SizedBox(width: 1, height: 1)),
                ],
              ],
            ),
          ),
        ),
      );
    }
    return ExpansionTile(
      tilePadding: const EdgeInsets.symmetric(horizontal: 8),
      childrenPadding: const EdgeInsets.only(left: 12, bottom: 6),
      leading: Icon(EnterpriseIcons.fromName(item.icon), color: item.color),
      title: Text(
        item.title,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontWeight: FontWeight.w900),
      ),
      children: [
        for (final child in item.children)
          _MenuNodeTile(
            item: child,
            modules: modules,
            selected: selected,
            collapsed: false,
            onSelect: onSelect,
          ),
      ],
    );
  }

  EnterpriseModule? _resolveModule(
      EnterpriseMenuItem item, List<EnterpriseModule> modules) {
    for (final module in modules) {
      if (module.key == item.key ||
          module.route == item.route ||
          module.webUrl == item.route) {
        return module;
      }
    }
    return null;
  }
}

class _ProfileBlock extends StatelessWidget {
  const _ProfileBlock({required this.name, required this.mode});

  final String name;
  final String mode;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.16),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: const Color(0xFF064E3B),
            child: Text(name.isEmpty ? 'U' : name[0].toUpperCase()),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w900)),
                Text('$mode session',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style:
                        const TextStyle(color: Colors.white54, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ModuleTile extends StatelessWidget {
  const _ModuleTile({
    required this.module,
    required this.active,
    required this.collapsed,
    required this.onTap,
  });

  final EnterpriseModule module;
  final bool active;
  final bool collapsed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final icon = Icon(EnterpriseIcons.fromName(module.icon),
        color: active ? Colors.black : module.color, size: 20);
    final controller = Get.find<EnterpriseAppController>();
    return Tooltip(
      message: module.title,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Obx(() {
          final isHighlighted = controller.isModuleHighlighted(module.key);
          final activeColor = controller.profileColor;
          return AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
            decoration: BoxDecoration(
              color: active
                  ? module.color
                  : (isHighlighted
                      ? activeColor.withValues(alpha: 0.1)
                      : Colors.white.withValues(alpha: 0.04)),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: active
                    ? module.color.withValues(alpha: 0.9)
                    : (isHighlighted
                        ? activeColor.withValues(alpha: 0.45)
                        : Colors.white.withValues(alpha: 0.06)),
              ),
              boxShadow: isHighlighted && !active
                  ? [
                      BoxShadow(
                        color: activeColor.withValues(alpha: 0.16),
                        blurRadius: 8,
                        spreadRadius: 1,
                      )
                    ]
                  : null,
            ),
            child: Row(
              mainAxisAlignment: collapsed
                  ? MainAxisAlignment.center
                  : MainAxisAlignment.start,
              children: [
                icon,
                if (!collapsed) ...[
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(module.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: active ? Colors.black : Colors.white,
                              fontWeight: FontWeight.w900,
                            )),
                        Text(module.mode,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: active ? Colors.black54 : Colors.white54,
                              fontSize: 11,
                            )),
                      ],
                    ),
                  ),
                  if (isHighlighted && !active) ...[
                    Container(
                      width: 6,
                      height: 6,
                      decoration: BoxDecoration(
                        color: activeColor,
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: activeColor.withValues(alpha: 0.8),
                            blurRadius: 4,
                          )
                        ],
                      ),
                    ),
                  ],
                ],
              ],
            ),
          );
        }),
      ),
    );
  }
}

class _WorkspaceTopbar extends StatelessWidget {
  const _WorkspaceTopbar({
    required this.config,
    required this.selected,
    required this.isLoading,
    required this.onRefresh,
    required this.onCommand,
    required this.onLauncher,
  });

  final EnterpriseAppConfig config;
  final EnterpriseModule? selected;
  final bool isLoading;
  final VoidCallback onRefresh;
  final VoidCallback onCommand;
  final VoidCallback onLauncher;

  @override
  Widget build(BuildContext context) {
    final padding = EnterpriseBreakpoints.pagePadding(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 520;
        return Padding(
          padding: EdgeInsets.fromLTRB(padding.left, 14, padding.right, 8),
          child: Row(
            children: [
              Expanded(
                child: InkWell(
                  onTap: onCommand,
                  borderRadius: BorderRadius.circular(10),
                  child: EnterpriseGlass(
                    opacity: 0.82,
                    radius: 10,
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 11),
                    child: Row(
                      children: [
                        Icon(
                            EnterpriseIcons.fromName(
                                selected?.icon ?? 'dashboard'),
                            color: selected?.color ?? config.theme.accent),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(selected?.title ?? config.workspace.name,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium
                                      ?.copyWith(fontWeight: FontWeight.w900)),
                              if (!compact)
                                Text('Search or command center - Ctrl K',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodySmall
                                        ?.copyWith(
                                            color: Theme.of(context)
                                                .colorScheme
                                                .onSurfaceVariant)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              if (!compact) ...[
                Flexible(
                  fit: FlexFit.loose,
                  child: _ProfileSwitcherWidget(
                      controller: Get.find<EnterpriseAppController>()),
                ),
                const SizedBox(width: 8),
              ],
              IconButton.filledTonal(
                tooltip: 'Module launcher',
                onPressed: onLauncher,
                icon: const Icon(Icons.grid_view),
              ),
              if (!compact) ...[
                const SizedBox(width: 8),
                IconButton.filledTonal(
                  tooltip: 'Notifications',
                  onPressed: () {},
                  icon: const Badge(
                      label: Text('3'),
                      child: Icon(Icons.notifications_outlined)),
                ),
              ],
              const SizedBox(width: 8),
              IconButton.filledTonal(
                tooltip: 'Refresh backend config',
                onPressed: onRefresh,
                icon: isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _WorkspaceTabs extends StatelessWidget {
  const _WorkspaceTabs({
    required this.modules,
    required this.selected,
    required this.onSelect,
  });

  final List<EnterpriseModule> modules;
  final EnterpriseModule? selected;
  final ValueChanged<EnterpriseModule> onSelect;

  @override
  Widget build(BuildContext context) {
    final padding = EnterpriseBreakpoints.pagePadding(context);
    return SizedBox(
      height: 42,
      child: ListView.separated(
        padding: EdgeInsets.symmetric(horizontal: padding.left),
        scrollDirection: Axis.horizontal,
        itemCount: modules.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final module = modules[index];
          final active = selected?.key == module.key;
          return ChoiceChip(
            selected: active,
            onSelected: (_) => onSelect(module),
            avatar: Icon(EnterpriseIcons.fromName(module.icon), size: 16),
            label: Text(module.title),
          );
        },
      ),
    );
  }
}

class _FloatingActionStack extends StatelessWidget {
  const _FloatingActionStack({
    required this.accent,
    required this.onAi,
    required this.onLauncher,
  });

  final Color accent;
  final VoidCallback onAi;
  final VoidCallback onLauncher;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        FloatingActionButton.small(
          heroTag: 'launcher',
          onPressed: onLauncher,
          backgroundColor: const Color(0xFF00796B),
          child: const Icon(Icons.menu),
        ),
        const SizedBox(height: 10),
        FloatingActionButton(
          heroTag: 'ai',
          onPressed: onAi,
          backgroundColor: accent,
          foregroundColor: Colors.black,
          child: const Icon(Icons.auto_awesome),
        ),
      ],
    );
  }
}

class _FloatingNavigation extends StatelessWidget {
  const _FloatingNavigation({
    required this.modules,
    required this.selected,
    required this.onSelect,
  });

  final List<EnterpriseModule> modules;
  final EnterpriseModule? selected;
  final ValueChanged<EnterpriseModule> onSelect;

  @override
  Widget build(BuildContext context) {
    if (modules.isEmpty) return const SizedBox.shrink();
    final selectedIndex = modules.indexWhere((m) => m.key == selected?.key);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: NavigationBar(
            height: 68,
            selectedIndex: selectedIndex < 0 ? 0 : selectedIndex,
            onDestinationSelected: (index) => onSelect(modules[index]),
            destinations: [
              for (final module in modules)
                NavigationDestination(
                  icon: Icon(EnterpriseIcons.fromName(module.icon)),
                  label: module.title,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _EmptyWorkspace extends StatelessWidget {
  const _EmptyWorkspace();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Text('No modules are enabled for this role.',
          style: TextStyle(color: Colors.white)),
    );
  }
}

class _ProfileSwitcherWidget extends StatelessWidget {
  const _ProfileSwitcherWidget({required this.controller});

  final EnterpriseAppController controller;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final active = controller.activeProfile.value;
      final activeColor = controller.profileColor;
      return Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: activeColor.withValues(alpha: 0.22)),
        ),
        child: EnterpriseGlass(
          opacity: 0.22,
          radius: 10,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          child: PopupMenuButton<String>(
            tooltip: 'Switch Use-Case Profile',
            offset: const Offset(0, 48),
            color: const Color(0xFF070E1A),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: activeColor.withValues(alpha: 0.3)),
            ),
            onSelected: controller.switchProfile,
            itemBuilder: (context) {
              return controller.profiles.map((profile) {
                final isCurrent = profile == active;
                Color pColor = switch (profile) {
                  'Retail Billing' => const Color(0xFF10B981),
                  'E-Commerce Hub' => const Color(0xFFF43F5E),
                  'AI Business Copilot' => const Color(0xFFF59E0B),
                  _ => const Color(0xFF6366F1),
                };
                return PopupMenuItem<String>(
                  value: profile,
                  child: Row(
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: pColor,
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: pColor.withValues(alpha: 0.4),
                              blurRadius: 4,
                            )
                          ],
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        profile,
                        style: TextStyle(
                          color: isCurrent ? pColor : Colors.white,
                          fontWeight:
                              isCurrent ? FontWeight.w900 : FontWeight.normal,
                          fontSize: 13,
                        ),
                      ),
                      if (isCurrent) ...[
                        const Spacer(),
                        Icon(Icons.check, color: pColor, size: 16),
                      ],
                    ],
                  ),
                );
              }).toList();
            },
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: activeColor,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: activeColor.withValues(alpha: 0.8),
                        blurRadius: 8,
                        spreadRadius: 1,
                      )
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  active,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w900,
                    fontSize: 12,
                  ),
                ),
                const Icon(Icons.arrow_drop_down,
                    color: Colors.white70, size: 18),
              ],
            ),
          ),
        ),
      );
    });
  }
}
