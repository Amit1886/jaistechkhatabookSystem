# Enterprise Dynamic Platform - Phase 1

## Why

The existing project already contains a large Django monolith with working models, Django Admin, DRF APIs, Channels, SaaS concepts, and platform apps. Rewriting it would break admin workflows and migrations. Phase 1 therefore adds FastAPI as a parallel enterprise API surface while keeping Django as the system of record for models, admin, migrations, and existing views.

## Where

- Django project remains in `khatapro/`.
- Existing domain apps remain in their current folders, for example `accounts/`, `commerce/`, `khataapp/`, `billing/`, and `apps/platform/*`.
- New enterprise core logic lives in `core/`.
- New primary FastAPI layer lives in `fastapi_app/`.
- FastAPI is mounted from `khatapro/asgi.py` under `/fastapi`.

## How

### Current Architecture Found

- Django apps: 80 installed app configs.
- Concrete Django models detected by metadata scanner: 549.
- Auth: custom `accounts.User`, Django auth, django-allauth, DRF SimpleJWT, and existing JWT middleware.
- Admin: existing Django Admin remains unchanged.
- APIs: existing DRF/mobile/platform APIs remain unchanged.
- Realtime: existing Channels ASGI websocket routing remains unchanged.
- Platform models already include tenant/company/role/device/audit primitives under `apps/platform/identity`.

### Phase 1 Implementation

- `core.metadata.scanner` introspects every installed Django model and produces Flutter/API-ready metadata.
- `core.dynamic_api.service.CRUDService` provides reusable list/detail/create/update/delete behavior for any Django model.
- `core.dynamic_api.schemas.DynamicSchemaFactory` generates read/create/update Pydantic JSON schemas from Django models.
- `core.permissions.engine.PermissionEngine` maps dynamic API actions to normal Django model permissions.
- `core.settings_engine.service.SettingsService` returns public and mobile auto-config settings with database, env, default, encrypted secret, and cache fallback.
- `fastapi_app` exposes health, settings, auth, metadata, and dynamic CRUD routers.
- `khatapro.asgi` mounts FastAPI at `/fastapi` and preserves Django + websocket behavior.
- Django Admin keeps `/superadmin/`, adds enterprise settings/offline sync administration, and configures Jazzmin sidebar ordering/icons for management groups.

### API Surface

- `GET /fastapi/health`
- `GET /fastapi/settings/public`
- `GET /fastapi/settings/mobile-config`
- `POST /fastapi/auth/signup`
- `POST /fastapi/auth/login`
- `POST /fastapi/auth/refresh`
- `POST /fastapi/auth/logout`
- `POST /fastapi/auth/password-reset`
- `GET /fastapi/permissions/me`
- `GET /fastapi/permissions/matrix`
- `GET /fastapi/permissions/catalog`
- `GET /fastapi/menu/`
- `GET /fastapi/menu/workspaces`
- `GET /fastapi/dashboard/`
- `GET /fastapi/dashboard/kpis`
- `GET /fastapi/reports/catalog`
- `GET /fastapi/reports/{model_key}/preview`
- `POST /fastapi/reports/{model_key}/export`
- `GET /fastapi/mobile/bootstrap`
- `GET /fastapi/mobile/screens`
- `GET /fastapi/mobile/screens/{model_key}`
- `GET /fastapi/offline/pull`
- `POST /fastapi/offline/push`
- `GET /fastapi/offline/conflicts`
- `GET /fastapi/plugins/`
- `GET /fastapi/plugins/manifest`
- `GET /fastapi/metadata/models`
- `GET /fastapi/metadata/models/{model_key}`
- `GET /fastapi/schemas/`
- `GET /fastapi/schemas/{model_key}`
- `GET /fastapi/crud/{model_key}`
- `GET /fastapi/crud/{model_key}?q=&ordering=&limit=&offset=&<metadata_filter>=`
- `POST /fastapi/crud/{model_key}`
- `GET /fastapi/crud/{model_key}/{pk}`
- `PATCH /fastapi/crud/{model_key}/{pk}`
- `DELETE /fastapi/crud/{model_key}/{pk}`
- `GET /fastapi/docs`
- `GET /fastapi/openapi.json`

### Lifecycle Diagrams

