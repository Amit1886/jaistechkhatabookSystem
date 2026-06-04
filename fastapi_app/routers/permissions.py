from django.contrib.auth.models import Permission
from fastapi import APIRouter, Depends

from core.metadata.scanner import scan_models
from fastapi_app.dependencies.auth import current_access_user


router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/me")
def my_permissions(user=Depends(current_access_user)):
    permissions = sorted(user.get_all_permissions())
    return {
        "user": {"id": str(user.pk), "email": getattr(user, "email", ""), "is_superuser": user.is_superuser},
        "permissions": permissions,
        "groups": list(user.groups.values_list("name", flat=True)),
    }


@router.get("/matrix")
def permission_matrix(user=Depends(current_access_user)):
    model_rows = []
    for meta in scan_models():
        perms = meta["permissions"]
        model_rows.append(
            {
                "model": meta["key"],
                "label": meta["label"],
                "view": user.is_superuser or user.has_perm(perms["view"]),
                "add": user.is_superuser or user.has_perm(perms["add"]),
                "change": user.is_superuser or user.has_perm(perms["change"]),
                "delete": user.is_superuser or user.has_perm(perms["delete"]),
            }
        )
    return {"count": len(model_rows), "results": model_rows}


@router.get("/catalog")
def permission_catalog(user=Depends(current_access_user)):
    if not user.is_superuser:
        return {"count": 0, "results": []}
    rows = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
    return {
        "count": rows.count(),
        "results": [
            {
                "id": perm.id,
                "key": f"{perm.content_type.app_label}.{perm.codename}",
                "name": perm.name,
                "app_label": perm.content_type.app_label,
                "model": perm.content_type.model,
            }
            for perm in rows[:2000]
        ],
    }
