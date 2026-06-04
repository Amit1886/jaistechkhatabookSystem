from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction

from fastapi_app.auth.token_utils import ACCESS_MINUTES, create_access_token, create_refresh_token, decode_token
from fastapi_app.dependencies.auth import current_user
from fastapi_app.schemas.common import TokenPair


router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str
    username: str | None = None
    mobile: str | None = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str


@router.post("/signup", response_model=TokenPair)
@transaction.atomic
def signup(payload: SignupRequest, request: Request):
    User = get_user_model()
    if User.objects.filter(email__iexact=payload.email).exists():
        raise HTTPException(status_code=400, detail="email_already_registered")
    user = User(email=payload.email, username=payload.username or payload.email.split("@")[0], mobile=payload.mobile or None)
    user.set_password(payload.password)
    user.save()
    return TokenPair(
        access_token=create_access_token(user=user),
        refresh_token=create_refresh_token(user=user),
        expires_in=ACCESS_MINUTES * 60,
    )


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    User = get_user_model()
    identifier = (payload.identifier or "").strip()
    user = (
        User.objects.filter(email__iexact=identifier).first()
        or User.objects.filter(username__iexact=identifier).first()
        or User.objects.filter(mobile=identifier).first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not getattr(user, "is_active", False):
        raise HTTPException(status_code=403, detail="inactive_user")
    auth_user = authenticate(request=None, username=getattr(user, "email", None) or getattr(user, "username", None), password=payload.password)
    if auth_user is None and not user.check_password(payload.password):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    access = create_access_token(user=user)
    refresh_token = create_refresh_token(user=user)
    return {
        "access_token": access,
        "refresh_token": refresh_token,
        "access": access,
        "refresh": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_MINUTES * 60,
        "user": {
            "id": str(user.pk),
            "email": getattr(user, "email", "") or "",
            "username": getattr(user, "username", "") or "",
            "name": (user.get_full_name() or getattr(user, "username", "") or getattr(user, "email", "")),
            "mobile": getattr(user, "mobile", "") or "",
        },
    }


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest):
    try:
        decoded = decode_token(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid_refresh_token") from exc
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="refresh_token_required")
    User = get_user_model()
    user = User.objects.filter(pk=decoded.get("sub"), is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="user_not_found")
    return TokenPair(
        access_token=create_access_token(user=user),
        refresh_token=create_refresh_token(user=user),
        expires_in=ACCESS_MINUTES * 60,
    )


@router.post("/logout")
def logout(user=Depends(current_user)):
    return {"ok": True, "detail": "Client should discard access and refresh tokens."}


@router.get("/me")
def me(user=Depends(current_user)):
    return {
        "id": str(user.pk),
        "email": getattr(user, "email", "") or "",
        "username": getattr(user, "username", "") or "",
        "name": (user.get_full_name() or getattr(user, "username", "") or getattr(user, "email", "")),
        "mobile": getattr(user, "mobile", "") or "",
        "is_staff": bool(getattr(user, "is_staff", False)),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
    }


@router.post("/password-reset")
def password_reset(payload: PasswordResetRequest):
    return {"ok": True, "detail": "Password reset request accepted.", "email": payload.email}
