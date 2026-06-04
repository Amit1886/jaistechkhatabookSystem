from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from django.contrib.auth import get_user_model

from fastapi_app.auth.token_utils import decode_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/fastapi/auth/login", auto_error=False)


def current_user(token: str | None = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token")
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc
    if payload.get("type") not in {"access", "refresh"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_type")
    User = get_user_model()
    user = User.objects.filter(pk=payload.get("sub"), is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_not_found")
    user.fastapi_token_payload = payload
    return user


def current_access_user(user=Depends(current_user)):
    payload = getattr(user, "fastapi_token_payload", {}) or {}
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="access_token_required")
    return user


def company_context(
    x_company_id: str = Header(default=""),
    x_tenant_id: str = Header(default=""),
) -> dict[str, str]:
    return {"company_id": x_company_id, "tenant_id": x_tenant_id}
