import React from "react";
import { useErpStore } from "../../store/erpUiStore";
import { ERPCard } from "./DesignSystem";
import { normalizeNotification } from "../../shared/notifications/notificationRegistry";

export default function NotificationCenter() {
  const notifications = useErpStore((state) => state.notifications);
  const normalized = (notifications.length ? notifications : [{ title: "Realtime stream ready", message: "No unread notifications" }]).map(normalizeNotification);

  return (
    <ERPCard title="Notification Center">
      <div className="feed-list">
        {normalized.slice(0, 6).map((item, index) => (
          <p key={item.id || index}>
            <strong>{item.title}</strong>
            <span>{item.message}</span>
          </p>
        ))}
      </div>
    </ERPCard>
  );
}
