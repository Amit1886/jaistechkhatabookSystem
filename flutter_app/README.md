# JaisTech ERP Flutter App

Responsive Flutter app for Android, Windows, web, and future iOS.

The app is backend-driven:

- modules are loaded from `GET /api/app/bootstrap/`
- dashboard data is loaded from `GET /api/dashboard/`
- JWT login uses Django only: `POST /api/auth/token/`
- module CRUD screens use each module `api_base`
- offline queue is prepared in `lib/sync/sync_queue.dart`

Run:

```powershell
cd "c:\Users\hp\Pictures\gethub project\jaistechkhatabookSystem\flutter_app"
flutter pub get
flutter run -d chrome
```

Demo login:

- `demo.test3@jaistech.local`
- `Demo@12345`

