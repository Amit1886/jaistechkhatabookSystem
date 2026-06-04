import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/invoice_controller.dart';
import '../../models/invoice_model.dart';
import 'create_invoice_screen.dart';
import 'invoice_detail_screen.dart';

class InvoiceListScreen extends StatefulWidget {
  const InvoiceListScreen({super.key});

  @override
  State<InvoiceListScreen> createState() => _InvoiceListScreenState();
}

class _InvoiceListScreenState extends State<InvoiceListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => Get.find<InvoiceController>().load());
  }

  @override
  Widget build(BuildContext context) {
    final c = Get.find<InvoiceController>();
    return Column(
      children: [
        Expanded(
          child: Obx(() {
            if (c.isLoading.value) {
              return const Center(child: CircularProgressIndicator());
            }
            final rows = c.items;
            if (rows.isEmpty) {
              return const Center(child: Text('No invoices yet. Tap + to create one.'));
            }
            return RefreshIndicator(
              onRefresh: c.load,
              child: ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, i) => _InvoiceTile(invoice: rows[i]),
              ),
            );
          }),
        ),
        const SizedBox(height: 8),
        Padding(
          padding: const EdgeInsets.only(right: 16, bottom: 12),
          child: Align(
            alignment: Alignment.bottomRight,
            child: FloatingActionButton.extended(
              onPressed: () async {
                await Get.to(() => const CreateInvoiceScreen());
                await c.load();
              },
              icon: const Icon(Icons.add),
              label: const Text('New Invoice'),
            ),
          ),
        ),
      ],
    );
  }
}

class _InvoiceTile extends StatelessWidget {
  const _InvoiceTile({required this.invoice});
  final InvoiceModel invoice;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusColor = invoice.status == 'paid'
        ? scheme.tertiary
        : invoice.status == 'cancelled'
            ? scheme.error
            : scheme.primary;
    return Card(
      child: ListTile(
        leading: Icon(Icons.receipt_long, color: statusColor),
        title: Text(invoice.number),
        subtitle: Text('${invoice.status.toUpperCase()} • ${invoice.date.toLocal().toString().split(' ').first}'),
        onTap: () => Get.to(() => InvoiceDetailScreen(invoiceId: invoice.id)),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text('₹${invoice.total.toStringAsFixed(2)}', style: Theme.of(context).textTheme.titleSmall),
            Text('Bal ₹${invoice.balance.toStringAsFixed(2)}', style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
