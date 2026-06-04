import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../services/enterprise_live_service.dart';

class LiveEntityScreen extends StatefulWidget {
  const LiveEntityScreen({super.key, required this.kind});

  final String kind;

  @override
  State<LiveEntityScreen> createState() => _LiveEntityScreenState();
}

class _LiveEntityScreenState extends State<LiveEntityScreen> {
  late Future<List<Map<String, dynamic>>> _future;

  EnterpriseLiveService get _live => Get.find<EnterpriseLiveService>();

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Map<String, dynamic>>> _load() {
    return switch (widget.kind) {
      'customers' => _live.parties(partyType: 'customer'),
      'suppliers' => _live.parties(partyType: 'supplier'),
      'inventory' => _live.products(),
      'transactions' => _live.transactions(),
      _ => _live.parties(),
    };
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openCreateDialog,
        icon: const Icon(Icons.add),
        label: Text(_addLabel),
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snapshot) {
          final rows = snapshot.data ?? const [];
          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(_title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900)),
                    ),
                    if (snapshot.connectionState == ConnectionState.waiting)
                      const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
                  ],
                ),
                const SizedBox(height: 14),
                Card(
                  child: Column(
                    children: [
                      if (rows.isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(22),
                          child: Text('No live records found. Add one from this app and it will appear in Django admin/dashboard.'),
                        )
                      else
                        for (final row in rows) _LiveRow(kind: widget.kind, row: row),
                    ],
                  ),
                ),
                const SizedBox(height: 84),
              ],
            ),
          );
        },
      ),
    );
  }

  String get _title => switch (widget.kind) {
        'inventory' => 'Live Inventory',
        'transactions' => 'Live Transactions',
        'suppliers' => 'Live Suppliers',
        _ => 'Live Customers',
      };

  String get _addLabel => switch (widget.kind) {
        'inventory' => 'Product',
        'transactions' => 'Transaction',
        'suppliers' => 'Supplier',
        _ => 'Customer',
      };

  Future<void> _openCreateDialog() async {
    if (widget.kind == 'inventory') {
      await _ProductDialog(onSave: _live.createProduct).show(context);
    } else if (widget.kind == 'transactions') {
      final parties = await _live.parties();
      if (!mounted) return;
      await _TransactionDialog(parties: parties, onSave: _live.createTransaction).show(context);
    } else {
      final type = widget.kind == 'suppliers' ? 'supplier' : 'customer';
      await _PartyDialog(partyType: type, onSave: _live.createParty).show(context);
    }
    await _refresh();
  }
}

class _LiveRow extends StatelessWidget {
  const _LiveRow({required this.kind, required this.row});

  final String kind;
  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final title = switch (kind) {
      'inventory' => row['name'],
      'transactions' => row['party'],
      _ => row['name'],
    };
    final subtitle = switch (kind) {
      'inventory' => 'SKU: ${row['sku']}  Stock: ${row['stock']}',
      'transactions' => '${row['txn_type']} • ${row['txn_mode']} • ${row['date']}',
      _ => '${row['party_type']} • ${row['mobile']}',
    };
    final trailing = switch (kind) {
      'inventory' => row['price'],
      'transactions' => row['amount'],
      _ => row['balance'],
    };
    return Column(
      children: [
        ListTile(
          leading: const Icon(Icons.circle, size: 10),
          title: Text((title ?? '').toString(), maxLines: 1, overflow: TextOverflow.ellipsis),
          subtitle: Text((subtitle ?? '').toString(), maxLines: 1, overflow: TextOverflow.ellipsis),
          trailing: Text((trailing ?? '').toString()),
        ),
        const Divider(height: 0),
      ],
    );
  }
}

class _PartyDialog {
  const _PartyDialog({required this.partyType, required this.onSave});

  final String partyType;
  final Future<void> Function({required String name, String mobile, String partyType}) onSave;

  Future<void> show(BuildContext context) async {
    final name = TextEditingController();
    final mobile = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Add ${partyType == 'supplier' ? 'Supplier' : 'Customer'}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: name, decoration: const InputDecoration(labelText: 'Name')),
            const SizedBox(height: 10),
            TextField(controller: mobile, decoration: const InputDecoration(labelText: 'Mobile')),
          ],
        ),
        actions: [
          TextButton(onPressed: Get.back, child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              await onSave(name: name.text, mobile: mobile.text, partyType: partyType);
              Get.back();
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }
}

class _ProductDialog {
  const _ProductDialog({required this.onSave});

  final Future<void> Function({required String name, required String sku, required String price, required String stock}) onSave;

  Future<void> show(BuildContext context) async {
    final name = TextEditingController();
    final sku = TextEditingController();
    final price = TextEditingController(text: '0');
    final stock = TextEditingController(text: '0');
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Product'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: name, decoration: const InputDecoration(labelText: 'Name')),
            const SizedBox(height: 10),
            TextField(controller: sku, decoration: const InputDecoration(labelText: 'SKU')),
            const SizedBox(height: 10),
            TextField(controller: price, decoration: const InputDecoration(labelText: 'Price')),
            const SizedBox(height: 10),
            TextField(controller: stock, decoration: const InputDecoration(labelText: 'Stock')),
          ],
        ),
        actions: [
          TextButton(onPressed: Get.back, child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              await onSave(name: name.text, sku: sku.text, price: price.text, stock: stock.text);
              Get.back();
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }
}

class _TransactionDialog {
  const _TransactionDialog({required this.parties, required this.onSave});

  final List<Map<String, dynamic>> parties;
  final Future<void> Function({required String partyId, required String amount, required String txnType, String mode, String notes}) onSave;

  Future<void> show(BuildContext context) async {
    String? partyId = parties.isNotEmpty ? parties.first['id'].toString() : null;
    String txnType = 'credit';
    final amount = TextEditingController(text: '0');
    final notes = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Add Transaction'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                value: partyId,
                items: [
                  for (final p in parties)
                    DropdownMenuItem(value: p['id'].toString(), child: Text((p['name'] ?? '').toString())),
                ],
                onChanged: (value) => setDialogState(() => partyId = value),
                decoration: const InputDecoration(labelText: 'Party'),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                value: txnType,
                items: const [
                  DropdownMenuItem(value: 'credit', child: Text('Credit')),
                  DropdownMenuItem(value: 'debit', child: Text('Debit')),
                ],
                onChanged: (value) => setDialogState(() => txnType = value ?? 'credit'),
                decoration: const InputDecoration(labelText: 'Type'),
              ),
              const SizedBox(height: 10),
              TextField(controller: amount, decoration: const InputDecoration(labelText: 'Amount')),
              const SizedBox(height: 10),
              TextField(controller: notes, decoration: const InputDecoration(labelText: 'Notes')),
            ],
          ),
          actions: [
            TextButton(onPressed: Get.back, child: const Text('Cancel')),
            FilledButton(
              onPressed: partyId == null
                  ? null
                  : () async {
                      await onSave(partyId: partyId!, amount: amount.text, txnType: txnType, notes: notes.text);
                      Get.back();
                    },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }
}
