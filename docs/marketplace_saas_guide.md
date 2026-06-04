# Multi‑Vendor SaaS Storefront (Shopify‑like) — Integration Guide

This project already contains ERP-style Billing/Inventory/Orders modules. The new `vendors` + `storefront` apps extend it into a **multi-vendor SaaS e-commerce** layer without changing existing billing flows.

## 1) Enable vendor subdomains

1. Ensure these apps are installed (already added in `khatapro/settings.py`):
   - `vendors`
   - `storefront`
2. Ensure middleware is enabled (already added in `khatapro/settings.py`):
   - `vendors.middleware.VendorSubdomainMiddleware`
3. Configure your base domain (optional but recommended):
   - Set `MARKETPLACE_BASE_DOMAIN=domain.com` in `.env`
   - Vendor store resolves as `vendor.domain.com`

Dev shortcut:
- `vendor.localhost` also resolves (e.g. `acme.localhost:8000`).

## 2) Database (MySQL)

This project uses SQLite by default for desktop/local. For MySQL, set `DATABASE_URL`:

Example:
```
DATABASE_URL=mysql://USER:PASSWORD@HOST:3306/DBNAME
```

Run migrations after switching DB:
```
python manage.py migrate
```

## 3) Create a vendor (store)

### API (recommended)

1. Create/login a user (existing accounts flow).
2. Call:
   - `POST /api/vendor/register/`
   - body: `{ "name": "Acme Store", "subdomain": "acme", "primary_warehouse_id": 1 }`

### Admin

Create `vendors.Vendor` and optionally link warehouses via `vendors.VendorWarehouse`.

## 4) Products → Online sync (critical)

Existing model reused:
- `products.Product`

Added fields:
- `products.Product.is_online`
- `products.Product.slug`
- `products.Product.description`
- `products.ProductMedia` for multiple images/videos

Auto sync:
- When a `products.Product` is created/updated, a **signal** ensures a `storefront.VendorProductListing` exists for vendors that have this product in any linked warehouse inventory (`products.WarehouseInventory`).

How to publish a product:
1. Ensure the vendor is linked to a warehouse (`vendors.VendorWarehouse`) and that warehouse has inventory rows (`products.WarehouseInventory`) for the product.
2. Set `Product.is_online=True`.

## 5) Storefront UI (Django templates)

Vendor subdomain root renders storefront:
- `GET /` on `acme.domain.com` → product grid
- `GET /p/<product_slug>/` → product detail

Non-subdomain browsing (useful in local/dev):
- `GET /store/` (expects vendor subdomain; otherwise shows “Store not found”)

## 6) Store APIs (DRF)

All endpoints are under `/api/` (as requested):

- Products: `GET /api/products/?vendor_id=...` (or via vendor subdomain)
  - Recommendations: `GET /api/products/<listing_id>/recommendations/`
- Cart: `GET /api/cart/`, `POST /api/cart/add/`, `POST /api/cart/update_item/`, `POST /api/cart/remove_item/`
- Wishlist: `GET /api/wishlist/`, `POST /api/wishlist/add/`, `POST /api/wishlist/remove/`
- Orders: `GET/POST /api/orders/`
  - Vendor accept/reject: `POST /api/orders/<id>/accept/`, `POST /api/orders/<id>/reject/`
  - Invoice PDF: `GET /api/orders/<id>/invoice/`
- Payments (per-vendor skeleton): `POST /api/payments/initiate/`
- Shipping (per-vendor skeleton): `POST /api/shipping/create_shipment/`, `GET /api/shipping/track/?order_id=...`
- Vendor dashboard: `GET /api/vendor-dashboard/`

### Admin marketplace APIs

Requires `Super Admin` group (or superuser).

- Summary: `GET /api/admin/marketplace/`
- Commission settings: `GET/POST /api/admin/marketplace/settings/`
- Manual settlement (paid orders): `POST /api/admin/marketplace/settle_order/` body `{ "order_id": <id> }`

### Vendor management APIs (staff/owner)

These are under `/api/vendor/`:

- Listings CRUD: `/api/vendor/listings/`
  - Publish/unpublish: `POST /api/vendor/listings/<id>/set_online/`
  - Feature: `POST /api/vendor/listings/<id>/set_featured/`
  - Upload images/videos: `POST /api/vendor/listings/<id>/upload_media/` (multipart `file`, `media_type=image|video`)
