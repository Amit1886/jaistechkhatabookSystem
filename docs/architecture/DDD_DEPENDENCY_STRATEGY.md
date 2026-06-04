# DDD Dependency Strategy

## Current Risk Areas

- `commerce` owns product, warehouse, order, invoice, payment, chat, coupons, WhatsApp order inbox, and reorder planning.
- `products`, `orders`, `payments`, and `warehouse` duplicate concepts already present in `commerce`.
- `billing` also contains commerce-like `Order`, `OrderItem`, `Payment`, and `Warehouse` models.
- `khataapp.Party` is used by commerce and finance workflows.
- `storefront` synchronizes with `commerce`, which can create reverse dependencies.
- `ledger` posts from several domains and must remain idempotent.

## Target Dependency Direction

```text
commerce.orders
  -> inventory.stock
  -> financial.billing
  -> financial.ledger
  -> integrations.notifications
  -> analytics.projections
```

## Circular Dependency Fixes

Use one of these patterns whenever two apps import each other:

1. Application service interface.
2. Domain event subscriber.
3. Lazy import inside function scope.
4. `django.apps.apps.get_model()` for model lookup during migration.
5. Read-only query service for reporting dependencies.

## Examples

Bad:

```text
commerce.views imports ledger.signals
ledger.services imports commerce.models
```

Better:

```text
commerce.orders.application.PlaceOrderService
  publishes OrderPlaced
financial.ledger.infrastructure.events
  consumes OrderPlaced and posts journal entries
```

## Compatibility Policy

Existing imports stay valid during migration:

```text
old.module.path -> imports new domain service -> returns same behavior
```

Only remove old modules after:

- all code imports new path;
- tests cover old and new behavior;
- release notes list the compatibility break;
- data migrations are complete when models are involved.
