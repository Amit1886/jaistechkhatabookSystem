from __future__ import annotations

from fastapi import APIRouter, Request

from core.settings_engine.service import settings_service


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public")
def public_settings(request: Request):
    return settings_service.get_public_settings(request=request)


@router.get("/mobile-config")
def mobile_config(request: Request):
    return settings_service.mobile_auto_config(request=request)
