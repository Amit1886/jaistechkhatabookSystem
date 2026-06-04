# Billentra All-In-One Business Super App

This repository now contains a working enterprise super-app foundation across Flutter, Django Admin, FastAPI, PostgreSQL, Redis, WebSocket-ready sync, Docker and modular runtime configuration.

## Frontend

- Flutter app: `flutter_offline_billing_app/`
- Runtime shell: `lib/layouts/enterprise_shell.dart`
- Module router: `lib/workspaces/enterprise_workspace_renderer.dart`
- Super-app workspaces: `lib/modules/super_app/super_app_workspaces.dart`
- Dynamic runtime modules: `lib/modules/dynamic/`
- Offline sync: `lib/offline/offline_sync_engine.dart`
- State management: GetX controllers in `lib/controllers/`

Included connected UI slices:

- ERP dashboard
- POS and cart checkout
- Self-checkout kiosk
- Accounting, journal and GST reports
- Inventory, product grid, warehouse movement and barcode actions
- CRM pipeline
- eCommerce customer app and live orders
- B2B/vendor/purchase portal
- HRM workspace
- Reports with PDF/Excel actions
- Admin drag-drop builder
- API management with environment switching and WebSocket test state
- Customer app, delivery app and APK build center

## Backend

- Django Admin and models remain the system of record.
- FastAPI entry point: `fastapi_app/main.py`
- Super-app endpoints: `fastapi_app/routers/super_app.py`
- Existing enterprise runtime models: `enterprise_control/models.py`
- Existing WebSocket consumers: `enterprise_control/consumers.py`, `system_mode/consumers.py`

New API surface:

- `GET /super-app/bootstrap`
- `GET /super-app/dashboard`
- `POST /super-app/pos/checkout`
- `GET /super-app/admin/runtime-config`
- `POST /super-app/api-test`
- `POST /super-app/builds/apk`
- `WS /super-app/ws`

## Data And SaaS Model

The current Django apps already provide the multi-tenant base:

- Runtime modules, permissions, menus and widgets: `enterprise_control`
- POS domain: `pos`
- Commerce/product/order areas: `commerce`, `products`, `portal`
- Billing/subscriptions/features: `billing`
- Analytics/reports: `analytics`
- Procurement/vendor flows: `procurement`
- Settings, releases and APK metadata: `core_settings`, `distribution`

## Docker

Production compose file:

```bash
docker compose -f deployments/docker/docker-compose.enterprise.yml up --build
```

Services:

- `web`: Django ASGI + FastAPI routes
- `celery`: background jobs
- `postgres`: PostgreSQL 16
- `redis`: cache, queues and realtime support
- `nginx`: reverse proxy and static/media serving

## Development

Backend:

```bash
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

Flutter:

```bash
cd flutter_offline_billing_app
flutter run -d chrome
```

## Customization System

Admins can extend the app without changing the Flutter shell by editing:

- `DynamicModule`
- `DynamicMenuItem`
- `DashboardWidget`
- `DynamicButton`
- `ThemeConfig`
- `APIRegistry`
- `AppFeatureMapping`

The Flutter app consumes runtime config first and falls back to a complete offline module set when the backend is unavailable.
