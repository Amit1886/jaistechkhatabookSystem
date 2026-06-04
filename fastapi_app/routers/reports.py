from fastapi import APIRouter, Depends, HTTPException

from core.dynamic_api.service import CRUDService
from core.metadata.scanner import resolve_model, scan_models
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/reports", tags=["dynamic-reports"])


@router.get("/catalog")
def report_catalog(user=Depends(current_access_user)):
    candidates = [
        meta
        for meta in scan_models()
        if any(word in meta["key"] for word in ["report", "invoice", "order", "payment", "transaction", "ledger"])
    ]
    return {
        "count": len(candidates),
        "results": [
            {
                "key": meta["key"],
                "label": meta["label_plural"],
                "columns": [field["name"] for field in meta["fields"] if not field["sensitive"]][:12],
                "filters": meta["filter_fields"][:10],
                "export_formats": ["json", "xlsx", "pdf"],
            }
            for meta in candidates
        ],
    }


@router.get("/{model_key}/preview")
def report_preview(model_key: str, limit: int = 25, user=Depends(current_access_user)):
    try:
        service = CRUDService(resolve_model(model_key))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return service.list(user=user, limit=min(max(limit, 1), 100), offset=0)


@router.post("/{model_key}/export")
def report_export(model_key: str, export_format: str = "json", user=Depends(current_access_user)):
    if export_format not in {"json", "xlsx", "pdf"}:
        raise HTTPException(status_code=400, detail="unsupported_export_format")
    return {
        "ok": True,
        "status": "queued",
        "model": model_key,
        "format": export_format,
        "message": "Export job accepted. Connect this endpoint to Celery for production file generation.",
    }
