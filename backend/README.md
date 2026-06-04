# JaisTech ERP Backend Architecture

This folder documents the enterprise structure requested for the Django platform. The runnable implementation is the `jaistech_erp` Django app, mounted at `/api/` in `khatapro.urls`.

## Runtime URLs

- Django: `http://127.0.0.1:8080`
- FastAPI: `http://127.0.0.1:8000`
- JWT: `POST /api/auth/token/`
- App bootstrap: `GET /api/app/bootstrap/`
- Dashboard: `GET /api/dashboard/`
- Dynamic model API: `/api/dynamic/<app_label>/<model_name>/`

## Enterprise Packages

- `apps/`: bounded ERP domains.
- `api/`: DRF routers, dynamic API generation, OpenAPI.
- `services/`: business orchestration and background service boundaries.
- `permissions/`: dynamic RBAC policy engine.
- `modules/`: module registry and no-code module metadata.
- `settings_engine/`: admin-driven app, branding, tax, printer, payment, and sync settings.
- `notifications/`: email, SMS, push, and in-app notification boundaries.
- `reports/`: export, analytics, GST, P&L, and inventory reports.
- `sync/`: offline queue and conflict resolution.
- `websocket/`: Channels/FastAPI realtime surfaces.
- `analytics/`: KPI aggregation and future AI analytics.

## Local Setup

```powershell
cd "c:\Users\hp\Pictures\gethub project\jaistechkhatabookSystem"
python manage.py migrate
python manage.py seed_jaistech_erp
python manage.py runserver 127.0.0.1:8080
```

Demo login:

- Email: `demo.test3@jaistech.local`
- Password: `Demo@12345`
- Mobile: `9999999999`

