# WhatsApp Gateway (Self‑Hosted)

This is a self-hosted WhatsApp Web automation gateway built on:

- Node.js + Express
- WPPConnect (Puppeteer under the hood)

Features:

- QR Login + session persistence (WPPConnect token store)
- Session management (multi-session via `session_id`)
- REST API for sending messages and templates
- Bulk messaging (basic throttling)
- Webhook push for incoming messages
- Auto reconnect (best effort)

> Important: Automating WhatsApp Web can violate WhatsApp terms and may result in number bans. For production, prefer the Official WhatsApp Cloud API.

## Quick Start

1. Install dependencies:
   - `cd whatsapp_gateway`
   - `npm install`

2. Configure:
   - Copy `.env.example` to `.env`
   - Set `GATEWAY_API_KEY`
   - Optional: keep sessions connected on restart: `AUTO_START_SESSIONS=true`

3. Run:
   - `npm run start`

Server starts on `PORT` (default: `3100`).

## REST API (Primary)

All API requests require:

- `Authorization: Bearer <GATEWAY_API_KEY>`

### Sessions

- `POST /session/start`
  - Body: `{ "session_id": "your-session", "webhook_url": "...", "webhook_secret": "..." }`
- `GET /session/qr?session_id=your-session`
- `POST /session/logout`
  - Body: `{ "session_id": "your-session" }`

### Messaging

- `POST /send-message`
  - Body: `{ "session_id":"your-session", "phone":"9199...", "message":"Hello" }`
- `POST /send-template`
  - Body: `{ "session_id":"your-session", "phone":"9199...", "template":"invoice_created", "data":{...} }`
- `POST /send-bulk`
  - Body: `{ "session_id":"your-session", "numbers":[...], "message":"..." }`

### Contacts / Groups

- `GET /contacts?session_id=your-session`
- `GET /groups?session_id=your-session`

## Django Compatibility Endpoints

This gateway also exposes endpoints compatible with the Django connector used in this repo:

- `POST /sessions/qr`
  - Body: `{ "session_id":"...", "webhook_url":"...", "webhook_secret":"..." }`
  - Returns: plain text QR payload (`data:image/png;base64,...`) or `connected`.
- `POST /messages/text`
  - Body: `{ "session_id":"...", "to":"9199...", "text":"..." }`

## Webhook Payload (Outgoing)

When a message arrives, the gateway POSTs JSON to the configured `webhook_url`:

```json
{
  "from": "9199xxxxxxx",
  "to": "91xxxxxxxxxx",
  "body": "Hello",
  "type": "chat",
  "message_id": "....",
  "timestamp": 1710000000,
  "name": "Customer Name",
  "session_id": "your-session"
}
```
