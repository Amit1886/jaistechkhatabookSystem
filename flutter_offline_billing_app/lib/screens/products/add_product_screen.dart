import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/product_controller.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_textfield.dart';
import 'barcode_scanner_screen.dart';

class AddProductScreen extends StatefulWidget {
  const AddProductScreen({super.key});

  @override
  State<AddProductScreen> createState() => _AddProductScreenState();
}

class _AddProductScreenState extends State<AddProductScreen> {
  final _name = TextEditingController();
  final _sku = TextEditingController();
  final _barcode = TextEditingController();
  final _salePrice = TextEditingController(text: '0');
  final _tax = TextEditingController(text: '0');

  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _sku.dispose();
    _barcode.dispose();
    _salePrice.dispose();
    _tax.dispose();
    super.dispose();
  }

  Future<void> _scan() async {
    final code = await Get.to<String>(() => const BarcodeScannerScreen());
    if (code == null) return;
    _barcode.text = code;
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final price = double.tryParse(_salePrice.text.trim()) ?? 0;
      final tax = double.tryParse(_tax.text.trim()) ?? 0;
      await Get.find<ProductController>().add(
        name: _name.text,
        sku: _sku.text,
        barcode: _barcode.text,
        salePrice: price,
        taxPercent: tax,
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
      appBar: AppBar(title: const Text('Add Product')),
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
                      controller: _name,
                      label: 'Product Name',
                      prefixIcon: Icons.inventory_2,
                    ),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _sku,
                      label: 'SKU (optional)',
                      prefixIcon: Icons.qr_code_2,
                    ),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _barcode,
                      label: 'Barcode (optional)',
                      prefixIcon: Icons.qr_code,
                      suffixIcon: Icons.camera_alt,
                      onSuffixTap: _scan,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: CustomTextField(
                            controller: _salePrice,
                            label: 'Sale Price',
                            keyboardType: TextInputType.number,
                            prefixIcon: Icons.currency_rupee,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: CustomTextField(
                            controller: _tax,
                            label: 'GST %',
                            keyboardType: TextInputType.number,
                            prefixIcon: Icons.percent,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Align(
                      alignment: Alignment.centerRight,
                      child: CustomButton(
                        label: 'Save',
                        loading: _saving,
                        icon: Icons.save,
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