API request:

```text
Client -> ASGI -> /fastapi mount -> FastAPI router -> dependency auth/company context
       -> permission engine -> CRUD/service layer -> Django ORM -> JSON response
```

Authentication:

```text
Login/signup -> Django user lookup/check_password -> python-jose JWT pair
             -> client sends Bearer token -> dependency decodes token -> request user
```

Metadata:

```text
Django app registry -> model scanner -> fields/relations/choices/permissions
                    -> metadata JSON -> Pydantic schema factory
                    -> Flutter dynamic screens + CRUD docs + OpenAPI contracts
```

Future model generation:

```text
New Django model + migration -> app registry includes model
                           -> metadata scanner detects it
                           -> /metadata exposes fields and permissions
                           -> /schemas/{app.model} exposes read/create/update contracts
                           -> /crud/{app.model} exposes filtered CRUD API
                           -> Flutter renderer can build list/form/table
```

Mobile rendering:

```text
Flutter app -> /fastapi/mobile/bootstrap -> menu/dashboard/permission URLs
            -> /fastapi/mobile/screens/{model} -> DynamicTableScreen
            -> DynamicFormRenderer -> /fastapi/crud/{model}
            -> OfflineSyncQueue when network is unavailable
```

Offline POS:

```text
POS creates local operation -> OfflineSyncQueue persists operation
                         -> /fastapi/offline/push on reconnect
                         -> CRUDService applies create/update/delete
                         -> /fastapi/offline/pull refreshes local cache
```

Plugin strategy:

```text
Django addon app -> models/admin/optional router
                 -> plugin manifest discovers app
                 -> metadata scanner exposes models
                 -> dynamic menu/mobile/report engines consume metadata
```

## Next Phases

1. Add field-level permission masks and row policies on top of Django model permissions.
2. Add richer conflict strategies for POS sync such as client-wins, merge, and admin review.
3. Connect report exports to Celery-generated PDF/XLSX files.
4. Connect Flutter navigation to the new dynamic runtime screens.
5. Add per-company setting override UI and rollout workflow.
6. Add drag-drop admin menu ordering with persisted menu schema previews.

## Flutter Dynamic Runtime Files

- `flutter_offline_billing_app/lib/dynamic_platform/dynamic_metadata.dart`
- `flutter_offline_billing_app/lib/dynamic_platform/enterprise_api_client.dart`
- `flutter_offline_billing_app/lib/dynamic_platform/dynamic_form_renderer.dart`
- `flutter_offline_billing_app/lib/dynamic_platform/dynamic_table_screen.dart`
- `flutter_offline_billing_app/lib/dynamic_platform/offline_sync_queue.dart`

## Phase 2 Persistence Layer

- `core.EnterpriseSetting` stores admin-editable public/private/mobile/company settings. Secret values are signed with Django signing APIs and can be resolved by the FastAPI settings service.
- `core.OfflineSyncBatch` stores every mobile/POS sync push batch.
- `core.OfflineSyncOperation` stores every queued operation and its server result.
- `core.OfflineSyncConflict` stores sync errors/conflicts for admin review.
- `python manage.py sync_dynamic_metadata` syncs scanned Django models into `platform_identity.DynamicModule`, `DynamicField`, and `EnterprisePermission`.

Verification run:

```text
python manage.py migrate core --noinput -> OK
python manage.py sync_dynamic_metadata -> Synced 553 modules, 5415 fields, 2212 permissions
GET /fastapi/settings/public with DB setting override -> 200
POST /fastapi/offline/push -> persisted OfflineSyncBatch
python manage.py check -> OK
```

## Current Upgrade Strategy

1. Keep existing Django models and database tables as the source of truth.
2. Add metadata, settings, schema, and CRUD engines around the model registry.
3. Keep existing DRF/mobile URLs working while `/fastapi` becomes the dynamic platform API.
4. Use Django permissions for baseline authorization, then layer role/screen/button/API/plan policies over metadata.
5. Let Flutter consume `/mobile/bootstrap`, `/menu`, `/dashboard`, `/metadata`, `/schemas`, and `/crud` instead of hardcoded screens.
6. Move heavy report exports, sync reconciliation, notifications, and analytics refreshes to Celery workers backed by Redis.
