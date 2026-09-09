import 'package:flutter/material.dart';

class ModalFocusTrap extends StatefulWidget {
  final Widget child;
  final VoidCallback? onEscape;

  const ModalFocusTrap({super.key, required this.child, this.onEscape});

  @override
  State<ModalFocusTrap> createState() => _ModalFocusTrapState();
}

class _ModalFocusTrapState extends State<ModalFocusTrap> {
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _focusNode = FocusNode(debugLabel: 'ModalFocusTrap');
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    return Focus(
      focusNode: _focusNode,
      onKeyEvent: (node, event) {
        if (event is KeyDownEvent &&
            event.logicalKey == LogicalKeyboardKey.escape) {
          widget.onEscape?.call();
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: widget.child,
    );
  }

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }
}
