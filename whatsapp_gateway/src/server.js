const path = require("path");

require("dotenv").config({ path: path.join(process.cwd(), ".env") });

const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");
const pinoHttp = require("pino-http");

const logger = require("./logger");
const { requireAuth } = require("./middleware/auth");
const { SessionManager } = require("./sessionManager");
const { TemplateStore } = require("./templateStore");
const { digitsOnly, safeJsonParse } = require("./utils/normalize");

const app = express();

app.use(pinoHttp({ logger }));
app.use(helmet());
app.use(cors({ origin: true, credentials: false }));
app.use(express.json({ limit: "1mb" }));

app.use(
  rateLimit({
    windowMs: 60 * 1000,
    max: 240,
    standardHeaders: true,
    legacyHeaders: false
  })
);

const sessionsPath = path.resolve(process.env.SESSIONS_PATH || "./.sessions");
const sessionManager = new SessionManager({ sessionsPath, logger });

const templatesPath = path.resolve(process.env.TEMPLATES_PATH || "./templates.json");
const templateStore = new TemplateStore(templatesPath);
templateStore.load();

// Optional: restore & auto-start persisted sessions (keeps webhooks working after restart)
const _autoStart = String(process.env.AUTO_START_SESSIONS || "").trim().toLowerCase();
if (_autoStart === "1" || _autoStart === "true" || _autoStart === "yes" || _autoStart === "on") {
  sessionManager.autoStartAll().catch((e) => logger.warn({ err: String(e && e.message ? e.message : e) }, "AUTO_START_SESSIONS failed"));
}

app.get("/health", (req, res) => res.json({ ok: true }));

// ---------------- Public QR page (simple) ----------------
app.get("/", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.end(`<!doctype html>
  <html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>WhatsApp Gateway</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  </head>
  <body class="bg-light">
    <div class="container py-4">
      <div class="card shadow-sm border-0">
        <div class="card-body">
          <h4 class="mb-1">WhatsApp Gateway</h4>
          <div class="text-muted">Enter a session id to start and fetch QR.</div>
          <div class="row g-2 mt-3">
            <div class="col-md-6">
              <input id="sid" class="form-control" placeholder="session_id (e.g. user_123)" />
            </div>
            <div class="col-md-6 d-flex gap-2">
              <button class="btn btn-primary" onclick="start()">Start</button>
              <button class="btn btn-outline-secondary" onclick="getQr()">Get QR</button>
              <button class="btn btn-outline-danger" onclick="logout()">Logout</button>
            </div>
          </div>
          <div class="mt-3 small text-muted">This UI is for local testing. Use REST API for production.</div>
          <hr />
          <div id="status" class="small text-muted mb-2"></div>
          <img id="qr" style="max-width:260px; display:none; border:1px solid #e5e7eb; border-radius:8px;" />
          <pre id="out" class="small bg-white p-2 rounded border mt-2" style="max-height:260px; overflow:auto;"></pre>
        </div>
      </div>
    </div>
    <script>
      const API_KEY = prompt("Gateway API Key (Bearer)", "${process.env.GATEWAY_API_KEY || process.env.WA_GATEWAY_API_KEY || ""}") || "";
      function headers(){ return { "Content-Type":"application/json", "Authorization":"Bearer " + API_KEY }; }
      function sid(){ return document.getElementById("sid").value.trim(); }
      function setStatus(t){ document.getElementById("status").textContent = t; }
      function setOut(v){ document.getElementById("out").textContent = typeof v === "string" ? v : JSON.stringify(v,null,2); }
      async function start(){
        const r = await fetch("/session/start", { method:"POST", headers: headers(), body: JSON.stringify({ session_id: sid() }) });
        const d = await r.json(); setOut(d); setStatus("started");
      }
      async function getQr(){
        const r = await fetch("/session/qr?session_id=" + encodeURIComponent(sid()), { headers: headers() });
        const d = await r.json(); setOut(d); setStatus(d.status || "");
        const img = document.getElementById("qr");
        if (d.qr_image){ img.src = d.qr_image; img.style.display = "block"; } else { img.style.display = "none"; }
      }
      async function logout(){
        const r = await fetch("/session/logout", { method:"POST", headers: headers(), body: JSON.stringify({ session_id: sid(), destroy_auth: true }) });
        const d = await r.json(); setOut(d); setStatus("logged out");
      }
    </script>
  </body>
  </html>`);
});

// ---------------- Authenticated API ----------------
app.use(requireAuth);

function requireSessionId(req, res) {
  const sid = String((req.body && req.body.session_id) || req.query.session_id || "").trim();
  if (!sid) {
    res.status(400).json({ ok: false, error: "missing_session_id" });
    return "";
  }
  return sid;
}

