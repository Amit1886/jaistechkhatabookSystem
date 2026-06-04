function parseBearer(headerValue) {
  const h = (headerValue || "").trim();
  if (!h) return "";
  const parts = h.split(" ");
  if (parts.length !== 2) return "";
  if (parts[0].toLowerCase() !== "bearer") return "";
  return (parts[1] || "").trim();
}

function isTruthy(value) {
  return ["1", "true", "yes", "on"].includes(String(value || "").trim().toLowerCase());
}

function isLoopbackIp(ip) {
  const v = String(ip || "").trim();
  if (!v) return false;
  if (v === "::1") return true;
  if (v === "127.0.0.1") return true;
  if (v.startsWith("::ffff:127.")) return true;
  return false;
}

function buildKeySet() {
  const raw = (process.env.GATEWAY_API_KEY || process.env.WA_GATEWAY_API_KEY || "").trim();
  if (!raw) return new Set();
  // allow comma-separated keys for rotation
  return new Set(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

const KEY_SET = buildKeySet();

function requireAuth(req, res, next) {
  if (!KEY_SET.size) {
    // Dev-friendly: allow localhost calls without an API key when explicitly enabled or not in production.
    // This keeps the demo/simple setup working for non-technical users.
    const env = String(process.env.NODE_ENV || "").trim().toLowerCase();
    const allowNoAuth = isTruthy(process.env.ALLOW_NO_AUTH || process.env.GATEWAY_ALLOW_NO_AUTH) || (env && env !== "production");
    if (allowNoAuth && isLoopbackIp(req.ip)) return next();
    return res.status(500).json({ ok: false, error: "gateway_api_key_not_configured" });
  }
  const token = parseBearer(req.headers.authorization);
  if (!token || !KEY_SET.has(token)) return res.status(401).json({ ok: false, error: "unauthorized" });
  return next();
}

module.exports = { requireAuth };
