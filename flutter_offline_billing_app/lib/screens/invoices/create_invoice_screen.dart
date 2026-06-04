import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/invoice_controller.dart';
import '../../controllers/party_controller.dart';
import '../../controllers/product_controller.dart';
import '../../models/product_model.dart';
import '../../services/invoice_service.dart';
import '../../widgets/custom_button.dart';

class CreateInvoiceScreen extends StatefulWidget {
  const CreateInvoiceScreen({super.key});

  @override
  State<CreateInvoiceScreen> createState() => _CreateInvoiceScreenState();
}

class _CreateInvoiceScreenState extends State<CreateInvoiceScreen> {
  final _discount = TextEditingController(text: '0');
  final _paid = TextEditingController(text: '0');

  String? _partyId;
  final List<InvoiceDraftItem> _items = [];
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await Get.find<PartyController>().load(type: 'customer');
      await Get.find<ProductController>().load();
    });
  }

  @override
  void dispose() {
    _discount.dispose();
    _paid.dispose();
    super.dispose();
  }

  double get _subtotal => _items.fold(0, (sum, it) => sum + (it.qty * it.unitPrice));
  double get _tax => _items.fold(0, (sum, it) => sum + (it.qty * it.unitPrice * (it.product.taxPercent / 100.0)));
  double get _discountVal => double.tryParse(_discount.text.trim()) ?? 0;
  double get _total => (_subtotal - _discountVal) + _tax;

  Future<void> _addItem() async {
    final products = Get.find<ProductController>().items.toList(growable: false);
    if (products.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Add products first.')));
      return;
    }

    final selected = await showModalBottomSheet<ProductModel>(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return ListView.separated(
          padding: const EdgeInsets.all(12),
          itemCount: products.length,
          separatorBuilder: (_, __) => const Divider(height: 0),
          itemBuilder: (context, i) {
            final p = products[i];
            return ListTile(
              leading: const Icon(Icons.inventory_2),
              title: Text(p.name),
              subtitle: Text('₹${p.salePrice.toStringAsFixed(2)} • GST ${p.taxPercent.toStringAsFixed(0)}%'),
              onTap: () => Navigator.pop(context, p),
            );
          },
        );
      },
    );
    if (selected == null) return;

    final qtyStr = await _promptQty(defaultQty: 1);
    if (qtyStr == null) return;
    final qty = double.tryParse(qtyStr) ?? 0;
    if (qty <= 0) return;

    setState(() {
      _items.add(InvoiceDraftItem(product: selected, qty: qty));
    });
  }

  Future<String?> _promptQty({required double defaultQty}) async {
    final c = TextEditingController(text: defaultQty.toStringAsFixed(0));
    final res = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Quantity'),
        content: TextField(
          controller: c,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(labelText: 'Qty'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, c.text), child: const Text('Add')),
        ],
      ),
    );
    c.dispose();
    return res;
  }

  Future<void> _save() async {
    if (_partyId == null || _partyId!.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Select a customer')));
      return;
    }
    if (_items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Add at least one item')));
      return;
    }

    setState(() => _saving = true);
    try {
      final discount = double.tryParse(_discount.text.trim()) ?? 0;
      final paid = double.tryParse(_paid.text.trim()) ?? 0;
      await Get.find<InvoiceController>().create(
        partyId: _partyId!,
        draftItems: _items,
        discount: discount,
        paid: paid,
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
    final scheme = Theme.of(context).colorScheme;
    final parties = Get.find<PartyController>();

    return Scaffold(
      appBar: AppBar(title: const Text('Create Invoice')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Obx(() {
                  final customers = parties.items.where((p) => p.type == 'customer').toList();
                  return DropdownButtonFormField<String>(
                    initialValue: _partyId,
                    decoration: const InputDecoration(labelText: 'Customer'),
                    items: customers
                        .map((c) => DropdownMenuItem<String>(value: c.id, child: Text(c.name)))
                        .toList(growable: false),
                    onChanged: (v) => setState(() => _partyId = v),
                  );
                }),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Text('Items', style: Theme.of(context).textTheme.titleMedium),
                        const Spacer(),
                        TextButton.icon(
                          onPressed: _addItem,
                          icon: const Icon(Icons.add),
                          label: const Text('Add'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    if (_items.isEmpty)
                      Text('No items yet.', style: Theme.of(context).textTheme.bodySmall)
                    else
                      ..._items.map((it) {
                        return ListTile(
                          contentPadding: EdgeInsets.zero,
                          title: Text(it.product.name),
                          subtitle: Text('Qty ${it.qty} • ₹${it.unitPrice.toStringAsFixed(2)}'),
                          trailing: IconButton(
                            onPressed: () => setState(() => _items.remove(it)),
                            icon: const Icon(Icons.close),
                          ),
                        );
                      }),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _discount,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(labelText: 'Discount'),
                            onChanged: (_) => setState(() {}),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextField(
                            controller: _paid,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(labelText: 'Paid'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Subtotal'),
                        Text('₹${_subtotal.toStringAsFixed(2)}'),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('GST'),
                        Text('₹${_tax.toStringAsFixed(2)}'),
                      ],
                    ),
                    const Divider(),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Total', style: TextStyle(fontWeight: FontWeight.w700, color: scheme.primary)),
                        Text('₹${_total.toStringAsFixed(2)}', style: TextStyle(fontWeight: FontWeight.w700, color: scheme.primary)),
                      ],
                    ),
                    const SizedBox(height: 14),
                    Align(
                      alignment: Alignment.centerRight,
                      child: CustomButton(
                        label: 'Create',
                        icon: Icons.check,
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
