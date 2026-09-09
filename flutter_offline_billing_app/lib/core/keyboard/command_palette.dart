import 'package:flutter/material.dart';

class CommandPalette extends StatefulWidget {
  final List<String> actions;
  final ValueChanged<String> onSelected;

  const CommandPalette({
    super.key,
    required this.actions,
    required this.onSelected,
  });

  @override
  State<CommandPalette> createState() => _CommandPaletteState();
}

class _CommandPaletteState extends State<CommandPalette> {
  final TextEditingController _controller = TextEditingController();
  List<String> _filtered = [];

  @override
  void initState() {
    super.initState();
    _filtered = widget.actions;
    _controller.addListener(() {
      setState(() {
        _filtered = widget.actions
            .where((a) => a.toLowerCase().contains(_controller.text.toLowerCase()))
            .toList();
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Command Palette'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _controller,
            autofocus: true,
            decoration: const InputDecoration(hintText: 'Type a command...'),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: 400,
            child: ListView.builder(
              shrinkWrap: true,
              itemCount: _filtered.length,
              itemBuilder: (context, index) {
                return ListTile(
                  title: Text(_filtered[index]),
                  onTap: () => widget.onSelected(_filtered[index]),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
