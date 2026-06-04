# Unified Multi-Interface Mode Switching Deployment

This project runs as one Django backend and one optional React frontend.

## 1) Backend setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8080
```

## 2) Frontend setup (single React app)

```bash
cd frontend
npm install
npm run dev
```

## 3) API endpoints

- `GET /api/system-mode/`
- `PATCH /api/system-mode/` (admin)
- `POST /api/change-mode/` (admin)
- `GET /api/current-mode/`

## 4) WebSocket endpoints

- `ws://<host>/ws/system-mode/` (dedicated system mode channel)
- `ws://<host>/ws/realtime/system_mode/` (existing realtime stream channel)

When mode is switched, backend emits `system.mode.changed` and frontend reloads instantly.

## 5) Mode resolution behavior

- Explicit modes: `POS`, `TABLET`, `MOBILE`, `DESKTOP`, `ADMIN_SUPER`
- `AUTO`: resolved by viewport width or user-agent.

## 6) Production notes

1. Use PostgreSQL for primary DB.
2. Use Redis for Channels and Celery broker/result.
3. Set `USE_REDIS=True` in `.env`.
4. Run ASGI server (e.g. `daphne` or `uvicorn`) for websockets.
5. Build frontend static assets and serve via CDN or reverse proxy.
