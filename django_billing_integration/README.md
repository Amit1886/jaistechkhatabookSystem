# Django Billing Integration (Sample App)

This folder contains a reusable Django app (`whatsapp_integration/`) that demonstrates how to integrate a billing/ERP Django project with a **self-hosted WhatsApp Web gateway** (Node.js).

If you are using the main Django project in this repo, you already have a richer implementation under the `whatsapp/` app (multi-tenant accounts, control center, bots, commerce automation). Use this sample only if you want a minimal integration for another Django billing project.

## What you get

- `whatsapp_integration` Django app:
  - Models: `WhatsAppSession`, `MessageLog`, `TemplateMessage`
  - Services: `send_whatsapp_message`, `send_template`, `send_bulk`
  - Webhook receiver: `POST /webhook/incoming/`
  - Simple Bootstrap dashboard to request QR + send messages

## How to use in your Django project

1. Copy `django_billing_integration/whatsapp_integration/` into your Django project root (same level as other apps).
2. Add to `INSTALLED_APPS`:
   - `"whatsapp_integration.apps.WhatsAppIntegrationConfig"`
3. Add env vars (see `.env.example`):
   - `WA_GATEWAY_BASE_URL`
   - `WA_GATEWAY_API_KEY`
   - `WA_SESSION_ID`
4. Include URLs:
   - `path("whatsapp/", include(("whatsapp_integration.urls", "whatsapp_integration"), namespace="whatsapp_integration"))`
5. Run:
   - `python manage.py makemigrations whatsapp_integration`
   - `python manage.py migrate`

## Gateway server

Use the gateway in this repo:

- `whatsapp_gateway/`

Start it and set the same API key:

```bash
cd whatsapp_gateway
cp .env.example .env
npm install
npm run start
```

