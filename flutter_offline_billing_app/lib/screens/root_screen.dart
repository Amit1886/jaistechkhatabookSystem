import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../controllers/auth_controller.dart';
import '../layouts/enterprise_shell.dart';
import 'auth/login_screen.dart';

class RootScreen extends GetView<AuthController> {
  const RootScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      if (controller.isBusy.value) {
        return const _Splash();
      }
      if (controller.currentUser.value == null) {
        return const LoginScreen();
      }
      return const EnterpriseShell();
    });
  }
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.receipt_long, size: 56, color: scheme.primary),
            const SizedBox(height: 10),
            Text('JaisTech Billing',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text('Starting...', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
