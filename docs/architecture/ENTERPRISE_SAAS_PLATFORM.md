# Enterprise SaaS Ecosystem Platform

This layer upgrades the ERP into a cloud-ready SaaS ecosystem while keeping the existing ERP running. It reuses the identity tenant engine and adds white-label, reseller, franchise, subscription, usage, and operations primitives.

## SaaS Architecture

```text
Tenant Identity
  -> Company / Branch
  -> WhiteLabelProfile / TenantDomain
  -> SaaSPlan / TenantSubscription
  -> UsageMetric / UsageRecord
  -> SaaSInvoice / PaymentRetry
  -> FeatureToggle / DynamicModule / MenuItem
```

API base:

`/api/v1/platform/saas/`

Core endpoints:

- `provision/`
- `meter/`
- `white-label/`
- `domains/`
- `plans/`
- `subscriptions/`
- `usage-metrics/`
- `usage-records/`
- `invoices/generate/`
- `partners/`
- `routes/`
- `salesman-tracking/`
- `van-sales/`
- `deliveries/`
- `warehouse-routes/`
- `forecasts/`

## White Label Engine

Each tenant can customize:

- logo
- brand name
- primary/secondary/accent colors
- custom domain
- sidebar configuration
- enabled modules
- invoice template
- permission template

## Distribution Ecosystem

Supported hierarchy:

```text
Company
  -> Super Stockist
  -> Distributor
  -> Dealer
  -> Retailer
  -> Customer
```

All entities use `EcosystemPartner` with parent-child relationships, partner type, territory, commission rules, and credit limits.

## Tenant Provisioning Flow

```text
POST /api/v1/platform/saas/provision/
  -> create Tenant
  -> create Company
  -> create Branch
  -> create owner membership
  -> setup default roles
  -> setup default permissions
  -> setup branding
  -> setup default modules/menus/features
  -> create subscription when plan is supplied
```

## Billing Engine

The SaaS billing layer supports:

- recurring subscription plans
- trial periods
- monthly/yearly interval pricing
- usage metering
- usage billing
- invoice automation
- payment retry schedule
- subscription lifecycle states

## Enterprise Operations

Operations primitives:

- route management
- salesman tracking
- van sales sessions
- delivery assignments
- warehouse routing
- procurement automation hooks
- inventory forecasting models

## Tenant Isolation

Every SaaS ecosystem record is tenant-scoped. Runtime requests should resolve `request.identity_tenant` through existing tenant middleware and use tenant-filtered APIs/services.

## Production Cloud Topology

```text
CDN / WAF
  -> Load Balancer
  -> Django API Pods
  -> Celery Worker Pods
  -> Celery Beat Pod
  -> Redis
  -> PostgreSQL
  -> Object Storage
  -> Monitoring Stack
```

## Scaling Strategy

- Scale API pods horizontally.
- Scale workers by queue: notifications, reports, ai, ocr, exports, integrations.
- Use Redis for cache, locks, Celery broker.
- Move SQLite desktop/local installs to PostgreSQL for cloud SaaS.
- Use object storage for logos, invoices, exports, OCR assets.
- Use read replicas for analytics/reporting workloads.
- Use outbox/event bus for cross-module async processing.

