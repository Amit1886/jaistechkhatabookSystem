import React from "react";
import { closeWorkspaceTab, setErpState, useErpStore } from "../../store/erpUiStore";
import DashboardBuilder from "./DashboardBuilder";
import DynamicTable from "./DynamicTable";
import NotificationCenter from "./NotificationCenter";
import { ERPCard } from "./DesignSystem";

function ModulePage({ moduleKey }) {
  const live = useErpStore((state) => state.liveData) || {};
  const reports = useErpStore((state) => state.reports) || [];
  const apiStatus = useErpStore((state) => state.apiStatus) || {};
  const settings = live.settings || {};

  if (moduleKey === "pos") return <POSModule products={live.products || []} />;
  if (moduleKey === "billing") return <BillingModule invoices={live.invoices || []} orders={live.orders || []} />;
  if (moduleKey === "crm") return <CRMModule customers={live.customers || []} />;
  if (moduleKey === "inventory" || moduleKey === "products") return <InventoryModule products={live.products || []} />;
  if (moduleKey === "reports") return <ReportsModule reports={live.reports || reports} sales={live.sales || {}} />;
  if (moduleKey === "settings") return <SettingsModule settings={settings} apiStatus={apiStatus} />;
  if (moduleKey === "profile") return <ProfileModule settings={settings} />;
  if (moduleKey === "notifications") return <NotificationCenter />;
  if (moduleKey === "devices") return <DevicesModule apiStatus={apiStatus} sales={live.sales || {}} />;
  return <DynamicTable title={`${moduleKey} Records`} rows={[]} />;
}

function POSModule({ products }) {
  const cart = products.slice(0, 3).map((product, index) => ({ ...product, qty: index + 1 }));
  const total = cart.reduce((sum, product) => sum + Number(product.price || 0) * product.qty, 0);
  return (
    <div className="module-grid pos-grid">
      <ERPCard title="Products">
        <div className="product-grid">
          {products.map((product) => (
            <button key={product.id}>
              <strong>{product.name}</strong>
              <span>{product.sku}</span>
              <b>Rs {product.price}</b>
            </button>
          ))}
        </div>
      </ERPCard>
      <ERPCard title="Cart">
        <div className="feed-list">
          {cart.map((product) => <p key={product.id}><strong>{product.name}</strong><span>{product.qty} x Rs {product.price}</span></p>)}
        </div>
        <div className="module-total"><span>Total</span><strong>Rs {total.toFixed(2)}</strong></div>
      </ERPCard>
      <ERPCard title="Payment And Receipt">
        <div className="payment-grid">
          {["Cash", "UPI", "Card"].map((mode) => <button key={mode}>{mode}</button>)}
        </div>
        <div className="receipt-box">
          <strong>Receipt Preview</strong>
          <span>Items {cart.length}</span>
          <span>Barcode scanner: connected by API config</span>
        </div>
      </ERPCard>
    </div>
  );
}

function BillingModule({ invoices, orders }) {
  return (
    <div className="module-grid">
      <DynamicTable title="Invoices" rows={invoices} />
      <DynamicTable title="Orders" rows={orders} />
      <ERPCard title="GST Ledger">
        <div className="feed-list">
          {invoices.map((invoice) => <p key={invoice.id}><strong>{invoice.number}</strong><span>{invoice.gst_type} | {invoice.status} | Rs {invoice.amount}</span></p>)}
        </div>
      </ERPCard>
    </div>
  );
}

function CRMModule({ customers }) {
  const leads = customers.filter((customer) => customer.type === "customer");
  return (
    <div className="module-grid">
      <DynamicTable title="Customers" rows={customers} />
      <ERPCard title="Leads And Followups">
        <div className="feed-list">
          {leads.map((lead) => <p key={lead.id}><strong>{lead.name}</strong><span>{lead.mobile} | Grade {lead.grade} | Score {lead.credit_score}</span></p>)}
        </div>
      </ERPCard>
    </div>
  );
}

