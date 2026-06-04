import 'package:flutter/material.dart';

import '../services/invoice_service.dart';

class InvoiceItemWidget extends StatelessWidget {
  const InvoiceItemWidget({super.key, required this.item, required this.onRemove});

  final InvoiceDraftItem item;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(item.product.name),
      subtitle: Text('Qty ${item.qty} • ₹${item.unitPrice.toStringAsFixed(2)} • GST ${item.product.taxPercent.toStringAsFixed(0)}%'),
      trailing: IconButton(onPressed: onRemove, icon: const Icon(Icons.close)),
    );
  }
}

