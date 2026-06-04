# JaisTech Billing Mobile App (Flutter)

Offline-first billing + accounting app:
- Material 3 UI + GetX
- Local SQLite (`sqflite`) for all data
- Optional sync in the background (every 30s while the app is running)
- No WebView

## Run / Build
Run these commands inside `flutter_offline_billing_app/`:

```bash
flutter pub get
flutter run
flutter build apk --release
```

APK output:
- `build/app/outputs/flutter-apk/app-release.apk`

### Windows note (symlink support)
If the Android build fails with a message about symlink support, enable Developer Mode:
Settings → Privacy & security → For developers → Developer Mode.

## Authentication (Online + Offline)
This app supports two modes:

### 1) Online Login (Django JWT)
- Endpoint: `POST /api/login/`
- Stores `access` + `refresh` in `flutter_secure_storage`

### 2) Offline Signup/Login (No internet required)
- Creates a local user in SQLite with a salted password hash
- Lets you use the full app offline immediately after installation

## Offline database
All modules write to SQLite first. Each row includes:
- `created_at`, `updated_at`
- `is_synced` (0/1) for sync tracking
- `is_deleted` (soft delete)

## Sync (Optional when online)
The sync engine runs every 30 seconds:
- If offline: does nothing
- If online and Settings are configured:
  - Push unsynced rows to `POST /api/v1/mobile/sync/push/`
  - Pull updates from `POST /api/v1/mobile/sync/pull/`
  - Marks local rows `is_synced = 1` after success

### Settings required for sync
In the app: More → Settings
- API Base URL (example: `http://192.168.1.10:8001`)
- `SYNC_API_TOKEN`

Important:
- On a real Android phone, `http://127.0.0.1:8001` points to the **phone**, not your PC.
- If the server is on your PC (same Wi‑Fi), use `http://<PC_LAN_IP>:8001`.
- Android emulator uses `http://10.0.2.2:8001`.

## Django setup (this repo)
Mobile sync endpoints live in `mobileapi/`:
- Push: `POST /api/v1/mobile/sync/push/`
- Pull: `POST /api/v1/mobile/sync/pull/`

Server config:
1) Set `SYNC_API_TOKEN` in Django settings or environment.
2) Apply migrations:
   - `python manage.py migrate`
3) Django admin: `/superadmin/` → Mobile Customers/Products/Invoices/Payments.
