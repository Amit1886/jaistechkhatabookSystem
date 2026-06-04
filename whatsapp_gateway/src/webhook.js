const axios = require("axios");

async function postWebhook({ url, secret, payload, timeoutMs, retryCount, retryDelayMs, logger }) {
  const target = String(url || "").trim();
  if (!target) return { ok: false, status: 0, error: "no_webhook_url" };

  const headers = { "Content-Type": "application/json" };
  if (secret) headers["X-WA-Secret"] = String(secret);

  const tries = Math.max(1, Number(retryCount || 0) + 1);
  for (let i = 0; i < tries; i++) {
    try {
      const resp = await axios.post(target, payload, { headers, timeout: Number(timeoutMs || 8000) });
      return { ok: resp.status >= 200 && resp.status < 300, status: resp.status, error: "" };
    } catch (e) {
      const msg = e && e.message ? String(e.message) : "webhook_error";
      if (logger) logger.warn({ err: msg, attempt: i + 1, tries, target }, "Webhook POST failed");
      if (i < tries - 1) {
        await new Promise((r) => setTimeout(r, Number(retryDelayMs || 1000)));
        continue;
      }
      return { ok: false, status: 0, error: msg };
    }
  }
  return { ok: false, status: 0, error: "unknown" };
}

module.exports = { postWebhook };