function _applyWebhookFromReq(s, req) {
  try {
    const url = String((req.body && req.body.webhook_url) || req.query.webhook_url || "").trim();
    const secret = String((req.body && req.body.webhook_secret) || req.query.webhook_secret || "").trim();
    if (url || secret) s.setWebhook({ url, secret });
  } catch {
    // ignore
  }
}

function _truthy(v) {
  const s = String(v || "").trim().toLowerCase();
  return s === "1" || s === "true" || s === "yes" || s === "on";
}

// ---------------- Backwards-compatible endpoints ----------------
// Django's existing gateway client expects:
// - POST /sessions/qr -> plain text response: "connected" OR "data:image..." OR status text
// - GET  /sessions/status -> JSON including qr_image/status/is_ready
// - POST /messages/text -> JSON ok/error
// - POST /sessions/reconnect (optional)
app.post("/sessions/qr", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).send("invalid_session_id");
  _applyWebhookFromReq(s, req);
  sessionManager.persist(s);
  s.start().catch((e) => logger.warn({ session_id: sid, err: String(e && e.message ? e.message : e) }, "Session start failed"));
  const timeoutMs = Math.max(1000, Number((req.body && req.body.timeout_ms) || req.query.timeout_ms || 5000));
  const out = await s.waitForQr({ timeoutMs });
  if (String(out.status || "").toLowerCase() === "connected") return res.status(200).send("connected");
  if (out.qr_image) return res.status(200).send(out.qr_image);
  if (out.qr) return res.status(200).send(out.qr);
  return res.status(200).send(String(out.status || "qr_not_ready"));
});

app.get("/sessions/status", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  _applyWebhookFromReq(s, req);
  sessionManager.persist(s);
  s.start().catch(() => null);
  const is_ready = await s.isLoggedInSafe({ timeoutMs: 900 });
  if (is_ready) {
    s.status = "ready";
    s.lastQrDataUrl = "";
    s.lastQrText = "";
  }
  return res.json({
    ok: true,
    status: s.status,
    is_ready: Boolean(is_ready || s.isReady()),
    last_error: s.lastError || "",
    qr_image: s.lastQrDataUrl || "",
    qr: s.lastQrText || "",
    last_qr_at: s.lastQrAt ? s.lastQrAt.toISOString() : null
  });
});

app.post("/sessions/reconnect", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  _applyWebhookFromReq(s, req);
  sessionManager.persist(s);

  const destroyAuth = _truthy(req.body && req.body.destroy_auth);
  try {
    await s.logout({ destroyAuth });
  } catch {
    // ignore
  }
  s.start().catch(() => null);

  const waitForQr = _truthy(req.body && req.body.wait_for_qr);
  if (!waitForQr) return res.json({ ok: true, session_id: sid, status: "reconnecting" });
  const timeoutMs = Math.max(1000, Number((req.body && req.body.timeout_ms) || 15000));
  const out = await s.waitForQr({ timeoutMs });
  return res.json({ ok: true, session_id: sid, ...out, last_error: s.lastError || "" });
});

app.post("/messages/text", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const to = digitsOnly(req.body.to);
  const text = String(req.body.text || "");
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.start().catch(() => null);
  try {
    const out = await s.sendText({ phone: to, text });
    return res.json({ ok: true, message_id: out.id });
  } catch (e) {
    return res.status(400).json({ ok: false, error: String(e && e.message ? e.message : e) });
  }
});

// MODULE 1/2: Session management
app.post("/session/start", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.setWebhook({ url: req.body.webhook_url, secret: req.body.webhook_secret });
  sessionManager.persist(s);
  // Don't block HTTP while Puppeteer boots (can hang on some machines).
  s.start().catch((e) => logger.warn({ session_id: sid, err: String(e && e.message ? e.message : e) }, "Session start failed"));
  return res.json({ ok: true, session_id: sid, status: s.status });
});

app.get("/session/qr", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.setWebhook({ url: req.query.webhook_url, secret: req.query.webhook_secret });
  sessionManager.persist(s);
  // Start asynchronously; always respond within waitForQr timeout.
  s.start().catch((e) => logger.warn({ session_id: sid, err: String(e && e.message ? e.message : e) }, "Session start failed"));
  const out = await s.waitForQr({ timeoutMs: Number(req.query.timeout_ms || 25000) });
  return res.json({ ok: true, session_id: sid, ...out, last_error: s.lastError || "" });
});

app.post("/session/logout", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.get(sid);
  if (!s) return res.json({ ok: true, session_id: sid, status: "not_started" });
  await s.logout({ destroyAuth: Boolean(req.body.destroy_auth) });
  return res.json({ ok: true, session_id: sid, status: s.status });
});

