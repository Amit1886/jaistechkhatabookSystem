function digitsOnly(value) {
  return String(value || "")
    .replace(/[^\d]/g, "")
    .trim();
}

function toWaId(phone) {
  const d = digitsOnly(phone);
  if (!d) return "";
  // WPPConnect expects "<digits>@c.us"
  return `${d}@c.us`;
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

module.exports = { digitsOnly, toWaId, safeJsonParse };
