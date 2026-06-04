const pino = require("pino");

const level = (process.env.LOG_LEVEL || "info").toLowerCase();

module.exports = pino({
  level,
  redact: {
    paths: ["req.headers.authorization", "*.apiKey", "*.accessToken", "*.webhook_secret"],
    remove: true
  }
});

