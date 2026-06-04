# Shopify Partner + Integration Setup

This project supports a vendor-level Shopify OAuth connection so a vendor can connect `yourstore.myshopify.com` from:

- `http://127.0.0.1:8080/store/<subdomain>/vendor/settings/apps/`

## 1) Create a Shopify Partner / Dev Dashboard app

1. Create an app in Shopify Dev Dashboard (Partner / public app flow).
2. Copy **Client ID** and **Client secret**.
3. Add the redirect URL:
   - `https://<your-domain>/integrations/shopify/oauth/callback/`
   - Local dev example: `http://127.0.0.1:8080/integrations/shopify/oauth/callback/`

## 2) Configure this Django project

Set these env vars (for example in `.env`):

- `SHOPIFY_CLIENT_ID=...`
- `SHOPIFY_CLIENT_SECRET=...`
- `SHOPIFY_SCOPES=read_orders,read_products,read_customers`

Restart the server.

Tip: See `.env.example` for a ready template.

## 3) Connect from Vendor Settings

Open:

- `http://127.0.0.1:8080/store/demo/vendor/settings/apps/`

In **Shopify Connection**, enter:

- `mystore.myshopify.com`

Click **Connect Shopify** and approve permissions in Shopify.

## Notes

- Tokens are stored per vendor in `vendors.VendorShopifyConnection`.
- This scaffolding stores tokens in plaintext (development-friendly). For production, store tokens encrypted / in a vault.
