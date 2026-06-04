export const NOTIFICATION_TYPES = {
  toast: { label: "Toast", tone: "info" },
  approval: { label: "Approval", tone: "amber" },
  stock: { label: "Stock Alert", tone: "red" },
  gst: { label: "GST Alert", tone: "violet" },
  payment: { label: "Payment Alert", tone: "green" },
  workflow: { label: "Workflow Alert", tone: "blue" },
};

export function normalizeNotification(item) {
  const type = item.type || item.category || "toast";
  const meta = NOTIFICATION_TYPES[type] || NOTIFICATION_TYPES.toast;
  return {
    id: item.id || `${type}-${Date.now()}`,
    type,
    title: item.title || meta.label,
    message: item.message || "",
    tone: item.severity || meta.tone,
    createdAt: item.created_at || item.createdAt || new Date().toISOString(),
    actionUrl: item.action_url || item.actionUrl || "",
  };
}

