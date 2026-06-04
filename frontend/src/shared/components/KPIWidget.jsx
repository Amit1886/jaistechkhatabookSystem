import React from "react";
import { Card } from "./Card";

export function KPIWidget({ label, value, tone = "blue", detail }) {
  return (
    <Card className={`kpi-widget kpi-widget--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </Card>
  );
}

