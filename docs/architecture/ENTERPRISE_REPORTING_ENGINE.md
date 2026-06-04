# Enterprise Reporting And Analytics Engine

This engine fixes reporting by creating one backend/frontend contract for all modules.

## Backend Architecture

```text
ReportTemplate
  -> ReportEngine
  -> ReportFilterEngine
  -> ReportRepository
  -> ReportRun
  -> ReportExportEngine
  -> CSV / Excel / PDF / Print
```

API base:

`/api/v1/platform/reports/`

Important endpoints:

- `templates/`
- `templates/{id}/run/`
- `templates/{id}/export/`
- `run/<report_key>/`
- `export/<report_key>/`
- `dashboard/`
- `seed/`

## Supported Domains

- sales
- purchase
- inventory
- GST
- accounting
- CRM
- warehouse
- manufacturing
- POS
- payments
- subscriptions

## Dynamic Filter Engine

Supported filters:

- date range
- tenant
- branch
- role
- warehouse
- product
- GST
- status
- text search

Each report template declares a `query_spec.filter_fields` map so frontend filters and backend query fields stay aligned.

## Frontend Reporting Repair

New shared frontend reporting components:

```text
frontend/src/shared/reports/
  ReportViewer.jsx
  ReportFilterPanel.jsx
  ReportChart.jsx
```

These fix:

- empty charts with visible empty state
- API mismatch with one `reportingApi`
- date filter normalization
- pagination controls
- export actions
- consistent table rendering

## Analytics Engine

`AnalyticsEngine` powers:

- KPI dashboards
- sales trends
- inventory totals
- stock analytics
- customer/payment/report extensions

## Export System

Supported:

- CSV
- Excel-compatible export
- print HTML
- PDF response placeholder for production renderer integration

For production PDF, plug WeasyPrint, wkhtmltopdf, or a cloud PDF renderer behind `ReportExportEngine`.

## Realtime Dashboard Strategy

Realtime counters are stored in `RealtimeDashboardCounter` and should be updated by event handlers:

- invoice created
- payment received
- stock updated
- subscription changed
- workflow approved

The frontend can subscribe to the existing platform WebSocket channel and refresh report widgets by key.

