import 'package:flutter/material.dart';

class BIDataCard extends StatelessWidget {
  final String title;
  final String value;
  final String? trend;
  final Color? trendColor;

  const BIDataCard({
    super.key,
    required this.title,
    required this.value,
    this.trend,
    this.trendColor,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 8),
            Text(value, style: Theme.of(context).textTheme.headlineMedium),
            if (trend != null)
              Text(trend!, style: TextStyle(color: trendColor ?? Colors.green)),
          ],
        ),
      ),
    );
  }
}

class BIChartCard extends StatelessWidget {
  final String title;
  final Widget chart;

  const BIChartCard({super.key, required this.title, required this.chart});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 16),
            SizedBox(height: 200, child: chart),
          ],
        ),
      ),
    );
  }
}
