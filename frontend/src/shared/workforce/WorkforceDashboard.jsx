import React, { useEffect, useState } from "react";
import { Card, KPIWidget, WorkflowBadge } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function WorkforceDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    workforceApi.dashboard().then(setData).catch((err) => setError(err.message));
  }, []);

  return (
    <div className="workforce-dashboard">
      {error && <div className="enterprise-alert">{error}</div>}
      <KPIWidget label="Active Employees" value={data?.active_employees ?? "-"} />
      <KPIWidget label="Present Today" value={data?.present_today ?? "-"} tone="green" />
      <KPIWidget label="Pending Leave" value={data?.pending_leave ?? "-"} tone="amber" />
      <KPIWidget label="Pending Tasks" value={data?.pending_tasks ?? "-"} tone="violet" />
      <Card title="Department KPIs" className="wide-card">
        <div className="feed-list">
          {(data?.by_department || []).map((row) => (
            <p key={row.department__name || "unassigned"}>
              <strong>{row.department__name || "Unassigned"}</strong>
              <span>{row.total} workers</span>
            </p>
          ))}
        </div>
      </Card>
      <Card title="Approval Center">
        <div className="feed-list">
          <p><WorkflowBadge state="approval" /> Leave approvals</p>
          <p><WorkflowBadge state="review" /> Task reviews</p>
          <p><WorkflowBadge state="draft" /> Onboarding drafts</p>
        </div>
      </Card>
    </div>
  );
}

