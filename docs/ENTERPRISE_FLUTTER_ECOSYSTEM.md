# Enterprise Flutter Ecosystem

This upgrade keeps Django as the master control system and adds a backend-driven Flutter shell on top of the existing offline billing app.

## Runtime Contract

Flutter can load either the existing additive bootstrap `/api/app/bootstrap/` or the enterprise control bootstrap `/api/dashboard/` after login. Django returns:

- `theme`: brand, colors, radius, density, animation mode
- `modes`: mobile, tablet, desktop, POS, self checkout, kiosk, landscape, touch
- `modules`: title, icon, route, web URL, permission, color, visibility, order
- `widgets`: dashboard widgets controlled by permission
- `permissions`: `can_view`, `can_create`, `can_edit`, `can_delete`, `can_export`, `can_print`, `can_manage`
- `features`: offline, sync, PWA, OTP, QR, biometric, scanner, printer, Hindi, shortcuts, WebSocket
- `api`: canonical backend endpoints for future module services

## Flutter Structure

The enterprise layer is additive:

- `lib/models/enterprise_app_config.dart`: backend bootstrap models
- `lib/services/enterprise_app_service.dart`: API loader with offline fallback
- `lib/controllers/enterprise_app_controller.dart`: dynamic app state
- `lib/permissions/permission_engine.dart`: role UI gate
- `lib/layouts/enterprise_shell.dart`: desktop sidebar, mobile bottom nav, topbar
- `lib/dashboard/enterprise_dashboard_screen.dart`: dynamic dashboard widget grid
- `lib/modules/dynamic/dynamic_module_screen.dart`: reusable module surface
- `lib/themes/dynamic_theme_engine.dart`: backend theme generator
- `lib/core/responsive/enterprise_breakpoints.dart`: mobile/tablet/desktop/POS/ultrawide layout classifier
- `lib/widgets/enterprise/enterprise_glass.dart`: premium glass surface used across workspaces
- `lib/workspaces/enterprise_workspace_renderer.dart`: central role/workspace/module renderer

The existing offline billing screens, database, sync, login, invoices, products, parties, reports, and settings remain available and are embedded where possible.

## Native Super App Shell

The app now launches `EnterpriseShell` directly instead of only wrapping the Django dashboard in a webview. It still keeps the web entrypoints available per module through `web_url`, but the first-class experience is native Flutter:

- Desktop and ultrawide: glass command rail, workspace topbar, AI copilot button, native module viewport
- Mobile and tablet: floating Material 3 navigation, adaptive widget grids, touch-friendly module pages
- POS: touch billing grid, barcode entry, cart panel, QR payment and thermal print actions
- Self checkout/kiosk: scan-first customer flow
- CRM/ecommerce/supplier/analytics: kanban-style workspace boards ready for backend dynamic records
- Admin/control: backend modules, permissions, widgets, themes, and workspace data drive what appears

`EnterpriseAppService` prefers the new Django endpoint:

```http
GET /api/dashboard/?platform=desktop
```

If that endpoint is unavailable, it falls back to:

```http
GET /api/app/bootstrap/?mode=desktop
```

This keeps compatibility with existing partially implemented APIs while allowing the new enterprise backend control center to take over.

## UI Engine

The Flutter UI is data-driven:

- `EnterpriseAppConfig` parses backend `workspace`, `theme`, `modules`, `menu`, `widgets`, `permissions`, `features`, and `realtime`
- `PermissionEngine` blocks module surfaces using backend permissions
- `EnterpriseWorkspaceRenderer` chooses the right workspace surface for each selected module
- `DynamicModuleScreen` embeds existing offline screens where they already exist and renders premium dynamic surfaces for missing modules
- `EnterpriseDashboardScreen` merges live dashboard API cards with backend-configured dashboard widgets

The current app remains GetX-based because the existing codebase already uses GetX services, controllers, and bindings. A future Riverpod/GoRouter migration should be done as a separate compatibility phase rather than mixed into this UI upgrade.

## Browser Testing

Start Django on port `8080`, then run from `flutter_offline_billing_app`:

```powershell
cd flutter_offline_billing_app
flutter run -d chrome --web-port 5174
```

Or use VS Code launch configuration:

```text
Flutter Web - Chrome Enterprise
```

No physical device is required. Chrome hot reload works normally.

## Backend API Examples

Current additive endpoint:

```http
GET /api/app/bootstrap/?mode=desktop
Authorization: Bearer <jwt>
```

Existing auth remains:

```http
POST /api/login/
POST /api/auth/token/
POST /api/auth/token/refresh/
```

Future enterprise module endpoints should follow the bootstrap `api` map so Flutter does not hard-code module URLs.

## Enterprise Control Center

