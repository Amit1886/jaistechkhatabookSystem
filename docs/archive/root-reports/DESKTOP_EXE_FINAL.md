# Desktop EXE (Hybrid Offline + Cloud) — Final Guide

## 1) Local run (browser)

### Option A (recommended)
- Run: `start_django_dev.bat`

### Option B
- Run: `start_django.bat`

These scripts set safe local defaults:
- `DEBUG=True`
- `SECURE_SSL_REDIRECT=False` (prevents `http://127.0.0.1:8000` redirecting to `https://...` which causes timeouts)

Open:
- `http://127.0.0.1:8000/accounts/login/`

If Chrome still shows timeout due to cached 301/HSTS:
- Use Incognito once, or clear site data for `127.0.0.1`.


## 2) Desktop mode (Python)

Run:
- `.\venv\Scripts\python.exe run_desktop.py`

What it does:
- Uses local SQLite in `%LOCALAPPDATA%\JaisTechKhataBook\db.sqlite3`
- Runs migrations automatically
- Starts background sync thread (every 30s) when cloud is configured
- Checks for updates (if cloud configured) and prompts download
- Shows a native splash (logo highlight) immediately
- Starts local server (defaults to `127.0.0.1:<auto>`; uses `DESKTOP_PORT` if available otherwise finds a free port)
- Opens inside the desktop app window (URL hidden): splash -> login automatically

Optional overrides (in `%LOCALAPPDATA%\JaisTechKhataBook\.env`):
- `DESKTOP_HOST=127.0.0.1`
- `DESKTOP_PORT=8000`
- `DESKTOP_UI=browser` (fallback to external browser)

Logs:
- `%LOCALAPPDATA%\JaisTechKhataBook\logs\desktop.log`

Backup:
- `%LOCALAPPDATA%\JaisTechKhataBook\backups\db-YYYYMMDD-HHMMSS.sqlite3`

Static/CSS/JS note:
- Desktop copies packaged `static/` into `%LOCALAPPDATA%\JaisTechKhataBook\static` and serves it locally.
- If you update the EXE and the UI looks “old” (cached CSS/JS), delete `%LOCALAPPDATA%\JaisTechKhataBook\static` and reopen the app (it will re-copy fresh assets).


## 3) Desktop EXE build (PyInstaller)

Run (PowerShell):
- `.\build_desktop.ps1`

Output:
- Bundle folder: `dist\JaisTechKhataBookDesktop\`
- EXE inside: `dist\JaisTechKhataBookDesktop\JaisTechKhataBookDesktop.exe`

Note:
- Use `desktop_app.spec` build (recommended). It bundles project assets + Django admin assets more reliably than `pyinstaller --onefile run_desktop.py`.
- This build uses a custom PyInstaller hook (`pyinstaller_hooks\hook-django.py`) to avoid shipping readable Django `.py` sources as loose files while keeping templates/static/locale data intact.
- Do **not** run `dist\JaisTechKhataBookDesktop.exe` (if it exists). Always run the EXE inside the bundle folder and keep the `_internal\` folder next to it.
- The EXE is built with `uac_admin=True`, so Windows will prompt for "Run as administrator" (UAC) on launch.
- On first launch, it creates a Desktop shortcut: `JaisTech KhataBook.lnk`
- The EXE icon is set to: `static\img\favicon.ico` (shows on Desktop/taskbar instead of Python icon)


## 4) Required ENV (.env)

### Always
- `DJANGO_SECRET_KEY=...` (use a long random value in production)
- `DEBUG=False` (default)

### Desktop version display (UI footer + landing)
- `DESKTOP_APP_VERSION=1.0.2`

### Hybrid sync (Desktop -> Cloud)
- Desktop machine `.env`:
  - `CLOUD_API_URL=https://your-cloud-domain.com`
  - `CLOUD_API_TOKEN=YOUR_SHARED_TOKEN`
- Cloud server `.env`:
  - `SYNC_API_TOKEN=YOUR_SHARED_TOKEN`

Sync behavior (Desktop -> Cloud):
- Desktop queues *all* model saves/deletes into `commerce.SyncQueue` (desktop-only)
- Desktop pushes to: `POST /api/v1/sync/push/` (batch)
- Cloud stores every event in: `commerce.SyncedObject` (Admin: **Commerce → Synced objects**)
- Cloud also applies core models into real tables (idempotent via `commerce.SyncMapping`):
  - `accounts.User`, `khataapp.Party`, `khataapp.Transaction`

