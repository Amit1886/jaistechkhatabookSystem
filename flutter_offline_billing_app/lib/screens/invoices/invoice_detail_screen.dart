import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../models/invoice_item_model.dart';
import '../../models/invoice_model.dart';
import '../../models/transaction_model.dart';
import '../../services/invoice_service.dart';

class InvoiceDetailScreen extends StatefulWidget {
  const InvoiceDetailScreen({super.key, required this.invoiceId});
  final String invoiceId;

  @override
  State<InvoiceDetailScreen> createState() => _InvoiceDetailScreenState();
}

class _InvoiceDetailScreenState extends State<InvoiceDetailScreen> {
  bool _loading = true;
  InvoiceModel? _invoice;
  List<InvoiceItemModel> _items = const [];
  List<TransactionModel> _txns = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final svc = Get.find<InvoiceService>();
      _invoice = await svc.getById(widget.invoiceId);
      _items = await svc.itemsForInvoice(widget.invoiceId);
      _txns = await svc.transactionsForInvoice(widget.invoiceId);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<Uint8List> _buildPdf(InvoiceModel invoice) async {
    final doc = pw.Document();

    doc.addPage(
      pw.Page(
        pageFormat: PdfPageFormat.a4,
        build: (ctx) {
          return pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.start,
            children: [
              pw.Text('JaisTech Billing', style: pw.TextStyle(fontSize: 20, fontWeight: pw.FontWeight.bold)),
              pw.SizedBox(height: 8),
              pw.Text('Invoice: ${invoice.number}'),
              pw.Text('Date: ${invoice.date.toLocal()}'),
              pw.SizedBox(height: 12),
              pw.TableHelper.fromTextArray(
                headers: const ['Item', 'Qty', 'Rate', 'Total'],
                data: [
                  for (final it in _items)
                    [
                      it.name,
                      it.qty.toStringAsFixed(2),
                      it.unitPrice.toStringAsFixed(2),
                      it.lineTotal.toStringAsFixed(2),
                    ],
                ],
                headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                cellAlignment: pw.Alignment.centerLeft,
              ),
              pw.SizedBox(height: 12),
              pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.end,
                children: [
                  pw.Column(
                    crossAxisAlignment: pw.CrossAxisAlignment.end,
                    children: [
                      pw.Text('Subtotal: ₹${invoice.subtotal.toStringAsFixed(2)}'),
                      pw.Text('GST: ₹${invoice.tax.toStringAsFixed(2)}'),
                      pw.Text('Discount: ₹${invoice.discount.toStringAsFixed(2)}'),
                      pw.SizedBox(height: 4),
                      pw.Text('Total: ₹${invoice.total.toStringAsFixed(2)}', style: pw.TextStyle(fontWeight: pw.FontWeight.bold)),
                      pw.Text('Paid: ₹${invoice.paid.toStringAsFixed(2)}'),
                      pw.Text('Balance: ₹${invoice.balance.toStringAsFixed(2)}'),
                    ],
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );

    return doc.save();
  }

  Future<void> _sharePdf() async {
    final invoice = _invoice;
    if (invoice == null) return;
    final bytes = await _buildPdf(invoice);
    await Printing.sharePdf(bytes: bytes, filename: '${invoice.number}.pdf');
  }

  Future<void> _shareWhatsApp() async {
    final invoice = _invoice;
    if (invoice == null) return;
    final text = Uri.encodeComponent('Invoice ${invoice.number} Total ₹${invoice.total.toStringAsFixed(2)}');
    final uri = Uri.parse('https://wa.me/?text=$text');
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Invoice'),
        actions: [
          IconButton(onPressed: _sharePdf, icon: const Icon(Icons.picture_as_pdf), tooltip: 'Share PDF'),
          IconButton(onPressed: _shareWhatsApp, icon: const Icon(Icons.chat), tooltip: 'WhatsApp'),
        ],
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _invoice == null
                ? Center(child: Text('Invoice not found', style: TextStyle(color: scheme.error)))
                : ListView(
                    padding: const EdgeInsets.all(12),
                    children: [
                      Card(
                        child: ListTile(
                          title: Text(_invoice!.number),
                          subtitle: Text(_invoice!.status.toUpperCase()),
                          trailing: Text('₹${_invoice!.total.toStringAsFixed(2)}'),
                        ),
                      ),
                      const SizedBox(height: 10),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('Items', style: Theme.of(context).textTheme.titleMedium),
                              const SizedBox(height: 8),
                              ..._items.map((it) => ListTile(
                                    contentPadding: EdgeInsets.zero,
                                    title: Text(it.name),
                                    subtitle: Text('Qty ${it.qty} • ₹${it.unitPrice.toStringAsFixed(2)}'),
                                    trailing: Text('₹${it.lineTotal.toStringAsFixed(2)}'),
                                  )),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('Payments', style: Theme.of(context).textTheme.titleMedium),
                              const SizedBox(height: 8),
                              if (_txns.isEmpty)
                                Text('No payments yet.', style: Theme.of(context).textTheme.bodySmall)
                              else
                                ..._txns.map((t) => ListTile(
                                      contentPadding: EdgeInsets.zero,
                                      title: Text('₹${t.amount.toStringAsFixed(2)}'),
                                      subtitle: Text('${t.mode} • ${t.date.toLocal().toString().split(' ').first}'),
                                    )),
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
