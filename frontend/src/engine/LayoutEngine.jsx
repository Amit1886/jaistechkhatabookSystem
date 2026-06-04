import React from "react";

import ModeSwitchControl from "../components/ModeSwitchControl";
import EnterpriseUIEngine from "./EnterpriseUIEngine";
import { useSystemMode } from "../hooks/useSystemMode";
import AdminSuperLayout from "../layouts/AdminSuperLayout";
import DesktopLayout from "../layouts/DesktopLayout";
import MobileLayout from "../layouts/MobileLayout";
import POSLayout from "../layouts/POSLayout";
import TabletLayout from "../layouts/TabletLayout";

function pickLayout(mode) {
  switch (mode) {
    case "POS":
      return POSLayout;
    case "MOBILE":
      return MobileLayout;
    case "TABLET":
      return TabletLayout;
    case "ADMIN_SUPER":
      return AdminSuperLayout;
    case "DESKTOP":
    default:
      return DesktopLayout;
  }
}

export default function LayoutEngine() {
  const { modeState, resolvedMode, loading } = useSystemMode();
  const CurrentLayout = pickLayout(resolvedMode);
  const enterpriseEnabled = new URLSearchParams(window.location.search).get("enterprise") === "1";

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading system mode...</div>;
  }

  if (enterpriseEnabled) {
    return <EnterpriseUIEngine />;
  }

  return (
    <div>
      <div className="fixed right-3 top-3 z-50 w-72">
        <ModeSwitchControl modeState={modeState} onChanged={() => {}} />
      </div>
      <CurrentLayout />
    </div>
  );
}
