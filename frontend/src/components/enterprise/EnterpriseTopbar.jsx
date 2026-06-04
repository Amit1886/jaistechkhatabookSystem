import React from "react";
import { setErpState, useErpStore } from "../../store/erpUiStore";
import { ERPButton, StatusDot } from "./DesignSystem";

export default function EnterpriseTopbar() {
  const status = useErpStore((state) => state.realtimeStatus);
  const notifications = useErpStore((state) => state.notifications);
  const splitView = useErpStore((state) => state.splitView);
  const appConfig = useErpStore((state) => state.appConfig);

  return (
    <header className="enterprise-topbar">
      <div className="breadcrumbs">
        <span>{appConfig?.user_context?.business?.name || "Demo Business"}</span>
        <strong>{appConfig?.workspace?.name || "Enterprise Workspace"}</strong>
      </div>
      <div className="topbar-actions">
        <span className="api-base-label">{appConfig?.api_base_url || "http://127.0.0.1:8080"}</span>
        <ERPButton variant="ghost" onClick={() => setErpState({ commandOpen: true })}>Search</ERPButton>
        <ERPButton variant="ghost" onClick={() => setErpState({ splitView: !splitView })}>Split</ERPButton>
        <div className="notification-pill">{notifications.length}</div>
        <StatusDot status={status} />
      </div>
    </header>
  );
}
