import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../core/responsive/enterprise_breakpoints.dart';
import '../../dynamic_platform/dynamic_form_renderer.dart';
import '../../dynamic_platform/dynamic_metadata.dart';
import '../../dynamic_platform/dynamic_runtime_service.dart';
import '../../models/enterprise_app_config.dart';
import '../../permissions/permission_engine.dart';
import '../../widgets/enterprise/enterprise_glass.dart';
import '../../widgets/enterprise/enterprise_icons.dart';
import '../../widgets/enterprise/enterprise_runtime_components.dart';

class DynamicRuntimeModuleScreen extends StatefulWidget {
  const DynamicRuntimeModuleScreen({
    super.key,
    required this.module,
    required this.permissionEngine,
  });

  final EnterpriseModule module;
  final PermissionEngine permissionEngine;

  @override
  State<DynamicRuntimeModuleScreen> createState() => _DynamicRuntimeModuleScreenState();
}

class _DynamicRuntimeModuleScreenState extends State<DynamicRuntimeModuleScreen> {
  final _runtime = Get.find<DynamicRuntimeService>();
  late Future<List<DynamicScreenMeta>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void didUpdateWidget(covariant DynamicRuntimeModuleScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.module.key != widget.module.key) {
      _future = _load();
    }
  }

  Future<List<DynamicScreenMeta>> _load() async {
    final modelKey = (widget.module.settings['model_key'] ?? widget.module.settings['model'] ?? '').toString();
    if (modelKey.isNotEmpty) {
      final screen = await _runtime.screen(modelKey);
      if (screen != null) return [screen];
    }
    final screens = await _runtime.screens();
    return _runtime.screensForModule(screens, widget.module);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<DynamicScreenMeta>>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return Padding(
            padding: EnterpriseBreakpoints.pagePadding(context),
            child: const EnterpriseSkeleton(rows: 5),
          );
        }
        final screens = snapshot.data ?? const [];
        if (screens.length == 1) {
          return DynamicRuntimeTable(module: widget.module, screen: screens.first);
        }
        return _ScreenCatalog(module: widget.module, screens: screens);
      },
    );
  }
}

class _ScreenCatalog extends StatelessWidget {
  const _ScreenCatalog({required this.module, required this.screens});

  final EnterpriseModule module;
  final List<DynamicScreenMeta> screens;

  @override
  Widget build(BuildContext context) {
    final padding = EnterpriseBreakpoints.pagePadding(context);
    return ListView(
      padding: padding.copyWith(bottom: 110),
      children: [
        EnterpriseGlass(
          radius: 10,
          opacity: 0.78,
          child: Row(
            children: [
              Icon(EnterpriseIcons.fromName(module.icon), color: module.color),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(module.title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                    const Text('Backend metadata decides which screens, APIs, forms, and tables appear here.'),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        if (screens.isEmpty)
          EnterpriseGlass(
            radius: 10,
            opacity: 0.74,
            child: const Text('No dynamic models are available for this module yet. Add a Django model or set module.settings.model_key in Admin.'),
          )
        else
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth > 900 ? 4 : constraints.maxWidth > 560 ? 2 : 1;
              return GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: screens.length,
                gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: columns,
                  crossAxisSpacing: 12,
                  mainAxisSpacing: 12,
                  mainAxisExtent: 118,
                ),
                itemBuilder: (context, index) {
                  final screen = screens[index];
                  return InkWell(
                    borderRadius: BorderRadius.circular(8),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => DynamicRuntimeTable(module: module, screen: screen),
                    )),
                    child: EnterpriseGlass(
                      radius: 8,
                      opacity: 0.72,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.table_chart, color: module.color),
                          const Spacer(),
                          Text(screen.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w900)),
                          Text(screen.model, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white54, fontSize: 12)),
                        ],
                      ),
                    ),
                  );
                },
              );
            },
          ),
      ],
    );
  }
}

class DynamicRuntimeTable extends StatefulWidget {
  const DynamicRuntimeTable({
    super.key,
    required this.module,
    required this.screen,
  });

  final EnterpriseModule module;
  final DynamicScreenMeta screen;

  @override
  State<DynamicRuntimeTable> createState() => _DynamicRuntimeTableState();
}