function InventoryModule({ products }) {
  return (
    <div className="module-grid">
      <DynamicTable title="Products And Stock" rows={products} />
      <ERPCard title="Categories And Brands">
        <div className="tag-cloud">
          {[...new Set(products.map((product) => product.category).filter(Boolean))].map((category) => <span key={category}>{category}</span>)}
          {[...new Set(products.map((product) => product.brand).filter(Boolean))].map((brand) => <span key={brand}>{brand}</span>)}
        </div>
      </ERPCard>
    </div>
  );
}

function ReportsModule({ reports, sales }) {
  return (
    <div className="module-grid">
      <ERPCard title="Report Catalog">
        <div className="report-card-grid">
          {reports.map((report) => (
            <button key={report.key}>
              <strong>{report.title || report.label}</strong>
              <span>Rows {report.rows ?? report.columns?.length ?? 0}</span>
              <b>{report.metric || "Ready"}</b>
            </button>
          ))}
        </div>
      </ERPCard>
      <ERPCard title="Sales Summary">
        <div className="settings-list">
          {Object.entries(sales).map(([key, value]) => <p key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></p>)}
        </div>
      </ERPCard>
    </div>
  );
}

function SettingsModule({ settings, apiStatus }) {
  const rows = apiStatus.results || [];
  return (
    <div className="module-grid">
      <ProfileModule settings={settings} />
      <ERPCard title="API Status">
        <div className="api-status-list">
          {rows.slice(0, 20).map((api) => <p key={`${api.method}-${api.endpoint}`}><strong>{api.method} {api.endpoint}</strong><span>{api.module} | {api.status}</span></p>)}
        </div>
      </ERPCard>
    </div>
  );
}

function ProfileModule({ settings }) {
  return (
    <ERPCard title="Profile">
      <div className="settings-list">
        <p><span>User</span><strong>{settings.profile?.name || settings.profile?.username || "Demo Test 3"}</strong></p>
        <p><span>Business</span><strong>{settings.business?.name || "Demo Business"}</strong></p>
        <p><span>Plan</span><strong>{settings.plan?.name || "Premium Plan 999"}</strong></p>
        <p><span>Email</span><strong>{settings.profile?.email || "demotest3@example.com"}</strong></p>
      </div>
    </ERPCard>
  );
}

function DevicesModule({ apiStatus, sales }) {
  return (
    <div className="module-grid">
      <ERPCard title="Connected APIs">
        <div className="settings-list">
          {Object.entries(apiStatus.summary || {}).map(([key, value]) => <p key={key}><span>{key}</span><strong>{value}</strong></p>)}
        </div>
      </ERPCard>
      <ERPCard title="Active Devices">
        <div className="settings-list">
          <p><span>Active devices</span><strong>{sales.active_devices || 0}</strong></p>
          <p><span>Live users</span><strong>{sales.live_users || 0}</strong></p>
        </div>
      </ERPCard>
    </div>
  );
}

function TabContent({ tab }) {
  if (tab.type === "dashboard") return <DashboardBuilder />;
  return <ModulePage moduleKey={tab.module || tab.id} />;
}

export default function TabbedWorkspace() {
  const tabs = useErpStore((state) => state.tabs);
  const activeTab = useErpStore((state) => state.activeTab);
  const active = tabs.find((tab) => tab.id === activeTab) || tabs[0];

  return (
    <main className="tabbed-workspace">
      <div className="workspace-tabs">
        {tabs.map((tab) => (
          <button key={tab.id} className={tab.id === activeTab ? "active" : ""} onClick={() => setErpState({ activeTab: tab.id })}>
            {tab.title}
            {tab.id !== "dashboard" && <span onClick={(event) => { event.stopPropagation(); closeWorkspaceTab(tab.id); }}>x</span>}
          </button>
        ))}
      </div>
      <TabContent tab={active} />
    </main>
  );
}
