import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/transaction_controller.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_textfield.dart';

class PaymentInScreen extends StatefulWidget {
  const PaymentInScreen({super.key});

  @override
  State<PaymentInScreen> createState() => _PaymentInScreenState();
}

class _PaymentInScreenState extends State<PaymentInScreen> {
  final _amount = TextEditingController();
  final _mode = TextEditingController(text: 'cash');
  final _reference = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _amount.dispose();
    _mode.dispose();
    _reference.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final amount = double.tryParse(_amount.text.trim()) ?? 0;
      await Get.find<TransactionController>().add(
        type: 'payment_in',
        amount: amount,
        mode: _mode.text.trim().isEmpty ? 'cash' : _mode.text.trim(),
        reference: _reference.text,
      );
      if (!mounted) return;
      Get.back();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment In')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    CustomTextField(
                      controller: _amount,
                      label: 'Amount',
                      keyboardType: TextInputType.number,
                      prefixIcon: Icons.currency_rupee,
                    ),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _mode,
                      label: 'Mode (cash/upi/bank)',
                      prefixIcon: Icons.payments,
                    ),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _reference,
                      label: 'Reference (optional)',
                      prefixIcon: Icons.confirmation_number,
                    ),
                    const SizedBox(height: 16),
                    Align(
                      alignment: Alignment.centerRight,
                      child: CustomButton(
                        label: 'Save',
                        icon: Icons.save,
                        loading: _saving,
                        onPressed: _save,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

