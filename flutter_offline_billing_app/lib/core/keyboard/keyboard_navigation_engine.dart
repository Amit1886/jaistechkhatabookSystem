import 'package:flutter/services.dart';

class KeyboardNavigationEngine {
  final Map<LogicalKeySet, VoidCallback> _bindings = {};
  final List<FocusNode> _focusNodes = [];

  void bind(LogicalKeySet key, VoidCallback action) {
    _bindings[key] = action;
  }

  void addFocusNode(FocusNode node) {
    _focusNodes.add(node);
  }

  bool handleKey(KeyEvent event) {
    final isCtrl = HardwareKeyboard.instance.isControlPressed;
    for (final entry in _bindings.entries) {
      if (isCtrl && entry.key.match(event.physicalKey)) {
        entry.value();
        return true;
      }
    }
    return false;
  }

  void dispose() {
    for (final node in _focusNodes) {
      node.dispose();
    }
    _focusNodes.clear();
  }
}
