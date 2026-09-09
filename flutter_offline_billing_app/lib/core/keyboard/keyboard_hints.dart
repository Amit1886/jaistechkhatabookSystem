import 'package:flutter/material.dart';

class KeyboardHints extends StatelessWidget {
  final Map<LogicalKeySet, String> hints;

  const KeyboardHints({super.key, required this.hints});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      children: hints.entries.map((entry) {
        return Chip(
          label: Text(entry.value),
          avatar: const Icon(Icons.keyboard, size: 16),
        );
      }).toList(),
    );
  }
}
