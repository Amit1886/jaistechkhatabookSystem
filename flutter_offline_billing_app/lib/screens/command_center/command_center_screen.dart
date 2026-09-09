import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/command_center_models.dart';
import '../../services/command_center_service.dart';
import '../../widgets/enterprise/bi_widgets.dart';

class CommandCenterScreen extends StatefulWidget {
  const CommandCenterScreen({super.key});

  @override
  State<CommandCenterScreen> createState() => _CommandCenterScreenState();
}

class _CommandCenterScreenState extends State<CommandCenterScreen> {
  final TextEditingController _searchController = TextEditingController();
  List<CommandCenterAction> _actions = [];
  List<CommandCenterAction> _filtered = [];

  @override
  void initState() {
    super.initState();
    _loadActions();
    _searchController.addListener(_filterActions);
  }

  Future<void> _loadActions() async {
    final service = CommandCenterService();
    final actions = await service.fetchActions();
    setState(() {
      _actions = actions;
      _filtered = actions;
    });
  }

  void _filterActions() {
    final query = _searchController.text.toLowerCase();
    setState(() {
      _filtered = _actions
          .where((a) => a.label.toLowerCase().contains(query))
          .toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Command Center')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                hintText: 'Search commands...',
                prefixIcon: Icon(Icons.search),
              ),
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: _filtered.length,
              itemBuilder: (context, index) {
                final action = _filtered[index];
                return ListTile(
                  title: Text(action.label),
                  onTap: () => _executeAction(action),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _executeAction(CommandCenterAction action) async {
    final service = CommandCenterService();
    final result = await service.execute(action);
    if (result.success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(result.message ?? 'Action executed')),
      );
    }
  }
}
