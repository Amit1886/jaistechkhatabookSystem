# Enterprise Frontend Business OS

The frontend is extended as a hybrid AdminLTE-compatible React workspace. Existing Django/AdminLTE screens remain unchanged; the new React Business OS shell is opt-in with `?enterprise=1`.

## Frontend Structure

```text
frontend/src/
  engine/
    LayoutEngine.jsx
    EnterpriseUIEngine.jsx
  components/enterprise/
    DesignSystem.jsx
    DynamicSidebar.jsx
    EnterpriseTopbar.jsx
    CommandPalette.jsx
    DashboardBuilder.jsx
    DynamicFormBuilder.jsx
    DynamicTable.jsx
    NotificationCenter.jsx
    TabbedWorkspace.jsx
  services/
    enterpriseApi.js
  realtime/
    enterpriseSocket.js
  store/
    erpUiStore.js
  hooks/
    useEnterpriseMetadata.js
```

## Metadata Driven Rendering

The UI reads platform metadata from backend endpoints:

- `/api/v1/platform/core/sidebar/`
- `/api/v1/platform/core/dashboard/`
- `/api/v1/platform/core/forms/schema/<key>/`
- `/api/v1/platform/identity/notifications/`
- `/api/v1/platform/identity/activity-sessions/dashboard/`

## UX Systems

- Dynamic sidebar and menus
- Role and permission aware metadata rendering
- Tenant-ready branding state
- Dashboard builder foundation
- Widget system
- Dynamic forms
- Dynamic tables
- Global command palette
- Notification center
- Activity and workflow-ready panels
- Pinned modules
- Tabbed workspace
- Split screen mode
- Breadcrumb/topbar shell
- Realtime status indicators

## Realtime Flow

```text
WebSocket /ws/platform/core/events/
  -> enterpriseSocket
  -> erpUiStore
  -> notification/activity/widgets update
```

## Compatibility

- Existing AdminLTE/Django templates are not replaced.
- New styles are namespaced under `enterprise-*`, `erp-*`, and `dynamic-*`.
- Existing frontend layouts continue to render normally.
- Enterprise workspace can be tested by opening the React frontend with `?enterprise=1`.

## Standards

- API calls live in service modules.
- UI state lives in store modules.
- Engine components orchestrate layout only.
- Components are reusable and metadata-driven.
- No business logic is placed in visual components.
- Responsive behavior supports desktop, tablet POS, and mobile admin layouts.