### Desktop updates (Cloud -> Desktop)
- Cloud server `.env` (optional):
  - `DESKTOP_UPDATE_TOKEN=YOUR_SHARED_TOKEN`
  - If empty, it falls back to `SYNC_API_TOKEN`.


## 5) Cloud admin: upload EXE + publish version

After migrations:
- `core_settings -> Desktop Releases` (singleton row)
- Upload `windows_exe`
- Set `version`
- Set `is_published=True`

Download test:
- Admin button in that page uses `/api/v1/desktop/releases/download/` (staff session allowed).


## 6) Desktop auto-update behavior

On startup (only when online):
- Calls `GET /api/v1/desktop/releases/latest/` with header `Authorization: Token <CLOUD_API_TOKEN>`
- If server returns a newer `version`, shows a Windows popup asking to download
- Downloads to:
  - `%LOCALAPPDATA%\JaisTechKhataBook\updates\<download_filename>` (usually `.zip`)
- Verifies `sha256` (if provided by server)
- If the download is a ZIP, it extracts to:
  - `%LOCALAPPDATA%\JaisTechKhataBook\updates\JaisTechKhataBookDesktop-<version>\`
- Then it prompts to restart (or auto-restarts if you set `DESKTOP_AUTO_UPDATE=True` in the desktop `.env`).


## 7) Print Templates (A4 + POS 80mm) â€” Admin + User

### 7.1 Seed professional templates (recommended)

Run (creates 6 templates: Invoice/Order Slip/Receipt in A4 + POS-80):
- `python manage.py seed_pro_print_templates`

Overwrite existing Pro templates (refresh latest HTML/JSON):
- `python manage.py seed_pro_print_templates --overwrite`

Notes:
- Templates are created in Django Admin â†’ `printer_config â†’ Print templates`.
- These Pro templates are **not** set as default (`is_default=False`) because default selection depends on your app flow (A4 vs POS).


### 7.2 User-side render endpoints (these reflect admin template changes)

Render (recommended user-side flow):
- POST ` /api/v1/printers/engine/render/ `
  - body keys: `document_type`, `template_id` (optional), `user_template_id` (optional), `print_mode` (`desktop` / `pos`), `source_model`, `source_id`, `payload`

Render using a PrinterConfig (POS client flow):
- POST ` /api/v1/printers/configs/<printer_id>/render/ `
  - body can include: `document_type`, `template_id`, `user_template_id`, `print_mode`, `source_model`, `source_id`, `payload`


### 7.3 Recommended user custom fields (for QR/WhatsApp/Map/Social/Bank)

Put this inside `UserPrintTemplate.custom_fields` (or send in `payload.custom`):
```json
{
  "website_link": "https://yourdomain.com",
  "whatsapp_number": "+91 90000 00000",
  "map_query": "Your Shop Address, City",
  "social_links": {
    "instagram": "https://instagram.com/yourhandle",
    "facebook": "https://facebook.com/yourpage",
    "youtube": "https://youtube.com/@yourchannel"
  },
  "bank_details": {
    "account_name": "Your Company Name",
    "account_no": "123456789012",
    "ifsc": "SBIN0000123",
    "upi_id": "yourupi@upi"
  },
  "terms_conditions": "Goods once sold will not be taken back. Subject to jurisdiction."
}
```

Status badges:
- Invoice/Order Slip uses `document.status` values: `paid` / `unpaid` / `pending` / `hold`
- Receipt uses `payment.status` (fallback `document.status`): `success` / `failed` / `pending` / `hold`


### 7.4 Assign Pro templates to user (simple)

In Django Admin â†’ `printer_config â†’ User print templates`, create:
- A4 invoice: `document_type=invoice`, `print_mode=desktop`, `paper_size=a4`, select template slug `invoice-pro-a4`
- POS invoice: `document_type=invoice`, `print_mode=pos`, `paper_size=pos_80`, select template slug `invoice-pro-pos-80`
- Receipt similarly: `receipt-pro-a4` / `receipt-pro-pos-80`
- Order slip similarly: `order-slip-pro-a4` / `order-slip-pro-pos-80`

Then use `make_default` action (API) or mark one as `is_default=True` per `(document_type, print_mode)` for that user.
