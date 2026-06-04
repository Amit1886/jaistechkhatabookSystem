import React from "react";
import { Button, Input } from "../components";

export function ReportFilterPanel({ filters, value, onChange, onRun, onReset }) {
  const supported = filters?.length ? filters : ["date_from", "date_to", "status", "q"];
  return (
    <div className="report-filter-panel">
      {supported.map((filter) => (
        <Input
          key={filter}
          label={filter.replaceAll("_", " ")}
          type={filter.includes("date") ? "date" : "text"}
          value={value[filter] || ""}
          onChange={(event) => onChange({ ...value, [filter]: event.target.value })}
        />
      ))}
      <div className="report-filter-actions">
        <Button variant="ghost" onClick={onReset}>Reset</Button>
        <Button onClick={onRun}>Run Report</Button>
      </div>
    </div>
  );
}

