# Billentra SaaS Backend Blueprint (Backend-only)

This blueprint adds **multi-tenancy**, **JSON RBAC**, **subscription feature-gating**, **B2B/B2C pricing rules**, **Celery/Redis task structure**, and **context processors** without touching frontend templates.

> Important: Enabling `django-tenants` requires **PostgreSQL**. Billentra currently defaults to **SQLite** for desktop/dev. Use the staged rollout below to avoid breaking billing logic.

---

## 0) Staged rollout (recommended)

### Phase A (Safe, no breaking change)
- Keep current single-DB architecture.
- Implement JSON RBAC + `@require_permission()`.
- Implement B2B/B2C filtering/pricing as **service utilities**.
- Add Celery tasks for invoices/WhatsApp.
- Add context processors for tenant/user/cart counts.

### Phase B (True schema multi-tenancy)
- Switch DB to PostgreSQL.
- Install `django-tenants`.
- Enable `TenantMainMiddleware`, `TENANT_MODEL`, `TENANT_DOMAIN_MODEL`.
- Split apps into `SHARED_APPS` and `TENANT_APPS`.
- Run new migrations and migrate existing data into tenant schemas.

---

## 1) Folder structure (added)

```
saas/
  apps.py
  models.py
  middleware.py
  context_processors.py
  tasks.py
  views.py
  utils/
    permissions.py
    pricing.py
docs/
  SAAS_BACKEND_BLUEPRINT.md
```

---

## 2) Multi-tenancy (django-tenants)

### Models (seller + domain)
- `saas.models.SellerTenant` (TenantMixin)
- `saas.models.SellerDomain` (DomainMixin)

### Settings (when enabling)
Add requirements:
- `django-tenants`

Update `khatapro/settings.py`:
- Add `django_tenants` to `INSTALLED_APPS` (shared)
- Define:
  - `TENANT_MODEL = "saas.SellerTenant"`
  - `TENANT_DOMAIN_MODEL = "saas.SellerDomain"`
  - `DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)`
  - `SHARED_APPS`, `TENANT_APPS`
- Replace middleware:
  - `django_tenants.middleware.main.TenantMainMiddleware` (before SessionMiddleware)

Subdomains:
- `demo.billentra.com` -> Domain model row mapping.

---

## 3) Hybrid user model (existing + extension)

Billentra already uses `AUTH_USER_MODEL = "accounts.User"`.

To match requested fields safely:
- add fields to `accounts.User`:
  - `store_type` (`b2b|b2c|hybrid`)
  - `primary_role` (`owner|manager|billing|warehouse|accounts|vendor|staff|custom`)
  - `permissions_json` JSONField
  - `seller` FK (either to `vendors.Vendor` or `saas.SellerTenant` after Phase B)
- add `User.has_permission(key)`:
  - owner/admin -> allow all
  - else check `permissions_json` + role defaults

---

## 4) RBAC (JSON)

Models:
- `PermissionMaster(key,label,module,...)`
- `Role(key,label,...)`
- `RolePermission(role,permission)`

Decorator:
- `saas.utils.permissions.require_permission("key")`

---

## 5) B2B/B2C product rules

Backend-only rule engine in `saas.utils.pricing`:
- MOQ enforcement
- Bulk tier pricing
- hide B2B-only for B2C users (filter at queryset/service level)
- Pay-later / credit ledger to remain in billing/ledger domain (service integration)

---

## 6) Signals -> lifecycle hooks

No signals are added in this blueprint.

Recommended pattern:
- Move side-effects to **domain services** (explicit calls) and Celery tasks:
  - `on_transaction_created()`
  - `on_invoice_created()`
  - `on_stock_updated()`
  - `on_payment_logged()`
  - `on_credit_due_changed()`

---

## 7) Subscription billing + feature gating

Phase A uses the existing **billing** plan system:
- `billing.Plan`
- `billing.FeatureRegistry`
- `billing.PlanFeature`
- `billing.UserSubscription` (or existing subscription model in your billing app)

Enforcement:
- `accounts.User.has_permission("feature.some_key")` checks `billing.services.user_has_feature(user, "feature.some_key")`.
- Use `billing/services.py::sync_feature_registry()` to auto-add new features to plans.

Providers:
- Phase A: manual/admin
- Phase B: integrate `dj-stripe` or Razorpay subscriptions

---

## 8) Performance architecture

Redis:
- product list cache
- cart quote cache
- order count cache

Celery tasks:
- `saas.tasks.generate_invoice_pdf_task`
- `saas.tasks.whatsapp_notify_task`

---

## 9) Context processors

- `saas.context_processors.tenant_info`
- `saas.context_processors.user_permissions`
- `saas.context_processors.cart_count`
- `saas.context_processors.order_count`

Add these to `TEMPLATES[0]["OPTIONS"]["context_processors"]` when ready.

---

## 10) RBAC role-permission matrix (example)

| Role | Permissions |
|------|-------------|
| owner | `*` |
| manager | `approve_request`, `view_reports` |
| billing | `create_order`, `create_invoice`, `apply_discount` |
| warehouse | `stock_inward`, `stock_outward`, `stock_adjust` |
| accounts | `ledger_view`, `ledger_post`, `payment_record` |
| vendor | `vendor_access`, `store_settings` |
| staff | custom keys |
