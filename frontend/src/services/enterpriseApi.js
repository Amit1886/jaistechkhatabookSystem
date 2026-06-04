const API_BASE = (import.meta.env.VITE_FASTAPI_URL || "http://127.0.0.1:8081").replace(/\/$/, "");
const TOKEN_KEY = "erp:fastapi:access";
const REFRESH_KEY = "erp:fastapi:refresh";

const JSON_HEADERS = { "Content-Type": "application/json", Accept: "application/json" };

function token() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

async function request(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = {
    ...JSON_HEADERS,
    ...(token() ? { Authorization: `Bearer ${token()}` } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(url, {
    credentials: "omit",
    headers,
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function login(identifier = "Demotest3", password = "Demo@123") {
  const data = await request("/auth/login", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ identifier, password }),
  });
  localStorage.setItem(TOKEN_KEY, data.access_token || data.access || "");
  localStorage.setItem(REFRESH_KEY, data.refresh_token || data.refresh || "");
  return data;
}

async function ensureDemoSession() {
  if (token()) return { reused: true };
  return login();
}

export const enterpriseApi = {
  apiBase: API_BASE,
  login,
  ensureDemoSession,
  appConfig: () => request("/api/system/app-config/?platform=app"),
  liveData: () => request("/api/system/live-data/"),
  apiStatus: () => request("/api/system/api-status/"),
  sidebar: () => request("/menu/sidebar?platform=app"),
  engineDashboard: () => request("/dashboard/"),
  reports: () => request("/reports/catalog"),
  offlinePull: () => request("/offline/pull?models=commerce.product,commerce.invoice,khataapp.party"),
  formSchema: (key) => request(`/mobile/screen-metadata/${key}/`),
  command: (commandType, payload = {}, idempotencyKey = "") =>
    request("/api/gateway/commands/", {
      method: "POST",
      body: JSON.stringify({ command_type: commandType, payload, idempotency_key: idempotencyKey }),
    }),
  query: (queryKey, filters = {}) =>
    request("/api/gateway/queries/", {
      method: "POST",
      body: JSON.stringify({ query_key: queryKey, filters }),
    }),
  notifications: () => request("/api/system/live-data/").then((data) => ({ results: data.notifications || [] })),
  activityDashboard: () => request("/api/system/live-data/").then((data) => ({
    users_online: data.sales?.live_users || 0,
    active_devices: data.sales?.active_devices || 0,
  })),
  evaluatePolicy: (policyType, context = {}) =>
    request("/api/gateway/policies/evaluate/", {
      method: "POST",
      body: JSON.stringify({ policy_type: policyType, context }),
    }),
};
