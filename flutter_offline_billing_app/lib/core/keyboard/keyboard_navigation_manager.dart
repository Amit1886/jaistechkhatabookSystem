import 'package:flutter/material.dart';

class KeyboardNavigationManager extends ChangeNotifier {
  final Map<Type, GlobalKey> _keys = {};

  void register<T extends Widget>(GlobalKey key) {
    _keys[T] = key;
  }

  void focusNext() {
    final current = FocusManager.instance.primaryFocus;
    if (current == null) return;
    current.nextFocus();
  }

  void focusPrevious() {
    final current = FocusManager.instance.primaryFocus;
    if (current == null) return;
    current.previousFocus();
  }
}
