# Enterprise Business Operating System Architecture

This layer turns the ERP into a service-oriented, event-driven Business Operating System. Existing ERP modules remain intact; new work should enter through commands, queries, policies, rules, services, repositories, and events.

## Clean Architecture Boundaries

```text
API / Views
  -> validate request only
  -> call CommandBus, QueryBus, services

Application Layer
  -> services, commands, queries, validators, jobs
  -> business orchestration lives here

Domain Layer
  -> command/event/query/policy contracts
  -> no Django ORM access

Repository Layer
  -> database reads/writes only

Infrastructure Layer
  -> Celery, outbox, integrations, websocket, observability

Models
  -> data structure only
```

## Event-Driven Flow

```text
Business Service
  -> EventService.publish()
  -> event_bus.EventOutbox
  -> EnterpriseEventHandler
  -> RuleEngine / AutomationRule
  -> Notifications / Audit / Analytics / AI / WhatsApp / Email / Webhooks
  -> Celery workers for async jobs
```

Standard events:

- `invoice_created`
- `payment_received`
- `purchase_completed`
- `stock_low`
- `user_logged_in`
- `workflow_approved`
- `workflow_transitioned`
- `stock_updated`
- `journal_posted`

## Command / Query Flow

```text
/api/gateway/commands/
  -> serializer validation
  -> CommandBus
  -> PolicyEngine
  -> service/event execution
  -> CommandEnvelope audit trail

/api/gateway/queries/
  -> serializer validation
  -> QueryBus
  -> permission check
  -> metadata-backed read model
  -> cached response when configured
```

## Policy And Rule Engine

Policies are centralized in `platform_core_policies`:

- role policies
- field policies
- tenant policies
- pricing rules
- workflow rules
- tax rules
- approval rules

Rules are centralized in `platform_core_rules`:

- stock below minimum -> purchase suggestion
- invoice above threshold -> approval required
- inactive user threshold -> disable/suspend command
- event conditions -> notification, webhook, WhatsApp, email, AI insight

## API Gateway Structure

```text
api/
  gateway/       command, query, job, policy endpoints
  public/        public API boundary
  internal/      internal service API boundary
  websocket/     websocket routing aggregation
  integrations/  external integration boundary
```

Gateway endpoints:

- `/api/gateway/commands/`
- `/api/gateway/queries/`
- `/api/gateway/jobs/`
- `/api/gateway/policies/evaluate/`
- `/api/gateway/health/`

## Background Processing

Celery queues are modeled through `BackgroundJobDefinition`:

- `notifications`
- `reports`
- `ai`
- `ocr`
- `exports`
- `integrations`
- `default`

Workers should execute long-running jobs only through task definitions, never inside API views.

## Observability

`RequestTracingMiddleware` assigns `X-Trace-Id` and stores request performance into `platform_core_observability_events`.

Observability event types:

- request
- trace
- audit
- performance
- slow query
- health
- error

## Coding Standards

- Views validate and call one application entry point.
- Services own business logic.
- Repositories own database access.
- Events trigger async side effects.
- Models stay structural.
- Commands mutate state.
- Queries return read models.
- Policies decide whether an action is allowed.
- Rules decide what should happen when conditions match.
- Jobs handle slow work outside request/response.

