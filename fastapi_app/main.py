from __future__ import annotations

import os
from contextlib import asynccontextmanager

if os.name == "nt":
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("DESKTOP_MODE", "1")
    os.environ.setdefault("LIGHTWEIGHT_DEPLOYMENT", "1")
    os.environ.setdefault("KP_APP_DATA_DIR", os.path.join(BASE_DIR, "_appdata", "Billentra"))
    os.environ.setdefault(
        "KP_DESKTOP_LOG_FILE",
        os.path.join(BASE_DIR, "_appdata", "Billentra", "logs", "desktop.log"),
    )
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "khatapro.settings")

import django

django.setup()

from django.core.cache import cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from fastapi_app.middleware.company import CompanyContextMiddleware
from fastapi_app.routers import (
    auth,
    dashboard,
    dynamic_crud,
    health,
    menu,
    metadata,
    mobile,
    offline_pos,
    permissions,
    plugins,
    reports,
    schemas,
    settings,
    super_app,
    system,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache.set("enterprise_fastapi:started", True, 60)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Billentra Enterprise Dynamic API",
        version="1.0.0",
        description="FastAPI layer for dynamic metadata, CRUD, auth, settings, mobile rendering, and POS sync.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "FASTAPI_CORS_ORIGINS",
            "http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:64562,http://localhost:64562,http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            host.strip()
            for host in os.getenv("FASTAPI_ALLOWED_HOSTS", "127.0.0.1,localhost,*").split(",")
            if host.strip()
        ],
    )
    app.add_middleware(CompanyContextMiddleware)

    app.include_router(health.router)
    app.include_router(settings.router)
    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(permissions.router)
    app.include_router(menu.router)
    app.include_router(dashboard.router)
    app.include_router(reports.router)
    app.include_router(super_app.router)
    app.include_router(schemas.router)
    app.include_router(mobile.router)
    app.include_router(offline_pos.router)
    app.include_router(plugins.router)
    app.include_router(metadata.router)
    app.include_router(dynamic_crud.router)

    @app.get("/", tags=["health"])
    def root():
        return {
            "ok": True,
            "service": "Billentra Enterprise FastAPI",
            "docs": "/docs",
            "login": "/auth/login",
            "app_config": "/api/system/app-config/?platform=app",
        }

    return app


app = create_app()
