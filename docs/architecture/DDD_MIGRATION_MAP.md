# DDD Migration Map

This map defines where existing Django apps will move over time. It is a planning document, not an immediate code move list.

## Platform

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `accounts` | `apps.platform.identity` | Keep `AUTH_USER_MODEL = accounts.User` until a dedicated migration phase. |
| `users` | `apps.platform.identity` | API/user profile layer; reconcile with `accounts` services. |
| `core_settings` | `apps.platform.settings` | Platform configuration, releases, feature gates. |
| `system_mode` | `apps.platform.system_mode` | Runtime/UI mode policy. |
| `saas` | `apps.platform.settings` or `apps.financial.subscriptions` | Split platform tenancy from billing subscription rules. |

## Financial

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `billing` | `apps.financial.billing` | Keep plan/payment models stable first. |
| `ledger` | `apps.financial.ledger` | Owns journal, posting, accounting reports. |
| `payments` | `apps.financial.payments` | Gateway/transaction abstraction. |
| `wallet` | `apps.financial.wallet` | Wallet balance and withdrawal lifecycle. |
| `subscription` | `apps.financial.subscriptions` | Merge with billing only after entitlement model is stable. |

## Inventory

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `products` | `apps.inventory.products` | Candidate canonical product catalog. |
| `warehouse` | `apps.inventory.warehouses` | Candidate canonical warehouse/staff assignment. |
| `procurement` | `apps.inventory.procurement` | Supplier pricing and purchase automation. |
| `commerce.Product/Warehouse/Inventory` | `apps.inventory.*` | Do not delete until data reconciliation and service shims exist. |

## Commerce

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `commerce` | `apps.commerce.orders`, `apps.commerce.invoices`, `apps.inventory.*` | Split by responsibility, starting with services. |
| `orders` | `apps.commerce.orders` | Candidate canonical order API/service layer. |
| `pos` | `apps.commerce.pos` | POS interface to order/invoice services. |
| `storefront` | `apps.commerce.storefront` | Multi-vendor customer storefront. |
| `vendors` | `apps.commerce.vendors` | Vendor/account/store settings. |

## CRM

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `khataapp.Party` | `apps.crm.parties` | Currently central to customer/supplier identity. Move last. |
| `khataapp.Transaction` | `apps.financial.ledger` or `apps.crm.parties` | Decide by accounting ownership. |
| `crm` | `apps.crm.customer_service` | CRM API and activity tracking. |
| `leads` | `apps.crm.leads` | Lead capture/assignment. |
| `portal` | `apps.crm.portal` | Customer/supplier self-service. |
| `marketing` | `apps.crm.marketing` | Campaigns and segments. |

## Analytics

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `reports` | `apps.analytics.reports` | Reporting views and exports. |
| `analytics` | `apps.analytics.dashboards` | Metrics/projections. |
| `smart_bi` | `apps.analytics.smart_bi` | BI query/explanation layer. |
| `performance` | `apps.analytics.performance` | System/business performance metrics. |

## AI

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `ai_engine` | `apps.ai.engine` | Shared AI orchestration. |
| `ai_ocr` | `apps.ai.ocr` | OCR workflows. |
| `ai_insights` | `apps.ai.insights` | Business insight generation. |
| `fraud_detection` | `apps.ai.fraud_detection` | Risk scoring. |
| `voice` | `apps.ai.voice` | Voice command interfaces. |
| `chatbot` | `apps.ai.chatbot` | Chatbot flows and replies. |

## Integrations

| Current app/module | Target bounded context | Notes |
| --- | --- | --- |
| `whatsapp`, `whatsapp_gateway`, `whatsapp-server` | `apps.integrations.whatsapp` | Provider and gateway consolidation. |
| `sms_center` | `apps.integrations.sms` | SMS provider abstraction. |
| `bank_import` | `apps.integrations.bank_import` | Bank ingestion. |
| `api_integrations` | `apps.integrations.api_integrations` | External API connections. |
| `event_bus`, `realtime` | `apps.integrations.realtime` | Event/websocket infrastructure. |
| Shopify/courier addons | `apps.integrations.shopify`, `apps.integrations.courier` | Keep provider adapters separate. |

## Migration Order

1. Extract services from existing apps into domain packages.
2. Update old modules to import from new services.
3. Add tests around service behavior.
4. Split views/serializers after service stability.
5. Move models only with explicit migration design.
6. Remove compatibility shims only after all imports are updated.