class _DynamicRuntimeTableState extends State<DynamicRuntimeTable> {
  final _runtime = Get.find<DynamicRuntimeService>();
  final _search = TextEditingController();
  final List<Map<String, dynamic>> _rows = [];
  bool _loading = true;
  int _offset = 0;
  int _count = 0;
  static const _limit = 30;

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final padding = EnterpriseBreakpoints.pagePadding(context);
    return ListView(
      padding: padding.copyWith(bottom: 110),
      children: [
        EnterpriseGlass(
          radius: 10,
          opacity: 0.78,
          child: Row(
            children: [
              Icon(EnterpriseIcons.fromName(widget.module.icon), color: widget.module.color),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(widget.screen.title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                    Text(widget.screen.model, style: const TextStyle(color: Colors.white54)),
                  ],
                ),
              ),
              IconButton.filledTonal(
                tooltip: 'Refresh',
                onPressed: () => _load(reset: true),
                icon: const Icon(Icons.sync),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                tooltip: 'Create',
                onPressed: _openCreate,
                icon: const Icon(Icons.add),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        EnterpriseGlass(
          radius: 10,
          opacity: 0.72,
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _search,
                  decoration: const InputDecoration(
                    hintText: 'Search records...',
                    prefixIcon: Icon(Icons.search),
                  ),
                  onSubmitted: (_) => _load(reset: true),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(
                tooltip: 'Apply search',
                onPressed: () => _load(reset: true),
                icon: const Icon(Icons.arrow_forward),
              ),
              const SizedBox(width: 8),
              IconButton.filledTonal(
                tooltip: 'Export',
                onPressed: () {},
                icon: const Icon(Icons.download),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        if (_loading)
          const EnterpriseSkeleton(rows: 6)
        else
          EnterpriseGlass(
            radius: 10,
            opacity: 0.76,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: DataTable(
                    headingRowColor: WidgetStatePropertyAll(Colors.white.withValues(alpha: 0.06)),
                    columns: [
                      for (final column in widget.screen.columns)
                        DataColumn(label: Text(column)),
                      const DataColumn(label: Text('Actions')),
                    ],
                    rows: [
                      for (final row in _rows)
                        DataRow(
                          cells: [
                            for (final column in widget.screen.columns)
                              DataCell(Text('${row[column] ?? ''}', maxLines: 1, overflow: TextOverflow.ellipsis)),
                            DataCell(
                              IconButton(
                                tooltip: 'Edit',
                                onPressed: () => _openEdit(row),
                                icon: const Icon(Icons.edit),
                              ),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Text('$_count records', style: const TextStyle(color: Colors.white54)),
                    const Spacer(),
                    IconButton(
                      tooltip: 'Previous page',
                      onPressed: _offset == 0 ? null : () => _load(offset: (_offset - _limit).clamp(0, _count).toInt()),
                      icon: const Icon(Icons.chevron_left),
                    ),
                    Text('${_offset + 1}-${(_offset + _rows.length).clamp(0, _count).toInt()}'),
                    IconButton(
                      tooltip: 'Next page',
                      onPressed: _offset + _limit >= _count ? null : () => _load(offset: _offset + _limit),
                      icon: const Icon(Icons.chevron_right),
                    ),
                  ],
                ),
              ],
            ),
          ),
      ],
    );
  }

  Future<void> _load({bool reset = false, int? offset}) async {
    setState(() => _loading = true);
    try {
      final nextOffset = reset ? 0 : offset ?? _offset;
      final payload = await _runtime.listRecords(
        widget.screen,
        query: _search.text,
        limit: _limit,
        offset: nextOffset,
      );
      final results = (payload['results'] as List?) ?? const [];
      _rows
        ..clear()
        ..addAll(results.whereType<Map>().map((row) => row.map((key, value) => MapEntry(key.toString(), value))));
      _count = int.tryParse('${payload['count'] ?? _rows.length}') ?? _rows.length;
      _offset = nextOffset;
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openCreate() async {
    final optimistic = <String, dynamic>{'id': 'local-${DateTime.now().millisecondsSinceEpoch}'};
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => Scaffold(
        appBar: AppBar(title: Text('New ${widget.screen.title}')),
        body: DynamicFormRenderer(
          screen: widget.screen,
          onSubmit: (value) async {
            setState(() => _rows.insert(0, {...optimistic, ...value}));
            await _runtime.createRecord(widget.screen, value);
          },
        ),
      ),
    ));
    _load(reset: true);
  }

  Future<void> _openEdit(Map<String, dynamic> row) async {
    final id = row['id'];
    if (id == null) return;
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => Scaffold(
        appBar: AppBar(title: Text(_titleFor(row))),
        body: DynamicFormRenderer(
          screen: widget.screen,
          initialValue: row,
          onSubmit: (value) async {
            final index = _rows.indexWhere((item) => item['id'] == id);
            if (index >= 0) setState(() => _rows[index] = {..._rows[index], ...value});
            await _runtime.updateRecord(widget.screen, id, value);
          },
        ),
      ),
    ));
    _load();
  }

  String _titleFor(Map<String, dynamic> row) {
    for (final key in ['name', 'title', 'email', 'invoice_number', 'number', 'id']) {
      final value = row[key];
      if (value != null && value.toString().isNotEmpty) return value.toString();
    }
    return widget.screen.title;
  }
}
