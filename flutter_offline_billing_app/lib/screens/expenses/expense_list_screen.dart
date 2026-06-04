import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../controllers/expense_controller.dart';
import '../../models/expense_model.dart';
import 'add_expense_screen.dart';

class ExpenseListScreen extends StatefulWidget {
  const ExpenseListScreen({super.key});

  @override
  State<ExpenseListScreen> createState() => _ExpenseListScreenState();
}

class _ExpenseListScreenState extends State<ExpenseListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => Get.find<ExpenseController>().load());
  }

  @override
  Widget build(BuildContext context) {
    final c = Get.find<ExpenseController>();
    return Scaffold(
      appBar: AppBar(title: const Text('Expenses')),
      body: SafeArea(
        child: Obx(() {
          if (c.isLoading.value) return const Center(child: CircularProgressIndicator());
          final rows = c.items;
          if (rows.isEmpty) return const Center(child: Text('No expenses yet.'));
          return RefreshIndicator(
            onRefresh: c.load,
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: rows.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (context, i) => _ExpenseTile(expense: rows[i], onDelete: () => c.remove(rows[i].id)),
            ),
          );
        }),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Get.to(() => const AddExpenseScreen());
          await c.load();
        },
        icon: const Icon(Icons.add),
        label: const Text('Add Expense'),
      ),
    );
  }
}

class _ExpenseTile extends StatelessWidget {
  const _ExpenseTile({required this.expense, required this.onDelete});
  final ExpenseModel expense;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey(expense.id),
      direction: DismissDirection.endToStart,
      confirmDismiss: (_) async {
        return await showDialog<bool>(
              context: context,
              builder: (context) => AlertDialog(
                title: const Text('Delete expense?'),
                content: const Text('This will remove the expense locally (will sync later).'),
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
          leading: const Icon(Icons.receipt),
          title: Text('₹${expense.amount.toStringAsFixed(2)}'),
          subtitle: Text('${expense.category ?? 'Expense'} • ${expense.date.toLocal().toString().split(' ').first}'),
          trailing: expense.isSynced ? const Icon(Icons.cloud_done, size: 18) : const Icon(Icons.cloud_off, size: 18),
        ),
      ),
    );
  }
}

