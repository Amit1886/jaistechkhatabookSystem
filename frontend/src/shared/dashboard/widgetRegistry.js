export const ROLE_WIDGETS = {
  admin: ["revenue", "active_users", "tenant_health", "approval_queue", "system_alerts"],
  manager: ["sales", "inventory", "collections", "workflow_queue"],
  cashier: ["today_billing", "payments", "pending_orders"],
  accountant: ["gst", "ledgers", "trial_balance", "payment_alerts"],
  warehouse: ["stock_low", "transfers", "procurement", "forecast"],
  salesman: ["route", "collections", "van_stock", "targets"],
};

export const WIDGET_DEFINITIONS = {
  revenue: { title: "Revenue", type: "kpi", query: "revenue_summary" },
  active_users: { title: "Active Users", type: "kpi", query: "active_users" },
  tenant_health: { title: "Tenant Health", type: "health", query: "tenant_health" },
  approval_queue: { title: "Approval Queue", type: "approval", query: "approval_queue" },
  system_alerts: { title: "System Alerts", type: "feed", query: "system_alerts" },
  sales: { title: "Sales", type: "chart", query: "sales_summary" },
  inventory: { title: "Inventory", type: "table", query: "inventory_summary" },
  collections: { title: "Collections", type: "kpi", query: "collection_summary" },
  workflow_queue: { title: "Workflow Queue", type: "workflow", query: "workflow_queue" },
  today_billing: { title: "Today Billing", type: "kpi", query: "today_billing" },
  payments: { title: "Payments", type: "table", query: "payment_summary" },
  pending_orders: { title: "Pending Orders", type: "table", query: "pending_orders" },
  gst: { title: "GST", type: "kpi", query: "gst_summary" },
  ledgers: { title: "Ledgers", type: "table", query: "ledger_summary" },
  trial_balance: { title: "Trial Balance", type: "report", query: "trial_balance" },
  payment_alerts: { title: "Payment Alerts", type: "feed", query: "payment_alerts" },
  stock_low: { title: "Low Stock", type: "feed", query: "stock_low" },
  transfers: { title: "Transfers", type: "table", query: "warehouse_transfers" },
  procurement: { title: "Procurement", type: "workflow", query: "procurement_queue" },
  forecast: { title: "Forecast", type: "chart", query: "inventory_forecast" },
  route: { title: "Route", type: "map", query: "salesman_route" },
  van_stock: { title: "Van Stock", type: "table", query: "van_stock" },
  targets: { title: "Targets", type: "kpi", query: "salesman_targets" },
};

export function widgetsForRole(role = "manager") {
  return (ROLE_WIDGETS[role] || ROLE_WIDGETS.manager).map((key) => ({ key, ...WIDGET_DEFINITIONS[key] }));
}

