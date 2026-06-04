# Enterprise Dynamic Flutter - Phase 3

## Completed

- Added `DynamicRuntimeService` for runtime metadata, CRUD, and local cache.
- Flutter app config now caches backend bootstrap payloads for faster startup and offline fallback.
- Dynamic module screens now load Django model metadata from backend:
  - `module.settings.model_key`
  - `/fastapi/mobile/screens/{model_key}`
  - `/fastapi/crud/{model_key}`
- Added runtime table/form renderer with:
  - search
  - pagination
  - skeleton loading
  - optimistic create/update refresh
  - dynamic columns
  - dynamic forms
- Extended form renderer mappings:
  - `text` -> `TextFormField`
  - `number` / `decimal` -> numeric input
  - `date_picker` -> date picker
  - `relation_dropdown` -> relation id field
  - `file_picker` -> upload placeholder
  - `json_editor` -> multi-line JSON editor
  - `switch` -> `SwitchListTile`
  - `select` -> dropdown
- Flutter sidebar now renders backend `sidebar` config with:
  - nested menus
  - icons
  - badges
  - permission-filtered items from backend
- Offline sync queue is now persistent through `SharedPreferences`.
- Seeded module-to-model runtime hints:
  - POS -> `orders.order`
  - Orders -> `orders.order`
  - Billing -> `billing.billinginvoice`
  - Products -> `products.product`
  - CRM -> `leads.lead`

## Runtime Flow

```text
Admin creates module/button/menu/layout
  -> Django stores DynamicModule/DynamicButton/DynamicMenuItem
  -> /api/dashboard returns app shell config
  -> Flutter parses modules/sidebar/buttons/theme/widgets
  -> module.settings.model_key selects metadata screen
  -> /fastapi/mobile/screens/{model_key}
  -> /fastapi/crud/{model_key}
  -> generated table/form renders automatically
```

## Verification

```text
python manage.py check -> OK
python -m py_compile enterprise_control/management/commands/seed_enterprise_ui.py -> OK
module settings smoke test -> POS/Orders/Billing/Products/CRM model hints present
```

Flutter analyzer still times out in this shell, so SDK-level analysis must be run from a local terminal where `flutter analyze --no-pub` returns normally.
