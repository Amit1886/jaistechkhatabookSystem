import React from "react";
import { Card } from "../components";

export function ReportChart({ title = "Chart", chart }) {
  const labels = chart?.labels || [];
  const values = chart?.datasets?.[0]?.data || [];
  const max = Math.max(...values, 1);

  return (
    <Card title={title}>
      {labels.length ? (
        <div className="report-chart">
          {labels.map((label, index) => (
            <div key={`${label}-${index}`}>
              <span style={{ height: `${Math.max((Number(values[index] || 0) / max) * 100, 4)}%` }} />
              <small>{label}</small>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-report-state">No chart data for selected filters</div>
      )}
    </Card>
  );
}

