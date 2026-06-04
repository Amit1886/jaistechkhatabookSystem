import 'package:flutter/material.dart';

class EnterpriseIcons {
  const EnterpriseIcons._();

  static IconData fromName(String name) {
    return switch (name) {
      'dashboard' => Icons.dashboard,
      'layout-dashboard' => Icons.space_dashboard,
      'point_of_sale' => Icons.point_of_sale,
      'shopping-bag' => Icons.shopping_bag,
      'shopping_cart_checkout' => Icons.shopping_cart_checkout,
      'scan-line' => Icons.qr_code_scanner,
      'inventory_2' => Icons.inventory_2,
      'boxes' => Icons.inventory_2,
      'receipt_long' => Icons.receipt_long,
      'receipt' => Icons.receipt_long,
      'groups' => Icons.groups,
      'users' => Icons.groups,
      'bar_chart' => Icons.bar_chart,
      'bar-chart-3' => Icons.bar_chart,
      'line-chart' => Icons.show_chart,
      'auto_awesome' => Icons.auto_awesome,
      'payments' => Icons.payments,
      'store' => Icons.storefront,
      'truck' => Icons.local_shipping,
      'clipboard-list' => Icons.assignment,
      'local_shipping' => Icons.local_shipping,
      'settings' => Icons.settings,
      'account_balance' => Icons.account_balance,
      'account_tree' => Icons.account_tree,
      'category' => Icons.category,
      'language' => Icons.language,
      'badge' => Icons.badge,
      'shopping_cart' => Icons.shopping_cart,
      'business_center' => Icons.business_center,
      'admin_panel_settings' => Icons.admin_panel_settings,
      'api' => Icons.api,
      'person' => Icons.person,
      'delivery_dining' => Icons.delivery_dining,
      'android' => Icons.android,
      'notifications' => Icons.notifications,
      'sync' => Icons.sync,
      'print' => Icons.print,
      'workspace_premium' => Icons.workspace_premium,
      _ => Icons.apps,
    };
  }
}
