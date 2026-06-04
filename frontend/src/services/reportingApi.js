async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export const reportingApi = {
  templates: () => request("/api/v1/platform/reports/templates/"),
  dashboard: () => request("/api/v1/platform/reports/dashboard/"),
  run: (key, payload = {}) =>
    request(`/api/v1/platform/reports/run/${key}/`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  exportUrl: (key) => `/api/v1/platform/reports/export/${key}/`,
  export: async (key, payload = {}) => {
    const response = await fetch(`/api/v1/platform/reports/export/${key}/`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.blob();
  },
};

