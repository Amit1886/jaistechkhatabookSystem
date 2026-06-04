import React from "react";
import { Card } from "../components/Card";
import { DataTable } from "../components/DataTable";
import { FilterBar } from "../components/FilterBar";
import { WorkflowBadge } from "../components/WorkflowBadge";

export function UnifiedModuleShell({ title, state = "draft", actions, filters, rows, children }) {
  return (
    <div className="unified-module-shell">
      <div className="module-page-head">
        <div>
          <WorkflowBadge state={state} />
          <h1>{title}</h1>
        </div>
        {actions}
      </div>
      {filters && <FilterBar>{filters}</FilterBar>}
      {children || (
        <Card>
          <DataTable title={`${title} Records`} rows={rows || []} />
        </Card>
      )}
    </div>
  );
}

