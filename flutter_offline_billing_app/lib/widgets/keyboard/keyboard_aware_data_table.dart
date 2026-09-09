import 'package:flutter/material.dart';

class KeyboardAwareDataTable extends StatelessWidget {
  final List<String> columns;
  final List<List<String>> rows;
  final FocusNode? focusNode;

  const KeyboardAwareDataTable({
    super.key,
    required this.columns,
    required this.rows,
    this.focusNode,
  });

  @override
  Widget build(BuildContext context) {
    return Focus(
      focusNode: focusNode,
      child: DataTable(
        columns: columns.map((c) => DataColumn(label: Text(c))).toList(),
        rows: rows
            .map((row) => DataRow(cells: row.map((cell) => DataCell(Text(cell))).toList()))
            .toList(),
      ),
    );
  }
}
