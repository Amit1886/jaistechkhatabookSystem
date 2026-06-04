import React from "react";
import { openWorkspaceTab, useErpStore } from "../../store/erpUiStore";
import { ERPCard, KPIWidget } from "./DesignSystem";

export default function DashboardBuilder() {
  const appConfig = useErpStore((state) => state.appConfig);
  const liveData = useErpStore((state) => state.liveData) || {};
  const activity = useErpStore((state) => state.activity);
  const buttons = useErpStore((state) => state.buttons);
  const kpis = appConfig?.dashboard_config?.kpis || [];
  const topProducts = liveData.top_products || [];
  const invoices = liveData.recent_invoices || [];

  return (
    <div className="dashboard-grid">
      {kpis.map((item, index) => (
        <KPIWidget key={item.key} label={item.label} value={`${item.prefix ? `${item.prefix} ` : ""}${item.value}`} tone={["green", "blue", "violet", "amber"][index % 4]} detail="live API" />
      ))}
      <KPIWidget label="Live Users" value={activity?.users_online ?? "-"} tone="green" detail="active accounts" />
      <KPIWidget label="Active Devices" value={activity?.active_devices ?? "0"} tone="amber" detail="registered sessions" />
      <ERPCard title="Quick Actions" className="wide-card quick-actions-card">
        <div className="quick-action-grid">
          {buttons.slice(0, 8).map((button) => (
            <button
              key={button.key}
              style={{ borderColor: button.color, background: `linear-gradient(135deg, ${button.color}22, rgba(255,255,255,.04))` }}
              onClick={() => openWorkspaceTab({ id: button.module || button.key, title: button.label, type: "module", route: button.route, module: button.module })}
            >
              <strong>{button.label}</strong>
              <span>{button.description || button.route}</span>
            </button>
          ))}
        </div>
      </ERPCard>
      <ERPCard title="Revenue Pulse" className="wide-card">
        <div className="chart-placeholder">
          {invoices.slice(0, 8).map((invoice, index) => (
            <span key={invoice.id || index} title={invoice.number} style={{ height: `${Math.max(24, Math.min(96, Number(invoice.amount || 0) / 80))}%` }} />
          ))}
        </div>
      </ERPCard>
      <ERPCard title="Top Products">
        <div className="feed-list">
          {topProducts.slice(0, 6).map((product) => (
            <p key={product.id}>
              <strong>{product.name}</strong>
              <span>{product.sku} | Stock {product.stock} | Rs {product.price}</span>
            </p>
          ))}
        </div>
      </ERPCard>
      <ERPCard title="Recent Invoices" className="wide-card">
        <div className="invoice-strip">
          {invoices.slice(0, 8).map((invoice) => (
            <button key={invoice.id} onClick={() => openWorkspaceTab({ id: "billing", title: "Billing", type: "module", module: "billing" })}>
              <strong>{invoice.number}</strong>
              <span>{invoice.customer}</span>
              <b>Rs {invoice.amount}</b>
            </button>
          ))}
        </div>
      </ERPCard>
    </div>
  );
}
