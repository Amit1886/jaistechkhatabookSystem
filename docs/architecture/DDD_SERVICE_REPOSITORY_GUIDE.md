# DDD Service and Repository Guide

## Application Services

Application services orchestrate business use cases. They can call repositories, domain policies, and integration adapters.

Examples:

```text
apps/commerce/orders/application/services/place_order.py
apps/inventory/stock/application/services/reserve_stock.py
apps/financial/ledger/application/services/post_journal.py
apps/integrations/whatsapp/application/services/send_notification.py
```

## Domain Policies

Domain policies contain rules that should be testable without HTTP requests.

Examples:

```text
apps/commerce/orders/domain/policies/order_pricing_policy.py
apps/inventory/stock/domain/policies/stock_reservation_policy.py
apps/financial/ledger/domain/policies/posting_policy.py
```

## Repositories

Repositories isolate ORM access behind explicit query/write APIs.

Examples:

```text
apps/commerce/orders/infrastructure/repositories/order_repository.py
apps/inventory/products/infrastructure/repositories/product_repository.py
apps/crm/parties/infrastructure/repositories/party_repository.py
```

## Interfaces

Interfaces contain adapters to the outside world:

- `interfaces/api/`: DRF serializers/viewsets/routers.
- `interfaces/web/`: Django views/forms/templates coordination.
- `interfaces/admin/`: admin registrations and admin-only actions.

## First Extraction Candidates

Start with high-value low-risk services:

1. `commerce.services.reorder_planner` -> `apps.inventory.procurement.application.services`
2. `ledger.services.posting` -> `apps.financial.ledger.application.services`
3. WhatsApp sending helpers -> `apps.integrations.whatsapp.application.services`
4. Product stock/price lookup -> `apps.inventory.products.application.services`
5. Order placement logic -> `apps.commerce.orders.application.services`

## Testing Rule

Every extracted service should be tested through:

- old import path;
- new import path;
- current Django view or API behavior when practical.
