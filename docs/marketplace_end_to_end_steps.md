# End-to-End Steps (Billing → Multi‑Vendor E‑commerce)

This repo already includes the required marketplace modules (`vendors`, `storefront`) integrated into the existing billing/inventory system **without changing existing billing logic**.

## 1) Migrations

Run:
```
python manage.py migrate
```

Marketplace migrations added:
- `vendors/migrations/0001_initial.py`
- `products/migrations/0002_product_online_fields_and_media.py`
- `products/migrations/0003_backfill_product_slugs.py`
- `storefront/migrations/0001_initial.py`
- `storefront/migrations/0002_storewebhookdelivery.py`
- `storefront/migrations/0003_storeshipment_shiprocket_fields.py`
- `storefront/migrations/0004_platformsettings_and_settlement.py`

## 2) Seed demo users + demo vendor + Shiprocket

Set Shiprocket creds in `.env` (recommended):
```
SHIPROCKET_EMAIL=...
SHIPROCKET_PASSWORD=...
SHIPROCKET_WEBHOOK_SECRET=...
```

Then run:
```
python manage.py seed_demo_users
python manage.py seed_marketplace_demo
```

Outputs:
- `Superadmin / Admin@123`
- `Demotest3 / Demo@123`
- Vendor: subdomain `demo`
- Shiprocket config enabled for `demo`
- Platform commission defaults to 2% (PlatformSettings id=1)
- Demo marketplace products + inventory + online listings

## 3) Vendor subdomain store

Configure:
- `.env`: `MARKETPLACE_BASE_DOMAIN=yourdomain.com`

Storefront:
- `demo.yourdomain.com/` (grid)
- `demo.yourdomain.com/p/<product_slug>/` (detail)

Dev shortcut:
- `demo.localhost:8000/`

Local URL (no subdomain required):
- `http://127.0.0.1:8080/store/demo/`

## 4) Product auto‑sync to store

Publish product:
1. Ensure vendor is linked to a warehouse (`vendors.VendorWarehouse`)
2. Ensure inventory rows exist (`products.WarehouseInventory`) for those products
3. Set `products.Product.is_online=True`

Signals:
- `products/signals.py` creates/updates `storefront.VendorProductListing`

Media:
- Upload multiple images/videos as `products.ProductMedia`
- Or via API: `POST /api/vendor/listings/<id>/upload_media/`

## 5) Customer auth (OTP)

- `POST /api/auth/otp/start/` (mobile/email)
- `POST /api/auth/otp/verify/` → returns JWT

## 6) Shopping

- Products: `GET /api/products/` (+ filters)
- Cart: `GET /api/cart/`, `POST /api/cart/add/`
- Wishlist: `GET /api/wishlist/`
- Place order: `POST /api/orders/`

## 7) Vendor order management

- Accept: `POST /api/orders/<id>/accept/`
  - Creates internal ERP order (`orders.Order`) using the same order_number
  - Attaches invoice PDF to `storefront.StoreOrder.invoice_pdf` (best-effort)
- Reject: `POST /api/orders/<id>/reject/`

## 8) Payments (Razorpay)

1. Configure vendor payment gateway:
   - `POST /api/vendor/payment-gateways/`
   - provider `razorpay`, set config:
     - `key_id`, `key_secret`, `webhook_secret`
2. Initiate payment:
   - `POST /api/payments/initiate/` body `{ "order_id": <id>, "provider": "razorpay" }`
3. Webhook:
   - `POST /api/payments/razorpay/webhook/<vendor_id>/`
   - On capture: marks `StoreOrder.payment_status=paid`

Idempotency:
- Webhook requests are deduped by `sha256(raw_body)` stored in `storefront.StoreWebhookDelivery`.

## 9) Auto settlement (Wallet + Commission)

When `StoreOrder.payment_status=paid`:
- Credits vendor owner wallet with `vendor_amount`
- Credits platform wallet user with `commission_amount` (from `storefront.PlatformSettings`)

Admin APIs:
- `GET /api/admin/marketplace/`
- `GET/POST /api/admin/marketplace/settings/`
- `POST /api/admin/marketplace/settle_order/`

## 10) Shipping (Shiprocket)

1. Configure:
   - `POST /api/vendor/shipping-providers/` provider `shiprocket` config:
     - `email`, `password`, `pickup_location`, `webhook_secret`
2. Create shipment:
   - `POST /api/shipping/create_shipment/` body `{ "order_id": <id>, "provider": "shiprocket" }`
   - Auto attempts AWB assignment
3. Ops:
   - Label: `POST /api/shipping/shiprocket_label/`
   - Pickup: `POST /api/shipping/shiprocket_pickup/`
   - Manifest: `POST /api/shipping/shiprocket_manifest/`
   - Manifest print: `POST /api/shipping/shiprocket_manifest_print/`
4. One-click download (proxy):
   - `GET /api/shipping/shiprocket_label_download/?order_id=<id>`
   - `GET /api/shipping/shiprocket_manifest_download/?order_id=<id>`
5. Webhook:
   - `POST /api/shipping/shiprocket/webhook/<vendor_id>/`

## 11) WhatsApp notifications

Uses existing WhatsApp module (`whatsapp.WhatsAppAccount`) to notify:
- order placed
- accepted/rejected
- shipped/delivered (Shiprocket webhook)
