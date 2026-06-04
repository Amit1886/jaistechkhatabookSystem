import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/sync_controller.dart';
import '../services/sync_service.dart';

class SyncStatusChip extends StatelessWidget {
  const SyncStatusChip({super.key});

  @override
  Widget build(BuildContext context) {
    final sync = Get.find<SyncController>();
    final scheme = Theme.of(context).colorScheme;

    return Obx(() {
      final state = sync.status.value;

      String label;
      Color bg;
      Color fg;

      if (state == SyncStatus.offline) {
        label = 'Offline';
        bg = scheme.surfaceContainerHighest;
        fg = scheme.onSurfaceVariant;
      } else if (state == SyncStatus.syncing) {
        label = 'Syncing...';
        bg = scheme.primaryContainer;
        fg = scheme.onPrimaryContainer;
      } else if (state == SyncStatus.error) {
        label = 'Sync error';
        bg = scheme.errorContainer;
        fg = scheme.onErrorContainer;
      } else {
        label = 'Online';
        bg = scheme.secondaryContainer;
        fg = scheme.onSecondaryContainer;
      }

      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: scheme.outlineVariant),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.sync, size: 14, color: fg),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: fg)),
          ],
        ),
      );
    });
  }
}

