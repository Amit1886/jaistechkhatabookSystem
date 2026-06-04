from __future__ import annotations

from django.conf import settings


class DesktopCsrfBypassMiddleware:
    """
    Desktop-only CSRF relaxation for localhost embedded UI.

    The desktop EXE serves the app on loopback and opens it in an embedded
    WebView. Some embedded engines can behave oddly with cookies on redirects,
    which breaks OTP/session-based flows (CSRF/session cookie mismatch).

    We only bypass CSRF checks for a small set of auth endpoints and only when
    DESKTOP_MODE is enabled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "DESKTOP_MODE", False) and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            path = (request.path or "").rstrip("/")
            if path in {
                "/accounts/login",
                "/accounts/signup",
                "/accounts/verify-otp",
                "/accounts/logout",
            }:
                request._dont_enforce_csrf_checks = True

        return self.get_response(request)
