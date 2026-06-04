export const SEARCH_SCOPES = [
  { key: "invoices", label: "Invoices", query: "invoice_search" },
  { key: "customers", label: "Customers", query: "customer_search" },
  { key: "products", label: "Products", query: "product_search" },
  { key: "payments", label: "Payments", query: "payment_search" },
  { key: "reports", label: "Reports", query: "report_search" },
  { key: "ledgers", label: "Ledgers", query: "ledger_search" },
  { key: "orders", label: "Orders", query: "order_search" },
];

export function normalizeSearchResult(scope, row) {
  return {
    id: row.id || row.pk || `${scope.key}-${row.name || row.number || row.code}`,
    scope: scope.key,
    title: row.title || row.name || row.invoice_number || row.order_number || row.code || "Untitled",
    subtitle: row.customer || row.party || row.status || scope.label,
    url: row.url || row.absolute_url || "",
    raw: row,
  };
}

