import React, { useEffect, useState } from "react";
import { Button, Card, DataTable, KPIWidget } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function WorkforceCommandCenter() {
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7));

  useEffect(() => {
    workforceApi.commandCenter().then(setData).catch(() => setData(null));
  }, []);

  async function generatePayroll() {
    await workforceApi.generatePayroll(period);
    const next = await workforceApi.commandCenter();
    setData(next);
  }

  return (
    <div className="workforce-command-center">
      <KPIWidget label="Live Employees" value={data?.dashboard?.active_employees ?? "-"} />
      <KPIWidget label="Fraud Alerts" value={data?.fraud_alerts ?? "-"} tone="amber" />
      <KPIWidget label="Burnout Alerts" value={data?.burnout_alerts ?? "-"} tone="red" />
      <KPIWidget label="Pending Tasks" value={data?.dashboard?.pending_tasks ?? "-"} tone="violet" />
      <Card title="Live Payroll Estimate" className="wide-card">
        <div className="portal-actions">
          <input className="command-period-input" value={period} onChange={(event) => setPeriod(event.target.value)} />
          <Button onClick={generatePayroll}>Generate Payroll</Button>
        </div>
        <DataTable rows={data?.live_payroll_estimates || []} columns={["employee__employee_code", "net_amount"]} />
      </Card>
      <Card title="Productivity Trends">
        <DataTable rows={data?.productivity_trends || []} columns={["period", "performance_score", "productivity_score"]} />
      </Card>
    </div>
  );
}
