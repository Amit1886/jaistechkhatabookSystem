# DDD Target Structure

The long-term target is a domain-first project while preserving Django compatibility.

```text
apps/
  platform/
    identity/
      application/
      domain/
      infrastructure/
      interfaces/
    admin_console/
    settings/
    access_control/
    system_mode/
  financial/
    billing/
    subscriptions/
    ledger/
    payments/
    wallet/
    tax/
  inventory/
    products/
    warehouses/
    procurement/
    stock/
    pricing/
  commerce/
    orders/
    invoices/
    storefront/
    pos/
    vendors/
    coupons/
  crm/
    parties/
    leads/
    portal/
    marketing/
    customer_service/
  industries/
    delivery/
    commission/
    location/
    devices/
  analytics/
    reports/
    smart_bi/
    performance/
    dashboards/
  ai/
    engine/
    ocr/
    insights/
    fraud_detection/
    voice/
    chatbot/
  integrations/
    whatsapp/
    sms/
    bank_import/
    api_integrations/
    realtime/
    shopify/
    courier/
```

Each bounded context should use this internal layout when code starts moving:

```text
application/
  commands/
  queries/
  services/
domain/
  entities/
  policies/
  value_objects/
infrastructure/
  repositories/
  events/
  tasks/
interfaces/
  api/
  web/
  admin/
```

## Boundary Rule

Business workflows depend inward:

```text
interfaces -> application -> domain
infrastructure -> application/domain
```

Cross-domain calls should go through application services or domain events, not direct model imports.
