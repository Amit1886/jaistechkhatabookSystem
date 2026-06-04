from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from django.utils import timezone

from core.dynamic_api.service import CRUDService
from core.metadata.scanner import resolve_model
from core.models import OfflineSyncBatch, OfflineSyncConflict, OfflineSyncOperation
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/offline", tags=["offline-pos-sync"])


class SyncOperation(BaseModel):
    client_id: str
    model: str
    operation: str
    pk: str | None = None
    data: dict = Field(default_factory=dict)
    client_timestamp: str | None = None


class SyncPushRequest(BaseModel):
    device_id: str
    operations: list[SyncOperation] = Field(default_factory=list)


@router.get("/pull")
def pull(models: str = "commerce.product,khataapp.party,commerce.order", limit: int = 100, user=Depends(current_access_user)):
    payload = {}
    for key in [item.strip() for item in models.split(",") if item.strip()]:
        try:
            service = CRUDService(resolve_model(key))
            payload[key] = service.list(user=user, limit=min(max(limit, 1), 500), offset=0)["results"]
        except Exception as exc:
            payload[key] = {"error": str(exc)}
    return {"ok": True, "server_policy": "server_timestamp_wins", "data": payload}


@router.post("/push")
def push(payload: SyncPushRequest, user=Depends(current_access_user)):
    batch = OfflineSyncBatch.objects.create(
        device_id=payload.device_id,
        user=user,
        operation_count=len(payload.operations),
        status="processing",
    )
    results = []
    for op in payload.operations:
        operation_row = OfflineSyncOperation.objects.create(
            batch=batch,
            client_id=op.client_id,
            model_key=op.model,
            operation=op.operation,
            object_pk=op.pk or "",
            payload=op.data,
            client_timestamp=op.client_timestamp or "",
        )
        try:
            service = CRUDService(resolve_model(op.model))
            if op.operation == "create":
                obj = service.create(data=op.data, user=user)
                result = {"client_id": op.client_id, "status": "created", "server_pk": str(obj.pk)}
            elif op.operation == "update" and op.pk:
                obj = service.update(pk=op.pk, data=op.data, user=user)
                result = {"client_id": op.client_id, "status": "updated", "server_pk": str(obj.pk)}
            elif op.operation == "delete" and op.pk:
                service.delete(pk=op.pk)
                result = {"client_id": op.client_id, "status": "deleted", "server_pk": op.pk}
            else:
                result = {"client_id": op.client_id, "status": "skipped", "error": "invalid_operation"}
            operation_row.status = result["status"]
            operation_row.result = result
            operation_row.object_pk = str(result.get("server_pk") or operation_row.object_pk)
        except Exception as exc:
            result = {"client_id": op.client_id, "status": "error", "error": str(exc)}
            operation_row.status = "error"
            operation_row.error = str(exc)
            if op.pk:
                OfflineSyncConflict.objects.create(
                    operation=operation_row,
                    model_key=op.model,
                    object_pk=op.pk,
                    client_payload=op.data,
                    policy="manual_review",
                )
        operation_row.processed_at = timezone.now()
        operation_row.save(update_fields=["status", "result", "error", "object_pk", "processed_at"])
        results.append(result)
    batch.finish(
        success_count=sum(1 for item in results if item["status"] in {"created", "updated", "deleted"}),
        error_count=sum(1 for item in results if item["status"] == "error"),
    )
    return {"ok": True, "batch_id": batch.id, "device_id": payload.device_id, "results": results}


@router.get("/conflicts")
def conflicts(user=Depends(current_access_user)):
    rows = OfflineSyncConflict.objects.filter(resolved=False).order_by("-created_at")[:100]
    return {
        "count": OfflineSyncConflict.objects.filter(resolved=False).count(),
        "results": [
            {
                "id": row.id,
                "model": row.model_key,
                "object_pk": row.object_pk,
                "policy": row.policy,
                "client_payload": row.client_payload,
                "server_snapshot": row.server_snapshot,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "policy": "server_timestamp_wins",
    }
