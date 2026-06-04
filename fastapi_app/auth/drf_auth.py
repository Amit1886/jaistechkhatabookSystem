from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions

from fastapi_app.auth.token_utils import decode_token


class FastAPIAccessTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            return None
        try:
            payload = decode_token(parts[1])
        except Exception:
            return None
        if payload.get("type") != "access":
            raise exceptions.AuthenticationFailed("access_token_required")
        user = get_user_model().objects.filter(pk=payload.get("sub"), is_active=True).first()
        if not user:
            raise exceptions.AuthenticationFailed("user_not_found")
        return (user, payload)
