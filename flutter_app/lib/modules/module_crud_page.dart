import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/module.dart';
import '../providers/erp_provider.dart';

class ModuleCrudPage extends StatefulWidget {
  const ModuleCrudPage({super.key, required this.module});

  final ErpModule module;

  @override
  State<ModuleCrudPage> createState() => _ModuleCrudPageState();
}

class _ModuleCrudPageState extends State<ModuleCrudPage> {
  List<dynamic> rows = [];
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(covariant ModuleCrudPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.module.key != widget.module.key) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: 12,
            runSpacing: 12,
            alignment: WrapAlignment.spaceBetween,
            children: [
              Text(widget.module.name, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              FilledButton.icon(onPressed: _load, icon: const Icon(Icons.refresh), label: const Text('Refresh')),
            ],
          ),
          const SizedBox(height: 16),
          Expanded(
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : rows.isEmpty
                    ? const Center(child: Text('No records available'))
                    : ListView.separated(
                        itemCount: rows.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 8),
                        itemBuilder: (context, i) {
                          final row = Map<String, dynamic>.from(rows[i]);
                          final title = row['name'] ?? row['invoice_number'] ?? row['key'] ?? row['sku'] ?? 'Record ${row['id']}';
                          return Card(
                            child: ListTile(
                              title: Text('$title', maxLines: 1, overflow: TextOverflow.ellipsis),
                              subtitle: Text(row.entries.take(4).map((e) => '${e.key}: ${e.value}').join('  '), maxLines: 2, overflow: TextOverflow.ellipsis),
                              trailing: const Icon(Icons.chevron_right),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }

  Future<void> _load() async {
    setState(() => loading = true);
    try {
      final data = await context.read<ErpProvider>().api.get(widget.module.apiBase);
      rows = data is Map && data['results'] is List ? data['results'] : (data is List ? data : []);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }
}

