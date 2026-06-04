# Unified ERP UI Standard

The ERP must feel like one Business Operating System, not separate modules. Every module should use the shared UI system and the same workflow language.

## Canonical Frontend Structure

```text
frontend/src/shared/
  components/
    Button.jsx
    Input.jsx
    Card.jsx
    DataTable.jsx
    FilterBar.jsx
    Modal.jsx
    Tabs.jsx
    KPIWidget.jsx
    WorkflowBadge.jsx
    ApprovalCard.jsx
  workflow/
    workflowStates.js
  search/
    searchRegistry.js
    useGlobalSearch.js
  notifications/
    notificationRegistry.js
  dashboard/
    widgetRegistry.js
  layout/
    UnifiedModuleShell.jsx
  standards/
    moduleStandards.js
```

## Global Workflow Standard

All ERP modules use the same states:

```text
Draft -> Review -> Approval -> Completed -> Cancelled
```

Examples:

- POS bill: Draft -> Completed or Cancelled
- Purchase order: Draft -> Review -> Approval -> Completed
- Stock transfer: Draft -> Review -> Approval -> Completed
- Payment voucher: Draft -> Approval -> Completed
- Manufacturing order: Draft -> Review -> Approval -> Completed

## Shared Components Rule

All modules must use:

- `Button` for commands
- `Input` for form fields
- `Card` for grouped content
- `DataTable` for lists
- `FilterBar` for filters
- `Modal` for dialogs
- `Tabs` for workspaces
- `KPIWidget` for dashboard KPIs
- `WorkflowBadge` for status
- `ApprovalCard` for approvals
- `UnifiedModuleShell` for module pages

No module should create its own button/table/modal/card styling.

## Global Search

Search is centralized through:

- `SEARCH_SCOPES`
- `useGlobalSearch`
- Gateway query endpoint

Default scopes:

- invoices
- customers
- products
- payments
- reports
- ledgers
- orders

## Global Notification System

Notification categories:

- toast
- approval
- stock
- GST
- payment
- workflow

All modules should emit events and let the unified notification center render alerts.

## Dashboard Standard

Dashboards are role-based and widget-driven:

- admin
- manager
- cashier
- accountant
- warehouse
- salesman

Widgets are declared in `widgetRegistry.js`, not hardcoded into module pages.

## Module Migration Rule

Each module should migrate to this shape:

```text
Module API -> metadata/query/service layer
Module UI -> UnifiedModuleShell
List screen -> DataTable + FilterBar
Detail screen -> Card + WorkflowBadge
Edit screen -> DynamicFormBuilder/Input/Button
Approval screen -> ApprovalCard
Notifications -> notificationRegistry
Search -> useGlobalSearch
Dashboard -> widgetRegistry
```

## Design Language

- Sidebar, topbar, tabs, forms, cards, tables, filters, modals, reports, dashboards, alerts, workflows, approvals, and notifications must use the shared design system.
- Keep dense enterprise layouts for operations-heavy screens.
- Avoid isolated module-specific visual systems.
- Prefer metadata-driven rendering over duplicated page logic.
- Keep business logic out of components.

