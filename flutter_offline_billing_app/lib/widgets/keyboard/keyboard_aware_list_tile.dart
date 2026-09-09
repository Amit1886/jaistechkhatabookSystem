import 'package:flutter/material.dart';

class KeyboardAwareListTile extends StatelessWidget {
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  final FocusNode? focusNode;

  const KeyboardAwareListTile({
    super.key,
    required this.title,
    this.subtitle,
    this.onTap,
    this.focusNode,
  });

  @override
  Widget build(BuildContext context) {
    return Focus(
      focusNode: focusNode,
      child: ListTile(
        title: Text(title),
        subtitle: subtitle != null ? Text(subtitle!) : null,
        onTap: onTap,
      ),
    );
  }
}