// MODULE 3: Messaging APIs
app.post("/send-message", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const phone = digitsOnly(req.body.phone);
  const message = String(req.body.message || "");
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  // Fire-and-forget start; return "not_ready" quickly if not logged in.
  s.start().catch(() => null);
  try {
    const out = await s.sendText({ phone, text: message });
    return res.json({ ok: true, message_id: out.id });
  } catch (e) {
    return res.status(400).json({ ok: false, error: String(e && e.message ? e.message : e) });
  }
});

app.post("/send-template", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const phone = digitsOnly(req.body.phone);
  const name = String(req.body.template || "").trim();
  const data = req.body.data && typeof req.body.data === "object" ? req.body.data : {};
  const rendered = templateStore.render(name, data);
  if (!rendered) return res.status(400).json({ ok: false, error: "template_not_found_or_empty" });
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.start().catch(() => null);
  try {
    const out = await s.sendText({ phone, text: rendered });
    return res.json({ ok: true, message_id: out.id, rendered });
  } catch (e) {
    return res.status(400).json({ ok: false, error: String(e && e.message ? e.message : e) });
  }
});

app.post("/send-bulk", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const numbers = Array.isArray(req.body.numbers) ? req.body.numbers : [];
  const msg = String(req.body.message || "");
  const delayMs = Math.max(0, Number(req.body.delay_ms || 350));
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.start().catch(() => null);
  const results = [];
  for (const n of numbers) {
    const phone = digitsOnly(n);
    if (!phone) continue;
    try {
      const out = await s.sendText({ phone, text: msg });
      results.push({ phone, ok: true, message_id: out.id });
    } catch (e) {
      results.push({ phone, ok: false, error: String(e && e.message ? e.message : e) });
    }
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
  }
  return res.json({ ok: true, sent: results.filter((r) => r.ok).length, results });
});

// Contacts / Groups
app.get("/contacts", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.start().catch(() => null);
  if (!s.client) return res.status(400).json({ ok: false, error: "not_ready" });
  const logged = typeof s.isLoggedInSafe === "function" ? await s.isLoggedInSafe({ timeoutMs: 1800 }) : await s.client.isLoggedIn().catch(() => false);
  if (!logged) return res.status(400).json({ ok: false, error: "not_ready" });
  const contacts = await s.client.getAllContacts();
  return res.json({
    ok: true,
    contacts: contacts.slice(0, 2000).map((c) => ({
      id: c.id || "",
      name: c.name || c.pushname || c.formattedName || "",
      number: digitsOnly(c.id || "")
    }))
  });
});

app.get("/groups", async (req, res) => {
  const sid = requireSessionId(req, res);
  if (!sid) return;
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.start().catch(() => null);
  if (!s.client) return res.status(400).json({ ok: false, error: "not_ready" });
  const logged = typeof s.isLoggedInSafe === "function" ? await s.isLoggedInSafe({ timeoutMs: 1800 }) : await s.client.isLoggedIn().catch(() => false);
  if (!logged) return res.status(400).json({ ok: false, error: "not_ready" });
  const groups = await s.client.getAllGroups();
  return res.json({
    ok: true,
    groups: groups.slice(0, 500).map((g) => ({ id: (g.id && g.id._serialized) || String(g.id || ""), name: g.name || "" }))
  });
});

// Optional template admin endpoints
app.get("/templates", (req, res) => res.json({ ok: true, templates: templateStore.list() }));
app.post("/templates", (req, res) => {
  const name = String(req.body.name || "").trim();
  const text = String(req.body.text || "");
  const ok = templateStore.set(name, text);
  return res.json({ ok, name });
});

// ---------------- Django compatibility routes ----------------
// Used by the existing Django WhatsApp app in this repo (provider client)
app.post("/sessions/qr", async (req, res) => {
  const sid = String((req.body && req.body.session_id) || "").trim();
  if (!sid) return res.status(400).send("missing_session_id");
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).send("invalid_session_id");
  s.setWebhook({ url: req.body.webhook_url, secret: req.body.webhook_secret });
  sessionManager.persist(s);
  s.start().catch((e) => logger.warn({ session_id: sid, err: String(e && e.message ? e.message : e) }, "Session start failed"));
  const out = await s.waitForQr({ timeoutMs: Number(req.body.timeout_ms || 25000) });
  if (out.status === "connected") return res.status(200).send("connected");
  // Plain text response: QR image as data URL
  const payload = (out.qr_image || out.qr || "").trim();
  if (payload) return res.status(200).send(payload);
  // If QR isn't available, return a meaningful error/status for Django UI.
  return res.status(200).send((s.lastError || out.status || "qr_not_ready") + "");
});

