import 'package:flutter/material.dart';

import 'dynamic_form_renderer.dart';
import 'dynamic_metadata.dart';
import 'enterprise_api_client.dart';

class DynamicTableScreen extends StatefulWidget {
  final EnterpriseApiClient api;
  final DynamicScreenMeta screen;

  const DynamicTableScreen({super.key, required this.api, required this.screen});

  @override
  State<DynamicTableScreen> createState() => _DynamicTableScreenState();
}

class _DynamicTableScreenState extends State<DynamicTableScreen> {
  List<Map<String, dynamic>> _rows = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.screen.title)),
      floatingActionButton: FloatingActionButton(
        onPressed: _openCreate,
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView.separated(
              itemCount: _rows.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final row = _rows[index];
                return ListTile(
                  title: Text(_titleFor(row)),
                  subtitle: Text(widget.screen.columns.map((c) => '$c: ${row[c] ?? ''}').join('  ')),
                  onTap: () => _openEdit(row),
                );
              },
            ),
    );
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final response = await widget.api.getJson(widget.screen.listEndpoint);
      final results = (response['results'] as List?) ?? const [];
      _rows = results.whereType<Map>().map((e) => e.cast<String, dynamic>()).toList();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _titleFor(Map<String, dynamic> row) {
    for (final key in ['name', 'title', 'email', 'number', 'id']) {
      final value = row[key];
      if (value != null && value.toString().isNotEmpty) return value.toString();
    }
    return row.toString();
  }

  Future<void> _openCreate() async {
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => Scaffold(
        appBar: AppBar(title: Text('New ${widget.screen.title}')),
        body: DynamicFormRenderer(
          screen: widget.screen,
          onSubmit: (value) => widget.api.postJson(widget.screen.formEndpoint, {'data': value}),
        ),
      ),
    ));
    _load();
  }

  Future<void> _openEdit(Map<String, dynamic> row) async {
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => Scaffold(
        appBar: AppBar(title: Text(_titleFor(row))),
        body: DynamicFormRenderer(
          screen: widget.screen,
          initialValue: row,
          onSubmit: (value) => widget.api.patchJson('${widget.screen.formEndpoint}/${row['id']}', {'data': value}),
        ),
      ),
    ));
    _load();
  }
}
