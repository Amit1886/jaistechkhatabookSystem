# Integrations Domain

Owns external system communication: WhatsApp, SMS, bank import, external APIs, realtime, Shopify, and courier adapters.

Initial source apps/services:
- `whatsapp`
- `whatsapp_gateway`
- `whatsapp-server`
- `sms_center`
- `bank_import`
- `api_integrations`
- `event_bus`
- `realtime`
- Shopify and courier addon code

Integration code should expose application services and adapters, not leak provider details into business domains.
