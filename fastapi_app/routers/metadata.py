from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.metadata.scanner import resolve_model, scan_models, model_metadata
from core.permissions.engine import permission_engine
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/models")
def models(user=Depends(current_access_user)):
    if not permission_engine.can_view_metadata(user=user):
        raise HTTPException(status_code=403, detail="metadata_forbidden")
    return {"count": len(scan_models()), "results": scan_models()}


@router.get("/models/{model_key}")
def model_detail(model_key: str, user=Depends(current_access_user)):
    if not permission_engine.can_view_metadata(user=user):
        raise HTTPException(status_code=403, detail="metadata_forbidden")
    try:
        model = resolve_model(model_key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return model_metadata(model)
