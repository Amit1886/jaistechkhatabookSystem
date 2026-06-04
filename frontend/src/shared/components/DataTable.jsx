import React from "react";
import { Card } from "./Card";
import { WorkflowBadge } from "./WorkflowBadge";

function renderCell(value) {
  if (value && typeof value === "object" && value.workflowState) {
    return <WorkflowBadge state={value.workflowState} />;
  }
  return String(value ?? "");
}

export function DataTable({ title = "Records", rows = [], columns, filters }) {
  const data = rows.length ? rows : [];
  const resolvedColumns = columns || Object.keys(data[0] || {});

  return (
    <Card title={title} action={filters}>
      <div className="erp-table-wrap">
        <table className="erp-table">
          <thead>
            <tr>{resolvedColumns.map((column) => <th key={column}>{column}</th>)}</tr>
          </thead>
          <tbody>
            {data.map((row, index) => (
              <tr key={row.id || index}>
                {resolvedColumns.map((column) => <td key={column}>{renderCell(row[column])}</td>)}
              </tr>
            ))}
            {!data.length && (
              <tr>
                <td colSpan={resolvedColumns.length || 1}>No records found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

