from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.dynamic_api.schemas import schema_factory
from core.metadata.scanner import resolve_model, scan_models
from core.permissions.engine import permission_engine
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/schemas", tags=["dynamic-schemas"])


@router.get("/")
def all_schemas(user=Depends(current_access_user)):
    if not permission_engine.can_view_metadata(user=user):
        raise HTTPException(status_code=403, detail="schemas_forbidden")
    results = []
    for meta in scan_models():
        try:
            model = resolve_model(meta["key"])
            results.append(schema_factory.schema_payload(model))
        except LookupError:
            continue
    return {"count": len(results), "results": results}


@router.get("/{model_key}")
def model_schemas(model_key: str, user=Depends(current_access_user)):
    if not permission_engine.can_view_metadata(user=user):
        raise HTTPException(status_code=403, detail="schemas_forbidden")
    try:
        model = resolve_model(model_key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return schema_factory.schema_payload(model)
