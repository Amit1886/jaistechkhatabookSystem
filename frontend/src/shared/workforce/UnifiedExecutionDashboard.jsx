import React, { useEffect, useState } from "react";
import { Button, Card, DataTable, KPIWidget, WorkflowBadge } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function UnifiedExecutionDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [command, setCommand] = useState(null);
  const [status, setStatus] = useState("");

  async function load() {
    const [work, exec] = await Promise.all([
      workforceApi.unifiedWorkDashboard(),
      workforceApi.executionCommandCenter(),
    ]);
    setDashboard(work);
    setCommand(exec);
  }

  useEffect(() => {
    load().catch(() => setStatus("Dashboard data is not available yet."));
  }, []);

  async function seedTools() {
    setStatus("Preparing role tools...");
    await workforceApi.seedWorkTools();
    await load();
    setStatus("Role tools synchronized.");
  }

  const snapshot = command?.snapshot || {};
  const tools = dashboard?.tools || [];
  const workItems = dashboard?.work_items || [];

  return (
    <div className="workforce-command-center unified-execution-dashboard">
      <KPIWidget label="Live Employees" value={snapshot.live_employees ?? "-"} />
      <KPIWidget label="Active Work" value={snapshot.active_work_items ?? "-"} tone="green" />
      <KPIWidget label="AI Alerts" value={snapshot.ai_alerts ?? "-"} tone="red" />
      <KPIWidget label="Payroll Projection" value={snapshot.payroll_projection ?? "-"} tone="violet" />

      <Card title="Role-Based Tools" className="wide-card">
        <div className="portal-actions">
          <Button onClick={seedTools}>Sync Role Tools</Button>
          {status && <span className="hiring-status">{status}</span>}
        </div>
        <DataTable rows={tools.slice(0, 12)} columns={["tool__name", "tool__category", "tool__route"]} />
      </Card>

      <Card title="My Work Hub" className="wide-card">
        <DataTable rows={workItems.slice(0, 12)} columns={["work_type", "title", "status", "priority", "due_at"]} />
      </Card>

      <Card title="Realtime Admin Command">
        <div className="feed-list">
          <p><WorkflowBadge state="review" /> Support tickets <span>{snapshot.support_tickets ?? 0}</span></p>
          <p><WorkflowBadge state="review" /> Sales activities <span>{snapshot.sales_activities ?? 0}</span></p>
          <p><WorkflowBadge state="approval" /> Remote sessions <span>{snapshot.remote_sessions ?? 0}</span></p>
          <p><WorkflowBadge state="completed" /> Workload balance <span>{snapshot.workload_balance_score ?? "-"}</span></p>
        </div>
      </Card>

      <Card title="AI Productivity Signals">
        <div className="feed-list">
          {(command?.recent_activity || []).slice(0, 6).map((row, index) => (
            <p key={`${row.started_at}-${index}`}>
              <strong>{row.employee__employee_code || "System"}</strong>
              <span>{row.activity_type} · P {row.productivity_score} · Risk {row.fraud_risk_score}</span>
            </p>
          ))}
        </div>
      </Card>
    </div>
  );
}
