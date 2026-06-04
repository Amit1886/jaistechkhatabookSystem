# WhatsApp Web Gateway Setup (QR Login) — This Repo

This guide wires the included Node.js gateway (`whatsapp_gateway/`) with the Django WhatsApp Control Center (`/ai-tools/whatsapp/`).

> Note: WhatsApp Web automation may violate WhatsApp terms and can risk number bans. For production, prefer the Official Cloud API.

## 1) Start Django

From repo root:

```bash
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py runserver
```

Ensure your `.env` has:

- `BASE_URL=http://127.0.0.1:8000`
- `WA_GATEWAY_BASE_URL=http://127.0.0.1:3100`
- `WA_GATEWAY_API_KEY=...` (must match the gateway API key)
- `WA_GATEWAY_AUTOSTART=true` (recommended: starts the gateway automatically when you run `manage.py runserver`)

## 2) Start Node Gateway

The included gateway uses **WPPConnect** (WhatsApp Web automation via Puppeteer).

```bash
cd whatsapp_gateway
cp .env.example .env
npm install
npm run start
```

> If `WA_GATEWAY_AUTOSTART=true`, you usually **do not need** to run the gateway manually.  
> Django will start it automatically on `manage.py runserver` (local/dev only).

Set `GATEWAY_API_KEY` inside `whatsapp_gateway/.env` to the same value you set in Django `WA_GATEWAY_API_KEY`.

If the gateway fails with `spawn EPERM` / `no open browser`, set system Chrome path in `whatsapp_gateway/.env`:

```bash
PUPPETEER_EXECUTABLE_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
```

## 3) Connect WhatsApp via QR

Open Setup Wizard:

- `http://127.0.0.1:8000/ai-tools/whatsapp/setup/`

Steps:

1. Choose **QR Login (Web Gateway)**
2. Add your WhatsApp number (label optional)
3. Click **Request QR**
4. WhatsApp Business App → Linked devices → Link a device → Scan QR

## 4) Test

- Send `hi` or `menu` from a customer number
- Check logs in WhatsApp Control Center:
  - `http://127.0.0.1:8000/ai-tools/whatsapp/`
