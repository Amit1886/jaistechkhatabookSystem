import React, { useEffect } from "react";
import CommandPalette from "../components/enterprise/CommandPalette";
import DynamicSidebar from "../components/enterprise/DynamicSidebar";
import EnterpriseTopbar from "../components/enterprise/EnterpriseTopbar";
import NotificationCenter from "../components/enterprise/NotificationCenter";
import TabbedWorkspace from "../components/enterprise/TabbedWorkspace";
import { useEnterpriseMetadata } from "../hooks/useEnterpriseMetadata";
import { createEnterpriseSocket } from "../realtime/enterpriseSocket";
import { setErpState, useErpStore } from "../store/erpUiStore";

export default function EnterpriseUIEngine() {
  const { loading, error } = useEnterpriseMetadata();
  const splitView = useErpStore((state) => state.splitView);

  useEffect(() => {
    const socket = createEnterpriseSocket({
      onStatus: (status) => setErpState({ realtimeStatus: status }),
      onMessage: (message) => {
        if (message?.type === "notification") {
          setErpState((current) => ({ notifications: [message.payload, ...current.notifications] }));
        }
      },
    });
    const keyboard = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setErpState({ commandOpen: true });
      }
    };
    window.addEventListener("keydown", keyboard);
    return () => {
      socket.close();
      window.removeEventListener("keydown", keyboard);
    };
  }, []);

  if (loading) {
    return <div className="enterprise-loading">Loading enterprise workspace...</div>;
  }

  return (
    <div className="enterprise-os-shell">
      <DynamicSidebar />
      <section className="enterprise-main">
        <EnterpriseTopbar />
        {error && <div className="enterprise-alert">{error}</div>}
        <div className={splitView ? "enterprise-content split-enabled" : "enterprise-content"}>
          <TabbedWorkspace />
          {splitView && <NotificationCenter />}
        </div>
      </section>
      <CommandPalette />
    </div>
  );
}

