import React, { useEffect, useState } from "react";
import { Button, Card, DataTable, KPIWidget, WorkflowBadge } from "../components";
import { workforceApi } from "../../services/workforceApi";

export function CognitiveCommandCenter() {
  const [data, setData] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [prompt, setPrompt] = useState("Show workforce health risks and recommended HR actions");
  const [copilot, setCopilot] = useState("");

  async function load() {
    const [summary, profileRows, incidentRows] = await Promise.all([
      workforceApi.cognitiveCommandCenter(),
      workforceApi.cognitiveProfiles(),
      workforceApi.selfHealingIncidents(),
    ]);
    setData(summary);
    setProfiles(profileRows.results || profileRows);
    setIncidents(incidentRows.results || incidentRows);
  }

  useEffect(() => {
    load().catch(() => setData(null));
  }, []);

  async function askCopilot() {
    const session = await workforceApi.askCopilot({ copilot_type: "hr", prompt });
    setCopilot(session.response);
  }

  async function scanGovernance() {
    await workforceApi.scanGovernance();
    await load();
  }

  const snapshot = data?.snapshot || {};

  return (
    <div className="workforce-command-center cognitive-command-center">
      <KPIWidget label="Workforce Health" value={snapshot.workforce_health ?? "-"} />
      <KPIWidget label="Engagement" value={snapshot.engagement_score ?? "-"} tone="green" />
      <KPIWidget label="Open HR Risks" value={data?.open_incidents ?? "-"} tone="red" />
      <KPIWidget label="Org Graph Nodes" value={data?.graph_nodes ?? "-"} tone="violet" />

      <Card title="AI Enterprise Copilot" className="wide-card">
        <div className="portal-actions">
          <input className="command-period-input" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
          <Button onClick={askCopilot}>Ask Copilot</Button>
          <Button variant="secondary" onClick={scanGovernance}>Scan Governance</Button>
        </div>
        {copilot && <div className="enterprise-alert">{copilot}</div>}
      </Card>

      <Card title="Cognitive Profiles" className="wide-card">
        <DataTable
          rows={profiles.slice(0, 8)}
          columns={["employee_display", "trust_score", "leadership_score", "burnout_risk", "promotion_probability"]}
        />
      </Card>

      <Card title="Self-Healing Governance">
        <div className="feed-list">
          {incidents.slice(0, 6).map((incident) => (
            <p key={incident.id}>
              <WorkflowBadge state={incident.status === "open" ? "approval" : "completed"} />
              <strong>{incident.title}</strong>
              <span>{incident.incident_type}</span>
            </p>
          ))}
        </div>
      </Card>

      <Card title="Culture Signals">
        <div className="feed-list">
          {(data?.signals_by_type || []).map((row) => (
            <p key={row.signal_type}>
              <strong>{row.signal_type}</strong>
              <span>{row.total} signals</span>
            </p>
          ))}
        </div>
      </Card>
    </div>
  );
}
