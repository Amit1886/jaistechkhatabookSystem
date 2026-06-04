import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/party_controller.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_textfield.dart';

class AddPartyScreen extends StatefulWidget {
  const AddPartyScreen({super.key, required this.type});
  final String type; // customer | supplier

  @override
  State<AddPartyScreen> createState() => _AddPartyScreenState();
}

class _AddPartyScreenState extends State<AddPartyScreen> {
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();

  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _address.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await Get.find<PartyController>().add(
        type: widget.type,
        name: _name.text,
        phone: _phone.text,
        address: _address.text,
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
    final title = widget.type == 'customer' ? 'Add Customer' : 'Add Supplier';
    return Scaffold(
      appBar: AppBar(title: Text(title)),
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
                      label: 'Name',
                      prefixIcon: Icons.badge,
                    ),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _phone,
                      label: 'Phone',
                      keyboardType: TextInputType.phone,
                      prefixIcon: Icons.phone,
                    ),
                    const SizedBox(height: 12),
                    CustomTextField(
                      controller: _address,
                      label: 'Address',
                      prefixIcon: Icons.location_on,
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

