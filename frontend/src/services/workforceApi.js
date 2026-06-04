async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export const workforceApi = {
  dashboard: () => request("/api/v1/platform/workforce/dashboard/"),
  commandCenter: () => request("/api/v1/platform/workforce/command-center/"),
  ecosystemCommandCenter: () => request("/api/v1/platform/workforce/ecosystem-command-center/"),
  cognitiveCommandCenter: () => request("/api/v1/platform/workforce/cognitive-command-center/"),
  unifiedWorkDashboard: () => request("/api/v1/platform/workforce/unified-work-dashboard/"),
  executionCommandCenter: () => request("/api/v1/platform/workforce/execution-command-center/"),
  orgTree: () => request("/api/v1/platform/workforce/org-tree/"),
  markAttendance: (payload) =>
    request("/api/v1/platform/workforce/self/attendance/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  tasks: () => request("/api/v1/platform/workforce/tasks/"),
  leaves: () => request("/api/v1/platform/workforce/leave-requests/"),
  announcements: () => request("/api/v1/platform/workforce/announcements/"),
  gigTasks: () => request("/api/v1/platform/workforce/gig-tasks/"),
  partners: () => request("/api/v1/platform/workforce/partners/"),
  marketplaceListings: () => request("/api/v1/platform/workforce/marketplace-listings/"),
  remoteSessions: () => request("/api/v1/platform/workforce/remote-sessions/"),
  cognitiveProfiles: () => request("/api/v1/platform/workforce/cognitive-profiles/"),
  selfHealingIncidents: () => request("/api/v1/platform/workforce/self-healing-incidents/"),
  recognitions: () => request("/api/v1/platform/workforce/recognitions/"),
  workItems: () => request("/api/v1/platform/workforce/work-items/"),
  workTools: () => request("/api/v1/platform/workforce/work-tools/"),
  seedWorkTools: () =>
    request("/api/v1/platform/workforce/work-tools/seed_defaults/", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  recordWorkActivity: (payload) =>
    request("/api/v1/platform/workforce/work-activity-records/record/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  askCopilot: (payload) =>
    request("/api/v1/platform/workforce/enterprise-copilot/ask/", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  scanGovernance: () =>
    request("/api/v1/platform/workforce/self-healing-incidents/scan/", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  aiAssignGig: (id) =>
    request(`/api/v1/platform/workforce/gig-tasks/${id}/ai_assign/`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  generatePayroll: (period) =>
    request("/api/v1/platform/workforce/payroll-runs/generate/", {
      method: "POST",
      body: JSON.stringify({ period }),
    }),
};
