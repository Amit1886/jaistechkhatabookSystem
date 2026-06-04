import 'package:flutter/material.dart';

class ModuleIcon {
  static IconData fromKey(String key) {
    switch (key) {
      case 'products':
        return Icons.inventory_2_outlined;
      case 'pos':
        return Icons.point_of_sale_outlined;
      case 'crm':
        return Icons.people_alt_outlined;
      case 'reports':
        return Icons.bar_chart_outlined;
      case 'stores':
        return Icons.storefront_outlined;
      case 'accounting':
        return Icons.account_balance_outlined;
      case 'self_checkout':
        return Icons.qr_code_scanner_outlined;
      case 'ecommerce':
        return Icons.public_outlined;
      default:
        return Icons.apps_outlined;
    }
  }
}

