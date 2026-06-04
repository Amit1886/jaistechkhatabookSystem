import 'package:flutter/material.dart';

import 'dynamic_metadata.dart';

class DynamicFormRenderer extends StatefulWidget {
  final DynamicScreenMeta screen;
  final Map<String, dynamic> initialValue;
  final Future<void> Function(Map<String, dynamic> value) onSubmit;

  const DynamicFormRenderer({
    super.key,
    required this.screen,
    required this.onSubmit,
    this.initialValue = const {},
  });

  @override
  State<DynamicFormRenderer> createState() => _DynamicFormRendererState();
}

class _DynamicFormRendererState extends State<DynamicFormRenderer> {
  final _formKey = GlobalKey<FormState>();
  late final Map<String, dynamic> _value = Map<String, dynamic>.from(widget.initialValue);
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(widget.screen.title, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          for (final field in widget.screen.fields) ...[
            _buildField(field),
            const SizedBox(height: 12),
          ],
          FilledButton(
            onPressed: _saving ? null : _submit,
            child: _saving ? const CircularProgressIndicator() : const Text('Save'),
          ),
        ],
      ),
    );
  }

  Widget _buildField(DynamicFieldMeta field) {
    if (field.widget == 'date_picker') {
      return TextFormField(
        controller: TextEditingController(text: _value[field.name]?.toString() ?? ''),
        readOnly: true,
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
          suffixIcon: const Icon(Icons.calendar_today),
        ),
        validator: (v) => field.required && (v == null || v.trim().isEmpty) ? '${field.label} is required' : null,
        onTap: field.readOnly
            ? null
            : () async {
                final picked = await showDatePicker(
                  context: context,
                  firstDate: DateTime(2000),
                  lastDate: DateTime(2100),
                  initialDate: DateTime.tryParse(_value[field.name]?.toString() ?? '') ?? DateTime.now(),
                );
                if (picked != null) {
                  setState(() => _value[field.name] = picked.toIso8601String().split('T').first);
                }
              },
      );
    }
    if (field.widget == 'switch') {
      return SwitchListTile(
        title: Text(field.label),
        value: _value[field.name] == true,
        onChanged: field.readOnly ? null : (v) => setState(() => _value[field.name] = v),
      );
    }
    if (field.widget == 'select' && field.choices.isNotEmpty) {
      return DropdownButtonFormField<String>(
        value: _value[field.name]?.toString(),
        decoration: InputDecoration(labelText: field.label, border: const OutlineInputBorder()),
        items: field.choices.map((choice) {
          final map = choice as Map;
          return DropdownMenuItem<String>(
            value: map['value']?.toString(),
            child: Text(map['label']?.toString() ?? ''),
          );
        }).toList(),
        onChanged: field.readOnly ? null : (v) => _value[field.name] = v,
        validator: (v) => field.required && (v == null || v.isEmpty) ? '${field.label} is required' : null,
      );
    }
    if (field.widget == 'relation_dropdown' || field.widget == 'multi_select') {
      return TextFormField(
        initialValue: _value[field.name]?.toString() ?? '',
        readOnly: field.readOnly,
        keyboardType: TextInputType.number,
        decoration: InputDecoration(
          labelText: field.relation == null ? field.label : '${field.label} (${field.relation})',
          border: const OutlineInputBorder(),
          suffixIcon: const Icon(Icons.link),
        ),
        validator: (v) => field.required && (v == null || v.trim().isEmpty) ? '${field.label} is required' : null,
        onChanged: (v) => _value[field.name] = v,
      );
    }
    if (field.widget == 'file_picker') {
      return TextFormField(
        initialValue: _value[field.name]?.toString() ?? '',
        readOnly: true,
        decoration: InputDecoration(
          labelText: field.label,
          border: const OutlineInputBorder(),
          suffixIcon: const Icon(Icons.upload_file),
        ),
        onTap: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Upload will use backend media support when enabled.')),
          );
        },
      );
    }
    if (field.widget == 'json_editor') {
      return TextFormField(
        initialValue: _value[field.name]?.toString() ?? '{}',
        readOnly: field.readOnly,
        minLines: 3,
        maxLines: 8,
        decoration: InputDecoration(labelText: field.label, border: const OutlineInputBorder()),
        onChanged: (v) => _value[field.name] = v,
      );
    }
    return TextFormField(
      initialValue: _value[field.name]?.toString() ?? '',
      readOnly: field.readOnly,
      maxLines: field.widget == 'textarea' ? 4 : 1,
      keyboardType: field.widget == 'number' || field.widget == 'decimal' ? TextInputType.number : TextInputType.text,
      decoration: InputDecoration(labelText: field.label, border: const OutlineInputBorder()),
      validator: (v) => field.required && (v == null || v.trim().isEmpty) ? '${field.label} is required' : null,
      onChanged: (v) => _value[field.name] = v,
    );
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _saving = true);
    try {
      await widget.onSubmit(_value);
      if (mounted) Navigator.of(context).maybePop();
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}
