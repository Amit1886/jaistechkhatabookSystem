import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/enterprise_app_controller.dart';
import '../../controllers/sync_controller.dart';
import '../../models/enterprise_app_config.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = Get.find<EnterpriseAppController>();
    final sync = Get.isRegistered<SyncController>() ? Get.find<SyncController>() : null;
    return Scaffold(
      appBar: AppBar(
        title: const Text('System Settings'),
        actions: [
          IconButton(
            tooltip: 'Refresh backend configuration',
            onPressed: () => app.refreshConfig(mode: 'app'),
            icon: const Icon(Icons.sync),
          ),
        ],
      ),
      body: SafeArea(
        child: Obx(() {
          final config = app.config.value ?? EnterpriseAppConfig.fallback();
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _Notice(config: config),
              const SizedBox(height: 12),
              _ReadOnlyTile(
                icon: Icons.admin_panel_settings,
                title: 'Backend Controlled',
                subtitle: 'API URL, JWT, sync token, server config, modules, permissions, and themes are managed by Superadmin.',
              ),
              _ReadOnlyTile(
                icon: Icons.business,
                title: config.workspace.name,
                subtitle: '${config.theme.brandName} - ${config.defaultMode} mode',
              ),
              _ReadOnlyTile(
                icon: Icons.widgets,
                title: '${config.visibleModules.length} enabled modules',
                subtitle: config.visibleModules.map((m) => m.title).take(8).join(', '),
              ),
              _ReadOnlyTile(
                icon: Icons.security,
                title: '${config.permissions.length} permission groups',
                subtitle: 'Changes sync automatically after Superadmin updates role, plan, modules, or features.',
              ),
              if (sync != null) _SyncStatus(sync: sync),
            ],
          );
        }),
      ),
    );
  }
}

class _Notice extends StatelessWidget {
  const _Notice({required this.config});

  final EnterpriseAppConfig config;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        gradient: LinearGradient(
          colors: [config.theme.primary.withValues(alpha: 0.9), config.theme.secondary.withValues(alpha: 0.72)],
        ),
      ),
      child: const Row(
        children: [
          Icon(Icons.lock, color: Colors.white),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'This app is centrally configured. Users cannot edit server URLs or tokens here.',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReadOnlyTile extends StatelessWidget {
  const _ReadOnlyTile({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon),
        title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: const Icon(Icons.lock_outline),
      ),
    );
  }
}

class _SyncStatus extends StatelessWidget {
  const _SyncStatus({required this.sync});

  final SyncController sync;

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final last = sync.lastSyncAt.value;
      return Card(
        child: ListTile(
          leading: const Icon(Icons.offline_bolt),
          title: Text('Sync: ${sync.status.value}'),
          subtitle: Text(last == null ? 'No sync completed yet' : 'Last sync: ${last.toLocal()}'),
          trailing: IconButton(
            tooltip: 'Sync now',
            onPressed: () => sync.syncNow(),
            icon: const Icon(Icons.sync),
          ),
        ),
      );
    });
  }
}
