import React from "react";
import { Button, Card, KPIWidget as SharedKPIWidget } from "../../shared/components";

export function ERPCard(props) {
  return <Card {...props} />;
}

export function KPIWidget(props) {
  return <SharedKPIWidget {...props} />;
}

export function StatusDot({ status = "offline" }) {
  return <span className={`status-dot status-dot--${status}`} aria-label={status} />;
}

export function ERPButton({ children, variant = "primary", ...props }) {
  return <Button variant={variant} {...props}>{children}</Button>;
}