The backend now includes `enterprise_control`, an additive Django app that reuses the existing `saas` APGS permission graph instead of creating a duplicate permission system.

Core models:

- `DynamicModule`: no-code module registry for web, Flutter, POS, kiosk, and API surfaces
- `PermissionTemplate`: one-click role presets backed by `saas.PermissionNode`
- `Workspace` and `UserWorkspace`: role/user-specific dashboards, menus, layouts, and landing routes
- `DashboardWidget`: backend-controlled dashboard widgets
- `ThemeConfig`: backend-controlled brand, color, radius, density, typography, and platform overrides
- `DeviceSession`: Flutter/POS/kiosk device tracking
- `AuditLog`: control-center and enterprise API audit trail

Admin control is available in Django admin under Enterprise Control Center models. DRF control APIs are available under:

```http
/api/enterprise/control/modules/
/api/enterprise/control/permissions/
/api/enterprise/control/roles/
/api/enterprise/control/templates/
/api/enterprise/control/workspaces/
/api/enterprise/control/widgets/
/api/enterprise/control/themes/
/api/enterprise/control/user-workspaces/
/api/enterprise/control/user-permission-graphs/
/api/enterprise/control/user-permission-overrides/
/api/enterprise/control/device-sessions/
/api/enterprise/control/audit-logs/
```

Runtime APIs requested by Flutter, POS, kiosk, ecommerce, and dashboards:

```http
GET /api/dashboard/
GET /api/permissions/
GET /api/modules/
GET /api/workspaces/
GET /api/theme/
GET /api/settings/
GET /api/menu/
GET /api/widgets/
GET /api/reports/
GET /api/analytics/
GET /api/notifications/
POST /api/enterprise/devices/register/
```

Realtime channels:

```text
ws/enterprise/permissions/
ws/enterprise/dashboard/
ws/enterprise/modules/
```

The seed command creates enterprise roles such as admin, customer, ecommerce customer, ecommerce vendor, POS user, billing user, CRM user, supplier, agent, staff, accountant, self checkout user, and kiosk user.

```powershell
.\venv\Scripts\python.exe manage.py migrate enterprise_control
.\venv\Scripts\python.exe manage.py seed_enterprise_control
```

## Migration Strategy

1. Keep existing dashboards and module URLs unchanged.
2. Register modules in `DynamicModule` and map them to current web URLs/API namespaces.
3. Seed or create `PermissionNode` keys for platform, module, and action permissions.
4. Assign `RoleTemplate` or `PermissionTemplate` presets to users through admin/API.
5. Let Flutter/POS/kiosk read `/api/dashboard/` and render only backend-approved modules, menus, widgets, theme, and permissions.
6. Use websocket broadcasts to refresh permissions, dashboard widgets, and module availability without app redeploys.

## Compatibility Rules

- Existing Django web dashboard stays at `/accounts/dashboard/`.
- Existing Flutter offline-first billing data remains local and sync-capable.
- Disabled modules are hidden by backend `visible=false` or missing `can_view`.
- Existing app screens are reused before building new native module views.
- The app falls back to local config if Django is unreachable.
- The enterprise API permission middleware only gates `/api/enterprise/` or explicit `X-Enterprise-Control` requests, so legacy APIs keep their current behavior.

## Demotest3 Enterprise Demo

The complete connected demo is seeded with:

```powershell
.\venv\Scripts\python.exe manage.py seed_enterprise_demo_ecosystem
```

Primary login:

```text
Username: Demotest3
Password: Demo@12345
```

Extra demo accounts:

```text
Demotest3POS
Demotest3Supplier
Demotest3Vendor
Demotest3CRM
Demotest3Customer
Demotest3Accountant
Demotest3Kiosk
```

All use password `Demo@12345`.

The seed command is idempotent and offline-safe. It creates:

- Demo users, role templates, permission graphs, and permission overrides
- Admin, POS, supplier, vendor, CRM, customer, accountant, and kiosk workspaces
- Dynamic modules for POS, billing, CRM, ecommerce, supplier, analytics, AI copilot, kiosk, and workspace switching
- Backend dashboard widgets for each workspace
- Glass enterprise theme and platform overrides for POS/kiosk
- Vendor storefront `demotest3`
- Products, inventory, customers, suppliers, orders, invoices, payments, ledger transactions, CRM leads, field agent assignment, and audit timeline

The demo flow is:

1. Admin logs in as `Demotest3`.
2. Django resolves role, permission graph, modules, workspace, theme, menu, widgets, and realtime channels.
3. Flutter loads `/api/dashboard/?platform=desktop`.
4. The same app renders the correct workspace for admin/POS/vendor/supplier/CRM/customer/kiosk users.
5. Admin can change modules, permissions, widgets, and themes in Django admin/API; Flutter refreshes from the backend contract without code changes.
