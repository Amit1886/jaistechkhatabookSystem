import React, { useEffect, useState } from "react";
import { Card, WorkflowBadge } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function OrgTree() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    workforceApi.orgTree().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <Card title="Organization Hierarchy">
      <div className="org-tree">
        {rows.map((row) => (
          <div key={row.id}>
            <strong>{row.name}</strong>
            <span>{row.department} · {row.designation}</span>
            <WorkflowBadge state={row.status === "active" ? "completed" : "review"} />
          </div>
        ))}
        {!rows.length && <div className="empty-report-state">No organization data yet</div>}
      </div>
    </Card>
  );
}

