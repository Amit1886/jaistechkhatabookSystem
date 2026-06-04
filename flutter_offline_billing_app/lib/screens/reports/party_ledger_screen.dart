import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../models/party_model.dart';
import '../../models/transaction_model.dart';
import '../../services/party_service.dart';
import '../../services/settings_service.dart';
import '../../services/transaction_service.dart';

class PartyLedgerScreen extends StatefulWidget {
  const PartyLedgerScreen({super.key});

  @override
  State<PartyLedgerScreen> createState() => _PartyLedgerScreenState();
}

class _PartyLedgerScreenState extends State<PartyLedgerScreen> {
  bool _loading = true;
  List<PartyModel> _parties = const [];
  List<TransactionModel> _txns = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final businessId = Get.find<SettingsService>().selectedBusinessId;
      _parties = await Get.find<PartyService>().list(businessId: businessId, type: 'customer');
      _txns = await Get.find<TransactionService>().list(businessId: businessId);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  double _netFor(String partyId) {
    double net = 0;
    for (final t in _txns.where((x) => x.partyId == partyId)) {
      if (t.type == 'payment_in') net += t.amount;
      if (t.type == 'payment_out') net -= t.amount;
    }
    return net;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Party Ledger')),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView.separated(
                  padding: const EdgeInsets.all(12),
                  itemCount: _parties.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final p = _parties[i];
                    final net = _netFor(p.id);
                    return Card(
                      child: ListTile(
                        leading: const Icon(Icons.person),
                        title: Text(p.name),
                        subtitle: Text('Net received: ₹${net.toStringAsFixed(2)}'),
                      ),
                    );
                  },
                ),
              ),
      ),
    );
  }
}

