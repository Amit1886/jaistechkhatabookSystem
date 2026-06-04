# Channels Setup (WhatsApp / SMS / Email / Shopify)

## 1) Create `.env`

Copy:

- `.env.example` → `.env`

Fill actual values and restart server.

## 2) Shopify

Env vars:

- `SHOPIFY_CLIENT_ID`
- `SHOPIFY_CLIENT_SECRET`
- `SHOPIFY_SCOPES` (comma-separated)

Shopify Dev Dashboard redirect URL:

- `http://127.0.0.1:8080/integrations/shopify/oauth/callback/`

Vendor connect UI:

- `http://127.0.0.1:8080/store/<subdomain>/vendor/settings/apps/`

## 3) WhatsApp

Global provider settings (admin):

- `http://127.0.0.1:8080/settings/center/`

Vendor toggle/config:

- `http://127.0.0.1:8080/store/<subdomain>/vendor/settings/notifications/`

Optional local gateway:

- `WA_GATEWAY_BASE_URL`
- `WA_GATEWAY_API_KEY`

## 4) SMS

Vendor toggle/config:

- `http://127.0.0.1:8080/store/<subdomain>/vendor/settings/notifications/`

Admin SMS dashboard:

- `http://127.0.0.1:8080/settings/sms/`

## 5) Email (SMTP)

Env vars:

- `EMAIL_HOST`, `EMAIL_PORT`
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS` / `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`

In `DEBUG=True`, default backend is console (emails print in logs).

## 6) Migrations

Use venv Python:

- `venv\\Scripts\\python.exe manage.py migrate`

