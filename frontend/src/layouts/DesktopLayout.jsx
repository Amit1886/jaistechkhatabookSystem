import React from "react";

import AppHeader from "../components/shared/AppHeader";
import AppShell from "../components/shared/AppShell";
import BillingHierarchyCard from "../components/BillingHierarchyCard";

function Sidebar() {
  return (
    <aside className="rounded-xl bg-slate-900 p-4 text-white shadow">
      <div className="mb-3 text-sm font-semibold">ERP Navigation</div>
      <ul className="space-y-2 text-sm text-slate-200">
        {["Dashboard", "Billing", "Inventory", "Warehouse", "Analytics", "Settings"].map((item) => (
          <li key={item} className="rounded px-2 py-1 hover:bg-slate-800">
            {item}
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default function DesktopLayout() {
  return (
    <AppShell>
      <AppHeader title="Desktop Mode" subtitle="Full ERP multi-panel layout" />
      <main className="mt-4 grid grid-cols-12 gap-4">
        <div className="col-span-12 xl:col-span-3">
          <Sidebar />
        </div>
        <div className="col-span-12 xl:col-span-9 space-y-4">
          <BillingHierarchyCard />
          <section className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold">Analytics Dashboard</h2>
            <div className="mt-3 grid grid-cols-2 gap-3">
              {["Sales", "Profit", "Orders", "Fast Movers"].map((item) => (
                <div key={item} className="rounded border p-3 text-sm">
                  {item}
                </div>
              ))}
            </div>
          </section>
          <section className="rounded-xl bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold">Operations</h2>
            <div className="mt-2 text-sm text-slate-600">
              Multi-panel workspace for inventory, payments, and fulfillment.
            </div>
          </section>
        </div>
      </main>
    </AppShell>
  );
}
