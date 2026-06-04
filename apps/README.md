# Enterprise Domain Architecture

This `apps/` package is the future Domain Driven Design home for the ERP platform.

Current production Django apps remain at the project root for backward compatibility. Do not move models, migrations, URL namespaces, templates, or app labels directly into this package without a migration phase.

## Domains

- `platform/`: identity, access control, admin console, settings, system mode.
- `financial/`: billing, subscriptions, ledger, payments, wallet, tax.
- `inventory/`: products, warehouses, procurement, stock, pricing.
- `commerce/`: orders, invoices, storefront, POS, vendors, coupons.
- `crm/`: parties, leads, portal, marketing, customer service.
- `industries/`: delivery, commission, location, devices.
- `analytics/`: reports, smart BI, performance, dashboards.
- `ai/`: engine, OCR, insights, fraud detection, voice, chatbot.
- `integrations/`: WhatsApp, SMS, bank import, external APIs, realtime, Shopify, courier.

## Migration Rule

Use this package as the target for new domain services first. Existing Django apps should be migrated through compatibility shims and test-backed phases.
