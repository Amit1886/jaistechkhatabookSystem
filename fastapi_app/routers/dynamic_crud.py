from django.core.exceptions import ObjectDoesNotExist, ValidationError

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from core.dynamic_api.service import CRUDService
from core.metadata.scanner import resolve_model
from core.permissions.engine import permission_engine
from fastapi_app.dependencies.auth import company_context, current_access_user
from fastapi_app.schemas.common import CRUDPayload


router = APIRouter(prefix="/crud", tags=["dynamic-crud"])


def _service_or_404(model_key: str) -> CRUDService:
    try:
        return CRUDService(resolve_model(model_key))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{model_key}")
def list_records(
    request: Request,
    model_key: str,
    q: str = Query(default=""),
    ordering: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user=Depends(current_access_user),
    context: dict[str, str] = Depends(company_context),
):
    service = _service_or_404(model_key)
    if not permission_engine.can_model_action(user=user, model=service.model, action="view"):
        raise HTTPException(status_code=403, detail="view_forbidden")
    return service.list(
        user=user,
        search=q,
        ordering=ordering,
        filters=_filters_from_query(service, request),
        limit=limit,
        offset=offset,
        company_id=context.get("company_id", ""),
    )


def _filters_from_query(service: CRUDService, request: Request) -> dict:
    reserved = {"q", "ordering", "limit", "offset"}
    allowed = set(service.meta.get("filter_fields") or [])
    filters = {}
    for key, value in request.query_params.multi_items():
        if key in reserved or key not in allowed or value in ("", None):
            continue
        filters[key] = value
    return filters


@router.get("/{model_key}/{pk}")
def detail_record(model_key: str, pk: str, user=Depends(current_access_user)):
    service = _service_or_404(model_key)
    if not permission_engine.can_model_action(user=user, model=service.model, action="view"):
        raise HTTPException(status_code=403, detail="view_forbidden")
    try:
        return service.serialize(service.get(pk))
    except ObjectDoesNotExist as exc:
        raise HTTPException(status_code=404, detail="not_found") from exc


@router.post("/{model_key}")
def create_record(model_key: str, payload: CRUDPayload, user=Depends(current_access_user)):
    service = _service_or_404(model_key)
    if not permission_engine.can_model_action(user=user, model=service.model, action="add"):
        raise HTTPException(status_code=403, detail="add_forbidden")
    try:
        return service.serialize(service.create(data=payload.data, user=user))
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=getattr(exc, "message_dict", str(exc))) from exc


@router.patch("/{model_key}/{pk}")
def update_record(model_key: str, pk: str, payload: CRUDPayload, user=Depends(current_access_user)):
    service = _service_or_404(model_key)
    if not permission_engine.can_model_action(user=user, model=service.model, action="change"):
        raise HTTPException(status_code=403, detail="change_forbidden")
    try:
        return service.serialize(service.update(pk=pk, data=payload.data, partial=True, user=user))
    except ObjectDoesNotExist as exc:
        raise HTTPException(status_code=404, detail="not_found") from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=getattr(exc, "message_dict", str(exc))) from exc


@router.delete("/{model_key}/{pk}")
def delete_record(model_key: str, pk: str, user=Depends(current_access_user)):
    service = _service_or_404(model_key)
    if not permission_engine.can_model_action(user=user, model=service.model, action="delete"):
        raise HTTPException(status_code=403, detail="delete_forbidden")
    try:
        return service.delete(pk=pk)
    except ObjectDoesNotExist as exc:
        raise HTTPException(status_code=404, detail="not_found") from exc
