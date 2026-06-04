import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/party_controller.dart';
import '../../models/party_model.dart';
import 'add_party_screen.dart';

class PartyListScreen extends StatefulWidget {
  const PartyListScreen({super.key});

  @override
  State<PartyListScreen> createState() => _PartyListScreenState();
}

class _PartyListScreenState extends State<PartyListScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
    _tabs.addListener(() {
      if (_tabs.indexIsChanging) return;
      _load();
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  String get _type => _tabs.index == 0 ? 'customer' : 'supplier';

  Future<void> _load() => Get.find<PartyController>().load(type: _type);

  @override
  Widget build(BuildContext context) {
    final c = Get.find<PartyController>();
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        Material(
          color: scheme.surface,
          child: TabBar(
            controller: _tabs,
            tabs: const [
              Tab(text: 'Customers'),
              Tab(text: 'Suppliers'),
            ],
          ),
        ),
        Expanded(
          child: Obx(() {
            if (c.isLoading.value) {
              return const Center(child: CircularProgressIndicator());
            }
            final rows = c.items.where((e) => e.type == _type).toList();
            if (rows.isEmpty) {
              return Center(
                child: Text('No ${_type}s yet. Tap + to add.'),
              );
            }
            return RefreshIndicator(
              onRefresh: _load,
              child: ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, i) => _PartyTile(
                  party: rows[i],
                  onDelete: () => c.remove(rows[i].id, type: _type),
                ),
              ),
            );
          }),
        ),
        const SizedBox(height: 8),
        Padding(
          padding: const EdgeInsets.only(right: 16, bottom: 12),
          child: Align(
            alignment: Alignment.bottomRight,
            child: FloatingActionButton.extended(
              onPressed: () async {
                await Get.to(() => AddPartyScreen(type: _type));
                await _load();
              },
              icon: const Icon(Icons.add),
              label: Text(_type == 'customer' ? 'Add Customer' : 'Add Supplier'),
            ),
          ),
        ),
      ],
    );
  }
}

class _PartyTile extends StatelessWidget {
  const _PartyTile({required this.party, required this.onDelete});

  final PartyModel party;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey(party.id),
      direction: DismissDirection.endToStart,
      confirmDismiss: (_) async {
        return await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Delete party?'),
                content: Text('Delete "${party.name}"?'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                  FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
                ],
              ),
            ) ??
            false;
      },
      onDismissed: (_) => onDelete(),
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        color: Theme.of(context).colorScheme.errorContainer,
        child: const Icon(Icons.delete),
      ),
      child: Card(
        child: ListTile(
          leading: const Icon(Icons.person),
          title: Text(party.name),
          subtitle: Text(
            [party.phone?.trim(), party.address?.trim()].whereType<String>().where((e) => e.isNotEmpty).join(' • '),
          ),
          trailing: party.isSynced ? const Icon(Icons.cloud_done, size: 18) : const Icon(Icons.cloud_off, size: 18),
        ),
      ),
    );
  }
}
