# Multi-Tenant WhatsApp Commerce Automation (Django)

This repo now includes a multi-tenant WhatsApp automation layer that plugs into the existing ERP/Billing modules (`commerce`, `khataapp`, `portal`, `payments`, `pos`).

## What's implemented (MVP)

- **Multi-tenant WhatsApp accounts**: each user can connect their own number (`whatsapp.WhatsAppAccount`).
- **One number -> one bot engine**: each account has exactly one `whatsapp.Bot`.
- **Providers**
  - **Meta WhatsApp Cloud API (Official)**: inbound webhook + outbound send.
  - **Web Gateway (QR / WhatsApp Web / device gateway)**: inbound webhook + outbound send (QR generation is delegated to your gateway).
- **Webhook engine**: inbound messages are stored + queued for processing.
- **Bot engine**: menu/cart/order flow via `commerce` + rule-based smart replies.
- **User visual flow builder actions**: visual flow `action` nodes can run commerce actions (catalog/cart/checkout/orders/track) and AI smart replies.
- **Broadcasts**: create + run broadcast campaigns (Celery task).
- **Operator (Admin) commands via WhatsApp**: add `whatsapp.WhatsAppOperator` (or use `User.mobile`) to run ERP commands like `sales today`, `low stock`, `sale 5 item 250`, and `broadcast all: ...`.
- **Security**: message bodies + provider tokens are encrypted at rest (`WA_ENCRYPTION_KEY` optional).
- **Payments (MVP)**: bot generates a public Payment Link + public Invoice PDF link during checkout (requires `BASE_URL`).
- **Invoice PDF (Cloud API)**: when `invoice_pdf_url` is available, the system also attempts to send it as a WhatsApp **document**.

## Key URLs

### User UI

- WhatsApp Control Center: `GET /ai-tools/whatsapp/`
- Legacy WhatsApp Accounting: `GET /ai-tools/whatsapp/accounting/`

## Settings

- `BASE_URL` (important): Used to generate clickable links sent inside WhatsApp (Payment Link, Invoice PDF).  
  Example: `https://erp.yourdomain.com` (no trailing slash).
- `WA_ENCRYPTION_KEY` (recommended): Encrypts tokens + message bodies at rest.
- `WA_GATEWAY_BASE_URL` / `WA_GATEWAY_API_KEY` (optional): Prefill defaults for the user-side Setup Wizard (QR gateway).
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`: Redis URLs for async processing.

### Webhooks

- **Meta Cloud API webhook (per account)**  
  `GET/POST /api/whatsapp/meta/<uuid:account_id>/webhook/`  
  - `GET` is used by Meta to verify webhook (uses `account.meta_verify_token`).
  - `POST` receives inbound messages.

- **Gateway inbound webhook (per account)**  
  `POST /api/whatsapp/gateway/<uuid:account_id>/inbound/`  
  Security: pass the account secret in `X-WA-Secret` header (or `?secret=`).

### REST APIs (DRF)

Base: ` /api/v1/whatsapp/`

- `GET/POST /api/v1/whatsapp/accounts/`
- `POST /api/v1/whatsapp/accounts/<id>/healthcheck/`
- `POST /api/v1/whatsapp/accounts/<id>/request_qr/` (web_gateway only)
- `GET /api/v1/whatsapp/accounts/<id>/analytics/?days=7`
- `GET/POST /api/v1/whatsapp/bot-flows/` (no-code builder backend)
- `GET /api/v1/whatsapp/bot-templates/` (active global templates)
- `GET/POST /api/v1/whatsapp/broadcasts/`
- `POST /api/v1/whatsapp/broadcasts/<id>/start/`
- `GET /api/v1/whatsapp/message-logs/?account=<uuid>`

### Public payment + invoice links

- Payment page (public): `GET/POST /portal/pay/<token>/`
- Invoice PDF (public): `GET /portal/pay/<token>/invoice.pdf`

> Note: These URLs are generated and sent by the WhatsApp checkout flow. In production, set `BASE_URL` to your public domain so the links are clickable from WhatsApp.

## Meta Cloud API setup (per WhatsAppAccount)

1. In `GET /ai-tools/whatsapp/`, add an account with provider `meta_cloud_api`.
2. Fill:
   - `meta_phone_number_id` (from Meta WhatsApp Manager)
   - `meta_access_token` (permanent token recommended)
   - optional: `meta_app_secret` (enables webhook signature verification)
3. In Meta App Dashboard > Webhooks:
   - Callback URL: shown in control center (`/api/whatsapp/meta/<account_id>/webhook/`)
   - Verify token: shown in control center (`selected.meta_verify_token`)
4. Subscribe to WhatsApp messages/events for that WABA/phone number.

## Web Gateway setup (QR / WhatsApp Web gateway)

This project supports a **gateway integration point**. Your gateway service must:

- POST inbound JSON to `POST /api/whatsapp/gateway/<account_id>/inbound/`
- Include header `X-WA-Secret: <account.webhook_secret>`
- Minimal payload example:
  - `{ "from": "9199xxxxxxx", "to": "91xxxxxxxxxx", "body": "hi", "type": "text", "message_id": "ext-123" }`

### Included self-hosted gateway (Node.js)

This repo includes a production-style gateway server under `whatsapp_gateway/` that implements:

- QR login + session persistence (WPPConnect token store)
- REST APIs for send message/template/bulk
- Webhook push into Django on incoming messages
- Django-compatible endpoints used by this project:
  - `POST /sessions/qr`
  - `POST /messages/text`

Run it locally:

```bash
cd whatsapp_gateway
npm install
cp .env.example .env
npm run start
```

Then in Django, open:

- Setup Wizard: `GET /ai-tools/whatsapp/setup/`
  - Use provider `web_gateway`
  - `Gateway Base URL`: `http://127.0.0.1:3100`
  - `Gateway API Key`: must match gateway `GATEWAY_API_KEY`
  - Click **Request QR** and scan from WhatsApp Business App > Linked devices.

