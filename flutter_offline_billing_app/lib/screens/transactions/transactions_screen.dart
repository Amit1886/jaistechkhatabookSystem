import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/transaction_controller.dart';
import '../../models/transaction_model.dart';
import 'payment_in_screen.dart';
import 'payment_out_screen.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key});

  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => Get.find<TransactionController>().load());
  }

  @override
  Widget build(BuildContext context) {
    final c = Get.find<TransactionController>();
    return Scaffold(
      appBar: AppBar(title: const Text('Transactions')),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () async {
                        await Get.to(() => const PaymentInScreen());
                        await c.load();
                      },
                      icon: const Icon(Icons.call_received),
                      label: const Text('Payment In'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.tonalIcon(
                      onPressed: () async {
                        await Get.to(() => const PaymentOutScreen());
                        await c.load();
                      },
                      icon: const Icon(Icons.call_made),
                      label: const Text('Payment Out'),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: Obx(() {
                if (c.isLoading.value) return const Center(child: CircularProgressIndicator());
                final rows = c.items;
                if (rows.isEmpty) return const Center(child: Text('No transactions yet.'));
                return ListView.separated(
                  padding: const EdgeInsets.all(12),
                  itemCount: rows.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) => _TxnTile(txn: rows[i]),
                );
              }),
            ),
          ],
        ),
      ),
    );
  }
}

class _TxnTile extends StatelessWidget {
  const _TxnTile({required this.txn});
  final TransactionModel txn;

  @override
  Widget build(BuildContext context) {
    final isIn = txn.type == 'payment_in';
    return Card(
      child: ListTile(
        leading: Icon(isIn ? Icons.call_received : Icons.call_made),
        title: Text('₹${txn.amount.toStringAsFixed(2)}'),
        subtitle: Text('${txn.mode} • ${txn.date.toLocal().toString().split(' ').first}'),
        trailing: txn.isSynced ? const Icon(Icons.cloud_done, size: 18) : const Icon(Icons.cloud_off, size: 18),
      ),
    );
  }
}

