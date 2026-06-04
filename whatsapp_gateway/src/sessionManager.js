const fs = require("fs");
const path = require("path");
const wppconnect = require("@wppconnect-team/wppconnect");
const { digitsOnly, toWaId } = require("./utils/normalize");
const { postWebhook } = require("./webhook");

function parsePuppeteerArgs() {
  const raw = String(process.env.PUPPETEER_ARGS || "").trim();
  if (!raw) return [];
  return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

function parseHeadless() {
  return String(process.env.PUPPETEER_HEADLESS || "true").toLowerCase() !== "false";
}

function parseExecutablePath() {
  const raw = String(process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROME_PATH || "").trim();
  if (raw) return raw;

  // Windows-friendly: auto-detect system Chrome if available (avoids bundled Chromium issues on some machines).
  try {
    if (process.platform === "win32") {
      const fs = require("fs");
      const candidates = [
        "C:\\\\Program Files\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe",
        "C:\\\\Program Files (x86)\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe"
      ];
      const local = process.env.LOCALAPPDATA ? String(process.env.LOCALAPPDATA) : "";
      if (local) candidates.push(`${local}\\\\Google\\\\Chrome\\\\Application\\\\chrome.exe`);
      for (const p of candidates) {
        try {
          if (p && fs.existsSync(p)) return p;
        } catch {
          // ignore
        }
      }
    }
  } catch {
    // ignore
  }

  return "";
}

function mediaMaxBytes() {
  try {
    const v = Number(process.env.MEDIA_MAX_BYTES || process.env.WA_MEDIA_MAX_BYTES || 3145728);
    if (!Number.isFinite(v) || v <= 0) return 3145728;
    return Math.min(Math.max(1024 * 64, v), 1024 * 1024 * 25);
  } catch {
    return 3145728;
  }
}

function _extFromMime(mime) {
  const m = String(mime || "").toLowerCase();
  if (m.includes("image/jpeg") || m.includes("image/jpg")) return "jpg";
  if (m.includes("image/png")) return "png";
  if (m.includes("image/webp")) return "webp";
  if (m.includes("audio/ogg") || m.includes("audio/opus")) return "ogg";
  if (m.includes("audio/mpeg")) return "mp3";
  if (m.includes("audio/wav")) return "wav";
  if (m.includes("application/pdf")) return "pdf";
  return "bin";
}

function _readJson(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function _atomicWriteJson(filePath, obj) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  const tmp = `${filePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2), "utf-8");
  fs.renameSync(tmp, filePath);
}

class GatewaySession {
  constructor({ sessionId, sessionsPath, tokensPath, logger }) {
    this.sessionId = sessionId;
    this.sessionsPath = sessionsPath;
    this.tokensPath = tokensPath;
    this.logger = logger;
    this.status = "new";
    this.lastError = "";
    this.lastQrText = "";
    this.lastQrDataUrl = "";
    this.lastQrAt = null;
    this.webhookUrl = "";
    this.webhookSecret = "";
    this.client = null;
    this._qrWaiters = [];
    this._starting = false;
    this._startPromise = null;
  }

  _profileDir() {
    return path.join(this.sessionsPath, "wppconnect_profiles", this.sessionId);
  }

  _tokenFilesToDelete() {
    // WPPConnect default file token store uses "<session>.data.json"
    return [
      path.join(this.tokensPath || "", `${this.sessionId}.data.json`),
      path.join(this.tokensPath || "", `${this.sessionId}.json`)
    ].filter((p) => p && p !== this.tokensPath);
  }

  setWebhook({ url, secret }) {
    this.webhookUrl = String(url || "").trim();
    this.webhookSecret = String(secret || "").trim();
  }

  isReady() {
    return this.status === "ready";
  }

  async isLoggedInSafe({ timeoutMs = 1800 } = {}) {
    if (!this.client || typeof this.client.isLoggedIn !== "function") return false;
    const ms = Math.max(250, Number(timeoutMs || 1800));
    try {
      const p = Promise.resolve(this.client.isLoggedIn())
        .then((v) => Boolean(v))
        .catch(() => false);
      const t = new Promise((resolve) => setTimeout(() => resolve(false), ms));
      return await Promise.race([p, t]);
    } catch {
      return false;
    }
  }

  async start() {
    if (this._starting) return this._startPromise || undefined;
    if (this.client && this.status !== "disconnected" && this.status !== "auth_failure" && this.status !== "logged_out") return;
    this._starting = true;
    this._startPromise = (async () => {

      try {
        this.lastError = "";
        if (this.client) {
          try {
            await this.client.close();
          } catch {
            // ignore
          }
          this.client = null;
        }

        const headless = parseHeadless();
        const args = parsePuppeteerArgs();
        const executablePath = parseExecutablePath();

        const profileDir = this._profileDir();
        fs.mkdirSync(profileDir, { recursive: true });

        const tokensDir = this.tokensPath ? path.resolve(this.tokensPath) : "";
        if (tokensDir) fs.mkdirSync(tokensDir, { recursive: true });

        this.status = "initializing";

        // Guard: on some machines, create() can hang if Chromium can't launch. Don't block forever.
        const createPromise = wppconnect.create({
          session: this.sessionId,
          waitForLogin: false,
          autoClose: 0,
          logQR: false,
          disableWelcome: true,
          folderNameToken: tokensDir || undefined,
          puppeteerOptions: {
            headless,
            args,
            userDataDir: profileDir,
            ...(executablePath ? { executablePath } : {})
          },
          catchQR: (base64Qr, asciiQR, attempt, urlCode) => {
            this.status = "qr";
            this.lastQrAt = new Date();
            this.lastQrText = String(urlCode || asciiQR || "");
            const raw = String(base64Qr || "");
            this.lastQrDataUrl = raw && raw.startsWith("data:image") ? raw : raw ? `data:image/png;base64,${raw}` : "";
            this.logger.info({ session_id: this.sessionId, attempt }, "WPPConnect QR updated");
            this._notifyQrWaiters();
          },
          statusFind: (statusSession) => {
            const st = String(statusSession || "");

            if (st === "inChat" || st === "isLogged") {
              this.status = "ready";
              this.lastQrDataUrl = "";
              this.lastQrText = "";
              this.lastError = "";
              this.logger.info({ session_id: this.sessionId, status: st }, "WPPConnect ready");
              this._notifyQrWaiters();
              return;
            }

            if (st === "qrReadSuccess") {
              this.status = "authenticated";
              this.logger.info({ session_id: this.sessionId, status: st }, "WPPConnect authenticated");
              this._notifyQrWaiters();
              return;
            }

            if (st === "notLogged") {
              this.status = "qr";
              this._notifyQrWaiters();
              return;
            }

            if (st === "qrReadFail" || st === "qrReadError") {
              this.status = "auth_failure";
              this.lastError = st;
              this.logger.warn({ session_id: this.sessionId, status: st }, "WPPConnect QR read failed");
              this._notifyQrWaiters();
              return;
            }

            if (st === "disconnectedMobile" || st === "browserClose" || st === "serverClose") {
              this.status = "disconnected";
              this.lastError = st;
              this.logger.warn({ session_id: this.sessionId, status: st }, "WPPConnect disconnected");
              this._notifyQrWaiters();
              return;
            }

            this.logger.info({ session_id: this.sessionId, status: st }, "WPPConnect status");
          }
        });

        const createTimeoutMs = Math.max(5000, Number(process.env.CREATE_SESSION_TIMEOUT_MS || 30000));
        const timeout = new Promise((_, reject) =>
          setTimeout(() => reject(new Error(`create_timeout_${createTimeoutMs}ms`)), createTimeoutMs)
        );

        this.client = await Promise.race([createPromise, timeout]);

        this.client.onMessage(async (message) => {
          try {
            if (!message || message.fromMe) return;
            const from = digitsOnly(message.from || "").replace(/@c\.us$/i, "");
            const to = digitsOnly(message.to || "").replace(/@c\.us$/i, "");
            const sender = message.sender || {};

            // Optional: include small media payloads (base64) for Django OCR/voice automation.
            let media = undefined;
            try {
              const isMedia = Boolean(message.isMedia);
              const size = Number(message.size || 0) || 0;
              if (isMedia) {
                if (size > 0 && size <= mediaMaxBytes()) {
                  const b64 = await this.client.downloadMedia(message);
                  media = {
                    mimetype: String(message.mimetype || ""),
                    size,
                    ext: _extFromMime(message.mimetype || ""),
                    base64: String(b64 || "")
                  };
                } else {
                  media = {
                    mimetype: String(message.mimetype || ""),
                    size,
                    ext: _extFromMime(message.mimetype || ""),
                    too_large: Boolean(size > mediaMaxBytes())
                  };
                }
              }
            } catch (e) {
              media = { error: String(e && e.message ? e.message : e) };
            }

            const payload = {
              from,
              to,
              body: String(message.body || ""),
              type: String(message.type || "chat"),
              message_id: String(message.id || ""),
              timestamp: Number(message.timestamp || message.t || 0),
              name: String(sender.pushname || sender.verifiedName || sender.name || sender.shortName || ""),
              session_id: this.sessionId,
              caption: String(message.caption || ""),
              mimetype: String(message.mimetype || ""),
              size: Number(message.size || 0) || 0,
              media
            };
            await postWebhook({
              url: this.webhookUrl,
              secret: this.webhookSecret,
              payload,
              timeoutMs: Number(process.env.WEBHOOK_TIMEOUT_MS || 8000),
              retryCount: Number(process.env.WEBHOOK_RETRY_COUNT || 0),
              retryDelayMs: Number(process.env.WEBHOOK_RETRY_DELAY_MS || 1000),
              logger: this.logger
            });
          } catch (e) {
            this.logger.warn({ session_id: this.sessionId, err: String(e && e.message ? e.message : e) }, "Inbound webhook push failed");
          }
        });

        // If the session was already authenticated, statusFind may not emit in time.
        try {
          const logged = await this.isLoggedInSafe({ timeoutMs: 1800 });
          if (logged) {
            this.status = "ready";
            this._notifyQrWaiters();
          }
        } catch {
          // ignore
        }
      } catch (e) {
        this.status = "error";
        this.lastError = String(e && e.message ? e.message : e);
        this.logger.error({ session_id: this.sessionId, err: String(e && e.message ? e.message : e) }, "WPPConnect start failed");
        throw e;
      } finally {
        this._starting = false;
      }
    })();

    try {
      return await this._startPromise;
    } finally {
      // keep promise for debugging; clear on success to allow future restarts after logout/disconnect
      this._startPromise = null;
    }
  }

  _notifyQrWaiters() {
    const waiters = this._qrWaiters.splice(0);
    waiters.forEach((w) => {
      try {
        w();
      } catch {
        // ignore
      }
    });
  }

  async waitForQr({ timeoutMs }) {
    const ms = Math.max(1000, Number(timeoutMs || 25000));
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      // Do not trust only internal status: verify with isLoggedIn to avoid false "connected"
      const logged = await this.isLoggedInSafe({ timeoutMs: 1500 });
      if (logged) {
        this.status = "ready";
        this.lastQrDataUrl = "";
        this.lastQrText = "";
        return { status: "connected", qr: "", qr_image: "" };
      }
      if (this.lastQrDataUrl) return { status: "qr", qr: this.lastQrText, qr_image: this.lastQrDataUrl };
      const remaining = Math.max(0, deadline - Date.now());
      await new Promise((resolve) => {
        const timer = setTimeout(resolve, Math.min(1000, remaining || 1000));
        this._qrWaiters.push(() => {
          clearTimeout(timer);
          resolve();
        });
      });
    }
    return { status: this.status, qr: this.lastQrText || "", qr_image: this.lastQrDataUrl || "" };
  }

  async sendText({ phone, text }) {
    if (!this.client) throw new Error("session_not_started");
    const ok = await this.isLoggedInSafe({ timeoutMs: 1800 });
    if (!ok) throw new Error("not_ready");
    const id = toWaId(phone);
    if (!id) throw new Error("invalid_phone");
    const body = String(text || "").trim();
    if (!body) throw new Error("empty_message");
    const res = await this.client.sendText(id, body);
    return { id: res && res.id ? String(res.id) : "" };
  }

  async logout({ destroyAuth = false }) {
    if (!this.client) return;
    try {
      await this.client.logout();
    } catch {
      // ignore
    }
    try {
      await this.client.close();
    } catch {
      // ignore
    }
    this.client = null;
    this.status = "logged_out";
    this.lastQrDataUrl = "";
    this.lastQrText = "";

    if (destroyAuth) {
      for (const filePath of this._tokenFilesToDelete()) {
        try {
          if (fs.existsSync(filePath)) fs.rmSync(filePath, { force: true });
        } catch {
          // ignore
        }
      }
      try {
        const profileDir = this._profileDir();
        if (fs.existsSync(profileDir)) fs.rmSync(profileDir, { recursive: true, force: true });
      } catch {
        // ignore
      }
    }
  }
}

class SessionManager {
  constructor({ sessionsPath, logger }) {
    this.sessionsPath = sessionsPath;
    this.logger = logger;
    this.tokensPath = path.join(this.sessionsPath, "tokens");
    this.sessions = new Map();
    this.stateFile = path.join(this.sessionsPath, "gateway_sessions.json");
    this.state = this._loadState();
  }

  _loadState() {
    const data = _readJson(this.stateFile);
    if (!data || typeof data !== "object") return {};
    return data;
  }

  _saveState() {
    try {
      _atomicWriteJson(this.stateFile, this.state || {});
    } catch (e) {
      this.logger.warn({ err: String(e && e.message ? e.message : e) }, "Failed to persist session state");
    }
  }

  get(sessionId) {
    return this.sessions.get(sessionId) || null;
  }

  ensure(sessionId) {
    const sid = String(sessionId || "").trim();
    if (!sid) return null;
    let s = this.sessions.get(sid);
    if (!s) {
      s = new GatewaySession({ sessionId: sid, sessionsPath: this.sessionsPath, tokensPath: this.tokensPath, logger: this.logger });
      const cfg = this.state && this.state[sid] ? this.state[sid] : null;
      if (cfg && typeof cfg === "object") {
        s.setWebhook({ url: cfg.webhook_url, secret: cfg.webhook_secret });
      }
      this.sessions.set(sid, s);
    }
    return s;
  }

  persist(session) {
    if (!session || !session.sessionId) return;
    const sid = session.sessionId;
    this.state = this.state || {};
    this.state[sid] = {
      webhook_url: session.webhookUrl || "",
      webhook_secret: session.webhookSecret || ""
    };
    this._saveState();
  }

  listConfigured() {
    const st = this.state || {};
    return Object.keys(st).sort();
  }

  async autoStartAll() {
    const ids = this.listConfigured();
    for (const sid of ids) {
      try {
        const s = this.ensure(sid);
        if (!s) continue;
        await s.start();
      } catch (e) {
        this.logger.warn({ session_id: sid, err: String(e && e.message ? e.message : e) }, "Auto-start session failed");
      }
    }
  }
}

module.exports = { SessionManager };
