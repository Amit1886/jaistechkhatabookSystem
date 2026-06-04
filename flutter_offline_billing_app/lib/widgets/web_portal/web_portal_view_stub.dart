import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

Widget buildWebPortalView(String url) {
  return Center(
    child: FilledButton.icon(
      onPressed: () {
        final uri = Uri.tryParse(url);
        if (uri != null) {
          launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
      icon: const Icon(Icons.open_in_browser),
      label: const Text('Open Dashboard'),
    ),
  );
}
