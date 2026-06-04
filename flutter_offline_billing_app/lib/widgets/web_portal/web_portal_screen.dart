import 'package:flutter/material.dart';

import 'web_portal_view.dart';

class WebPortalScreen extends StatelessWidget {
  const WebPortalScreen({super.key, required this.url});

  final String url;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: buildWebPortalView(url),
      ),
    );
  }
}