- Payment gateway configs: `/api/vendor/payment-gateways/`
  - Razorpay example `config`: `{ "key_id": "...", "key_secret": "..." }`
- Shipping provider configs: `/api/vendor/shipping-providers/`
  - Shiprocket example `config`: `{ "email": "...", "password": "...", "pickup_location": "Primary", "webhook_secret": "..." }`

### Webhooks (provider callbacks)

Configure per vendor and point providers to these URLs:

- Razorpay: `POST /api/payments/razorpay/webhook/<vendor_id>/`
  - Set `VendorPaymentGatewayConfig.config.webhook_secret`
  - Razorpay sends `X-Razorpay-Signature` header (HMAC-SHA256 of raw body)
- Shiprocket: `POST /api/shipping/shiprocket/webhook/<vendor_id>/`
  - Set `VendorShippingProviderConfig.config.webhook_secret`
  - Send secret in `X-Webhook-Secret` (or `X-Shiprocket-Signature`) header

Webhook idempotency:
- Both webhook endpoints dedupe using `sha256(raw_body)` stored in `storefront.StoreWebhookDelivery` (prevents double-processing on retries).

Shiprocket improvements:
- `POST /api/shipping/create_shipment/` now also attempts `assign/awb` after creating an adhoc order (so you get an AWB tracking number).
- `GET /api/shipping/track/?order_id=...` attempts live provider tracking when Shiprocket config is active.
- Optional polling task: `storefront.tasks.poll_shiprocket_tracking` (run via Celery beat if you use Celery).

Shiprocket ops endpoints (vendor/staff):
- `POST /api/shipping/shiprocket_label/` body: `{ "order_id": <store_order_id> }`
- `POST /api/shipping/shiprocket_pickup/` body: `{ "order_id": <id>, "pickup_date": "YYYY-MM-DD", "retry": true }`
- `POST /api/shipping/shiprocket_manifest/` body: `{ "order_id": <id> }`
- `POST /api/shipping/shiprocket_manifest_print/` body: `{ "order_id": <id> }` (requires Shiprocket `order_id` in shipment payload)

One-click print/download (proxy):
- `GET /api/shipping/shiprocket_label_download/?order_id=<id>`
- `GET /api/shipping/shiprocket_manifest_download/?order_id=<id>`

## 7) OTP login (customer)

- Start: `POST /api/auth/otp/start/` with `{ "mobile": "9xxxxxxxxx" }` or `{ "email": "a@b.com" }`
- Verify: `POST /api/auth/otp/verify/` with `{ "otp_id": 123, "code": "123456" }`

On success, you get JWT `access` + `refresh` tokens.

## 8) WhatsApp notifications

Uses existing WhatsApp module:
- If the vendor owner has an active `whatsapp.WhatsAppAccount`, the storefront sends WhatsApp messages on:
  - order placed
  - order accepted/rejected

## 9) GST invoice PDF

On vendor accept, the system attempts to render a PDF via `xhtml2pdf` and attaches it to:
- `storefront.StoreOrder.invoice_pdf`

If PDF renderer is unavailable, `GET /api/orders/<id>/invoice/` returns `501`.

## 10) Next extensions (recommended)

- Add full checkout UI + payment verification webhooks (Razorpay/Stripe/Paytm).
- Add shipment label generation + tracking webhooks (Shiprocket/Delhivery).
- Add richer product media UI (carousel/reels) in templates or React storefront.

## Demo: Shiprocket credentials (seed)

If you run the existing seed command `accounts.management.commands.seed_demo_users`, it will also create:
- Demo Warehouse: code `DEMO`
- Demo Vendor: subdomain `demo` (owner: `Demotest3`)
- Shiprocket provider config for that vendor

For real Shiprocket testing, set these environment variables before running seed:

```
SHIPROCKET_EMAIL=your_shiprocket_email
SHIPROCKET_PASSWORD=your_shiprocket_password
SHIPROCKET_WEBHOOK_SECRET=your_random_secret
```

## Wallet + Commission + Settlement

- Vendor payout is credited to **vendor owner wallet** (`wallet.Wallet`) when `StoreOrder.payment_status=paid`.
- Commission percent is configured via `storefront.PlatformSettings.commission_percent`.
- Platform commission is credited to `PlatformSettings.platform_user` wallet (set it to your superadmin user).
