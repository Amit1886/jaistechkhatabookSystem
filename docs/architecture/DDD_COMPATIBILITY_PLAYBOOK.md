# DDD Compatibility Playbook

This project must keep existing behavior while moving toward domain packages.

## Non-Negotiables

- Do not rename Django app labels in the same phase as moving code.
- Do not move models before service extraction.
- Do not change database table names unless a migration plan exists.
- Do not break URL namespaces such as `accounts`, `commerce`, `billing`, `ledger`, or `reports`.
- Do not move templates until views have compatibility coverage.

## Safe Code Migration Pattern

1. Create new domain service in `apps/<domain>/<context>/application/services/`.
2. Write or identify tests for current behavior.
3. Update old view/service to call the new service.
4. Keep old import path alive as a shim.
5. Run `manage.py check` and focused tests.
6. Repeat until the old module contains no business logic.

## Shim Example

Old module:

```python
# commerce/services/reorder_planner.py
from apps.inventory.procurement.application.services.reorder_planner import *  # compatibility shim
```

The real implementation lives in the new domain package, while old imports keep working.

## Model Migration Pattern

Model moves are last. If a model must move:

1. Keep `db_table`.
2. Keep or explicitly manage `AppConfig.label`.
3. Add migration tests.
4. Update content type and permission behavior deliberately.
5. Keep old code importable until all references are replaced.

## API Compatibility

Keep v1 endpoints stable:

```text
/api/v1/products/
/api/v1/orders/
/commerce/
/accounts/
/billing/
```

Introduce domain-first APIs as v2:

```text
/api/v2/inventory/products/
/api/v2/commerce/orders/
/api/v2/financial/ledger/
```

## Release Strategy

Use small releases:

- Release A: skeleton + docs.
- Release B: service extraction.
- Release C: views call services.
- Release D: repository layer.
- Release E: model consolidation/data migration.
