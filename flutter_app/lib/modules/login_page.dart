import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../providers/erp_provider.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final email = TextEditingController(text: 'demo.test3@jaistech.local');
  final password = TextEditingController(text: 'Demo@12345');
  bool busy = false;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: width < 700 ? width - 32 : 420),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(8),
                          gradient: const LinearGradient(colors: [Color(0xFF176B87), Color(0xFF2D9CDB)]),
                        ),
                        child: const Icon(Icons.grid_view_rounded, color: Colors.white),
                      ),
                      const SizedBox(width: 14),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('JaisTech ERP', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                            Text('Enterprise access'),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),
                  TextField(controller: email, decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.mail_outline))),
                  const SizedBox(height: 12),
                  TextField(controller: password, obscureText: true, decoration: const InputDecoration(labelText: 'Password', prefixIcon: Icon(Icons.lock_outline))),
                  const SizedBox(height: 20),
                  FilledButton.icon(
                    onPressed: busy ? null : _login,
                    icon: busy ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.login),
                    label: const Text('Sign in'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _login() async {
    setState(() => busy = true);
    final erp = context.read<ErpProvider>();
    final ok = await erp.login(email.text.trim(), password.text);
    setState(() => busy = false);
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Login failed. Check backend and credentials.')));
    }
  }
}

