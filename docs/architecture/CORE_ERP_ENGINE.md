# Core Enterprise ERP Engine

This engine is additive and metadata-driven. It does not replace current ERP modules; it provides a platform foundation that existing and future apps can bind to gradually.

## Runtime Shape

`apps.platform.core` contains the dynamic ERP platform backbone:

- Metadata engine: modules, industry blueprints, feature toggles
- UX engine: menus, dynamic sidebar, forms, dashboards
- Process engine: workflows, transitions, automation rules
- Event engine: event subscriptions and durable outbox publishing
- Reporting engine: report definitions and dashboard widgets
- Inventory foundation: products, variants, attributes, warehouses, stock ledger, transfers, procurement, BOM
- Accounting foundation: chart of accounts, journals, journal lines, GST ledger

## API Surface

Base path:

`/api/v1/platform/core/`

Important endpoints:

- `sidebar/`: resolves tenant-aware, permission-aware dynamic sidebar
- `events/publish/`: publishes an event into the ERP event bus
- `dashboard/`: platform engine health summary
- `forms/schema/<key>/`: resolves dynamic form schema
- `workflows/transition/`: executes workflow transition with permission check and event emission

## Event Flow

Business action -> service layer -> event service -> event outbox -> subscriptions/automation -> notifications/audit/analytics/workflows.

Standard events include:

- `invoice_created`
- `payment_received`
- `stock_updated`
- `journal_posted`
- `workflow_transitioned`

## Tenant Flow

All production records are tenant-scoped where business isolation matters. The platform reuses `apps.platform.identity` for tenants, companies, branches, and permissions.

Request middleware resolves `request.identity_tenant`; services and APIs use that tenant for filtering and event payloads.

## Extension Strategy

Existing modules should move gradually:

- Current sidebar links can become `MenuItem` rows.
- Current forms can become `FormDefinition` + `FormFieldDefinition`.
- Current business processes can become `WorkflowDefinition` + `WorkflowTransition`.
- Current reports can become `ReportDefinition` and dashboard widgets.
- Existing inventory/accounting modules can emit events into the platform bus before full migration.

## Safety Rules

- Existing apps remain enabled.
- No existing tables were renamed.
- No existing business logic was removed.
- New tables use `platform_core_*`, `platform_inventory_*`, and `platform_financial_*` prefixes.
- Strict workflow/permission behavior is opt-in through configured permissions and transitions.

