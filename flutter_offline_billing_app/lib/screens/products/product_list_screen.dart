import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/product_controller.dart';
import '../../models/product_model.dart';
import 'add_product_screen.dart';

class ProductListScreen extends StatefulWidget {
  const ProductListScreen({super.key});

  @override
  State<ProductListScreen> createState() => _ProductListScreenState();
}

class _ProductListScreenState extends State<ProductListScreen> {
  final _q = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => Get.find<ProductController>().load());
  }

  @override
  void dispose() {
    _q.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = Get.find<ProductController>();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: TextField(
            controller: _q,
            decoration: const InputDecoration(
              prefixIcon: Icon(Icons.search),
              labelText: 'Search product',
            ),
            onChanged: (v) => c.load(query: v),
          ),
        ),
        Expanded(
          child: Obx(() {
            if (c.isLoading.value) {
              return const Center(child: CircularProgressIndicator());
            }
            final rows = c.items;
            if (rows.isEmpty) {
              return const Center(child: Text('No products yet. Tap + to add.'));
            }
            return RefreshIndicator(
              onRefresh: () => c.load(query: _q.text),
              child: ListView.separated(
                padding: const EdgeInsets.all(12),
                itemCount: rows.length,
                separatorBuilder: (_, __) => const SizedBox(height: 8),
                itemBuilder: (context, i) => _ProductTile(
                  product: rows[i],
                  onDelete: () => c.remove(rows[i].id),
                ),
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
                await Get.to(() => const AddProductScreen());
                await c.load(query: _q.text);
              },
              icon: const Icon(Icons.add),
              label: const Text('Add Product'),
            ),
          ),
        ),
      ],
    );
  }
}

class _ProductTile extends StatelessWidget {
  const _ProductTile({required this.product, required this.onDelete});

  final ProductModel product;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey(product.id),
      direction: DismissDirection.endToStart,
      confirmDismiss: (_) async {
        return await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Delete product?'),
                content: Text('Delete "${product.name}"?'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                  FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
                ],
              ),
            ) ??
            false;
      },
      onDismissed: (_) => onDelete(),
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        color: Theme.of(context).colorScheme.errorContainer,
        child: const Icon(Icons.delete),
      ),
      child: Card(
        child: ListTile(
          leading: const Icon(Icons.inventory_2),
          title: Text(product.name),
          subtitle: Text(
            [
              if (product.sku != null && product.sku!.isNotEmpty) 'SKU: ${product.sku}',
              '₹${product.salePrice.toStringAsFixed(2)}',
            ].join(' • '),
          ),
          trailing: product.isSynced ? const Icon(Icons.cloud_done, size: 18) : const Icon(Icons.cloud_off, size: 18),
        ),
      ),
    );
  }
}

