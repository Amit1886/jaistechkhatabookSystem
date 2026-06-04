import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:jaistech_billing_mobile_app/core/theme/app_theme.dart';
import 'package:jaistech_billing_mobile_app/models/enterprise_app_config.dart';

void main() {
  testWidgets('App theme builds', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: AppTheme.light(),
        home: const Scaffold(body: SizedBox()),
      ),
    );

    expect(find.byType(MaterialApp), findsOneWidget);
  });

  test('enterprise config parses backend-driven demo workspace', () {
    final config = EnterpriseAppConfig.fromJson({
      'version': 'demo',
      'platform': 'desktop',
      'workspace': {
        'key': 'admin_workspace',
        'name': 'Admin Control Workspace',
        'landing_route': '/superadmin/',
        'layout': {'columns': 12},
      },
      'theme': {
        'brand_name': 'Billentra Enterprise Demo',
        'primary': '#0F766E',
        'secondary': '#2563EB',
        'accent': '#F59E0B',
      },
      'modules': [
        {
          'key': 'pos',
          'title': 'POS',
          'icon': 'shopping-bag',
          'route': '/pos',
          'web_url': '/pos/ui/',
          'enabled': true,
          'visible': true,
          'order': 1,
        }
      ],
      'widgets': [
        {
          'key': 'pos_sales',
          'title': 'POS Sales Today',
          'widget_type': 'metric',
          'permission_key': 'pos_view',
          'data_source': 'Rs 86,420',
        }
      ],
      'permissions': {
        'pos': {'view': true, 'create': true, 'print': true}
      },
      'realtime': {'module_channel': 'ws/enterprise/modules/'},
    });

    expect(config.workspace.key, 'admin_workspace');
    expect(config.theme.brandName, 'Billentra Enterprise Demo');
    expect(config.visibleModules.single.key, 'pos');
    expect(config.widgets.single.value, 'Rs 86,420');
    expect(config.permissions['pos']?.canPrint, isTrue);
  });
}
