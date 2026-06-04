const fs = require("fs");
const path = require("path");

function renderTemplate(text, data) {
  const src = String(text || "");
  const d = data && typeof data === "object" ? data : {};
  return src.replace(/{{\s*([a-zA-Z0-9_]+)\s*}}/g, (_, key) => {
    const v = d[key];
    return v === undefined || v === null ? "" : String(v);
  });
}

class TemplateStore {
  constructor(filePath) {
    this.filePath = filePath;
    this.templates = {};
  }

  load() {
    const fp = this.filePath;
    if (!fp) return;
    try {
      if (!fs.existsSync(fp)) {
        this.templates = {
          invoice_created: "Hi {{name}}, invoice {{invoice}} created. Amount: {{amount}}",
          payment_received: "Payment received for {{invoice}}. Amount: {{amount}}. Thank you!",
          low_stock: "Low stock alert: {{product}} remaining {{stock}}",
          order_delivered: "Your order {{order}} is delivered. Thanks for shopping!"
        };
        this.save();
        return;
      }
      const raw = fs.readFileSync(fp, "utf-8");
      const parsed = JSON.parse(raw);
      this.templates = parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      this.templates = {};
    }
  }

  save() {
    const fp = this.filePath;
    if (!fp) return;
    try {
      const dir = path.dirname(fp);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(fp, JSON.stringify(this.templates, null, 2), "utf-8");
    } catch {
      // ignore
    }
  }

  list() {
    return Object.keys(this.templates).sort().map((k) => ({ name: k, text: String(this.templates[k] || "") }));
  }

  get(name) {
    return String(this.templates[name] || "");
  }

  set(name, text) {
    const key = String(name || "").trim();
    if (!key) return false;
    this.templates[key] = String(text || "");
    this.save();
    return true;
  }

  render(name, data) {
    const tpl = this.get(name);
    if (!tpl) return "";
    return renderTemplate(tpl, data);
  }
}

module.exports = { TemplateStore, renderTemplate };

