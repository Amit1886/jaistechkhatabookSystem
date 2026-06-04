import React from "react";
import { DataTable } from "../../shared/components";

export default function DynamicTable({ title = "Dynamic Table", rows = [] }) {
  const data = rows.length ? rows : [];
  const columns = Object.keys(data[0] || {});

  if (!data.length) {
    return <div className="erp-card empty-report-state">{title}: no live records returned by the API.</div>;
  }
  return <DataTable title={title} rows={data} columns={columns} />;
}