app.post("/messages/text", async (req, res) => {
  const sid = String((req.body && req.body.session_id) || "").trim();
  const to = digitsOnly(req.body.to);
  const text = String(req.body.text || "");
  if (!sid) return res.status(400).json({ ok: false, error: "missing_session_id" });
  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });
  s.start().catch(() => null);
  try {
    const out = await s.sendText({ phone: to, text });
    return res.json({ ok: true, message_id: out.id });
  } catch (e) {
    return res.status(400).json({ ok: false, error: String(e && e.message ? e.message : e) });
  }
});

function sessionSummary(s) {
  return {
    session_id: s.sessionId,
    status: s.status,
    // NOTE: is_ready is computed in route handler using isLoggedIn when possible.
    is_ready: Boolean(s.isReady && s.isReady()),
    last_error: s.lastError || "",
    qr: s.lastQrText || "",
    qr_image: s.lastQrDataUrl || "",
    last_qr_at: s.lastQrAt ? s.lastQrAt.toISOString() : null,
    has_webhook: Boolean(s.webhookUrl),
  };
}

async function buildSessionStatus(s) {
  let isLoggedIn = false;
  if (s && typeof s.isLoggedInSafe === "function") {
    isLoggedIn = await s.isLoggedInSafe({ timeoutMs: Number(process.env.IS_LOGGED_IN_TIMEOUT_MS || 1800) });
  } else if (s && s.client && typeof s.client.isLoggedIn === "function") {
    try {
      isLoggedIn = await s.client.isLoggedIn();
    } catch {
      isLoggedIn = false;
    }
  }

  // Keep internal status aligned with actual login status to avoid "connected but not_ready".
  try {
    if (isLoggedIn && s.status !== "ready") {
      s.status = "ready";
      s.lastQrDataUrl = "";
      s.lastQrText = "";
    }
    if (!isLoggedIn && s.status === "ready") {
      // Browser/session exists but WhatsApp isn't logged in anymore.
      s.status = "disconnected";
    }
  } catch {
    // ignore
  }

  const base = sessionSummary(s);
  return { ...base, is_logged_in: isLoggedIn, is_ready: isLoggedIn };
}

// Required API: GET /sessions/status
// - With ?session_id=... -> status for one session
// - Without session_id -> list all known sessions (configured + in-memory)
app.get("/sessions/status", async (req, res) => {
  const sid = String(req.query.session_id || "").trim();

  if (!sid) {
    const configured = sessionManager.listConfigured();
    const inMemory = Array.from(sessionManager.sessions.keys());
    const ids = Array.from(new Set([...(configured || []), ...(inMemory || [])])).sort();
    const sessions = ids.map((id) => sessionSummary(sessionManager.ensure(id)));
    return res.json({ ok: true, count: sessions.length, sessions });
  }

  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });

  // Optional: keep webhook config in sync
  const webhookUrl = String(req.query.webhook_url || "").trim();
  const webhookSecret = String(req.query.webhook_secret || "").trim();
  if (webhookUrl || webhookSecret) {
    s.setWebhook({ url: webhookUrl, secret: webhookSecret });
    sessionManager.persist(s);
  }

  const out = await buildSessionStatus(s);
  return res.json({ ok: true, ...out });
});

// Required API: POST /sessions/reconnect
// Body: { session_id, webhook_url?, webhook_secret?, wait_for_qr?, timeout_ms? }
app.post("/sessions/reconnect", async (req, res) => {
  const sid = String((req.body && req.body.session_id) || "").trim();
  if (!sid) return res.status(400).json({ ok: false, error: "missing_session_id" });

  const s = sessionManager.ensure(sid);
  if (!s) return res.status(400).json({ ok: false, error: "invalid_session_id" });

  s.setWebhook({ url: req.body.webhook_url, secret: req.body.webhook_secret });
  sessionManager.persist(s);

  // Don't block HTTP while Puppeteer boots (can hang on some machines).
  s.start().catch((e) => logger.warn({ session_id: sid, err: String(e && e.message ? e.message : e) }, "Session reconnect start failed"));

  const waitForQr = Boolean(req.body.wait_for_qr);
  if (waitForQr) {
    const out = await s.waitForQr({ timeoutMs: Number(req.body.timeout_ms || 15000) });
    const status = await buildSessionStatus(s);
    return res.json({ ok: true, session_id: sid, wait: out, ...status });
  }

  const status = await buildSessionStatus(s);
  return res.json({ ok: true, ...status });
});

// ---------------- Error handler ----------------
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  logger.error({ err: String(err && err.message ? err.message : err) }, "Unhandled error");
  res.status(500).json({ ok: false, error: "internal_error" });
});

const port = Number(process.env.PORT || 3100);
app.listen(port, () => logger.info({ port }, "WhatsApp Gateway listening"));
