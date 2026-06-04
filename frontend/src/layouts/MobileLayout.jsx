import React from "react";

import BottomNav from "../components/shared/BottomNav";
import AppHeader from "../components/shared/AppHeader";
import AppShell from "../components/shared/AppShell";
import LiveStreamPanel from "../modules/realtime/LiveStreamPanel";

export default function MobileLayout() {
  return (
    <AppShell className="pb-20">
      <AppHeader title="Mobile Mode" subtitle="Compact one-column workflow" />

      <main className="mt-4 space-y-3">
        <section className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold">Quick Actions</h2>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {["New Sale", "Collections", "Inventory", "Reports"].map((item) => (
              <button key={item} className="rounded-lg bg-slate-900 px-3 py-3 text-sm text-white">
                {item}
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-xl bg-white p-4 shadow-sm">
          <h2 className="text-sm font-semibold">Live Feeds</h2>
          <LiveStreamPanel />
        </section>
      </main>

      <BottomNav />
    </AppShell>
  );
}