## Migrations (required)

After pulling these changes, run:

```bash
python manage.py migrate
```

The repo already includes the required migrations:

- `whatsapp/migrations/0002_multitenant_whatsapp_automation.py`
- `commerce/migrations/0026_whatsapp_account_links.py`
- `whatsapp/migrations/0003_bot_templates_and_quick_commerce.py`

## Seed default templates (recommended)

Creates the admin global template library (Welcome/Order/Payment/Support/etc):

```bash
python manage.py seed_whatsapp_templates
```

## Quick commerce mode (optional)

Enable per WhatsApp account from `GET /ai-tools/whatsapp/`:

- Auto-accept WhatsApp orders (`status=accepted`)
- Optionally auto-assign a `FieldAgent`

## Celery / Redis

Inbound processing + broadcasts use Celery tasks:

- `whatsapp.tasks.process_inbound_message`
- `whatsapp.tasks.run_broadcast_campaign`

Run Redis + Celery worker (server deployment):

```bash
celery -A khatapro worker -l INFO
celery -A khatapro beat -l INFO
```

## Encryption

Optional env var:

- `WA_ENCRYPTION_KEY`  
  - If set to a valid Fernet key, it’s used directly.
  - Otherwise, it’s used as material to derive a Fernet key.

If not set, the system derives a key from Django `SECRET_KEY`.

## AI smart replies (optional)

Rule-based smart replies are enabled by default (price + order status).  
To enable LLM fallback (Hinglish) set:

- `WHATSAPP_AI_ENABLED=true`
- `OPENAI_API_KEY=...`
- optional: `WHATSAPP_AI_MODEL=gpt-4o-mini`

## Notes on WhatsApp Web automation

Automating WhatsApp Web / WhatsApp Business App with unofficial libraries can violate WhatsApp terms and may risk number bans.

This repo supports **Web Gateway** as an *integration point*: you host a separate gateway service and connect it here. Prefer **Meta Cloud API** for production.

## Scaling checklist (10k tenants / 100k msgs/day)

- Use Redis as Celery broker/result backend.
- Run multiple Celery workers; keep webhook views fast (store + enqueue).
- Use Postgres in production; keep indexes (already added in models/migrations).
- Add monitoring for queue lag + webhook error rates.
- Rotate secrets and set `WA_ENCRYPTION_KEY` explicitly in production.
