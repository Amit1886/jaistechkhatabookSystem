# Enterprise Dynamic UI - Phase 2

## Completed

- Added persisted dynamic UI builders:
  - `enterprise_control.DynamicButton`
  - `enterprise_control.DynamicMenuItem`
  - existing `DynamicModule`, `Workspace`, `DashboardWidget`, and `ThemeConfig`
- Added Django Admin builders for modules, buttons, sidebar items, workspaces, widgets, themes, devices, and audit logs.
- Added enterprise admin shell assets:
  - `templates/admin/base_site.html`
  - `static/enterprise_admin/enterprise_admin.css`
  - `static/enterprise_admin/enterprise_admin.js`
- Added runtime FastAPI endpoints:
  - `GET /fastapi/menu/`
  - `GET /fastapi/menu/launcher`
  - `GET /fastapi/menu/sidebar`
  - `GET /fastapi/menu/buttons`
  - `GET /fastapi/mobile/bootstrap`
- Added Flutter runtime design components:
  - `EnterpriseRuntimeButton`
  - `EnterpriseActionStrip`
  - `EnterpriseLauncherGrid`
  - `EnterpriseSkeleton`
- Extended Flutter config parsing for `sidebar`, `launcher`, and `buttons`.
- Seeded default enterprise UI with:
  - Dashboard
  - POS
  - Orders
  - Billing
  - Products
  - Reports
  - SelfCheckout
  - CRM

## Runtime Flow

```text
Django Admin builder
  -> DynamicModule / DynamicButton / DynamicMenuItem / DashboardWidget
  -> FastAPI runtime payload
  -> Flutter EnterpriseAppConfig
  -> Runtime launcher, sidebar, dashboard buttons, and module screens
```

## Commands

```text
python manage.py migrate enterprise_control --noinput
python manage.py seed_enterprise_ui
python manage.py check
```

## Verification

```text
python manage.py check -> OK
python -m py_compile enterprise_control/management/commands/seed_enterprise_ui.py enterprise_control/services.py fastapi_app/routers/menu.py -> OK
bootstrap payload smoke test -> 8 modules, 8 sidebar items, 8 launcher items, 8 buttons
```

Flutter SDK commands were available but did not return before timeout in this shell:

```text
flutter analyze -> timed out
flutter analyze --no-pub -> timed out
dart analyze -> timed out
```
