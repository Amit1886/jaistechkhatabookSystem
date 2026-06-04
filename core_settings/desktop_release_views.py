from __future__ import annotations

import os
from pathlib import Path

from django.http import FileResponse, JsonResponse, HttpResponseNotFound
from django.views.decorators.http import require_GET

from .models import DesktopRelease


def _extract_token(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    auth_header = auth_header.strip()
    if auth_header.lower().startswith("token "):
        return auth_header[6:].strip()
    return auth_header


def _expected_token() -> str:
    # Prefer a dedicated update token; fallback to sync token.
    return (os.getenv("DESKTOP_UPDATE_TOKEN") or os.getenv("SYNC_API_TOKEN") or "").strip()


def _is_authorized(request) -> bool:
    # Allow admin session users (download button inside /superadmin/).
    user = getattr(request, "user", None)
    if getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False):
        return True

    expected = _expected_token()
    if not expected:
        return False
    provided = _extract_token(request.headers.get("Authorization"))
    return provided == expected


def _public_download_enabled() -> bool:
    raw = (os.getenv("DESKTOP_PUBLIC_DOWNLOAD") or "True").strip().lower()
    return raw in {"1", "true", "yes", "on"}

def _android_public_download_enabled() -> bool:
    raw = (os.getenv("ANDROID_PUBLIC_DOWNLOAD") or "True").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _download_filename(release: DesktopRelease) -> str:
    try:
        suffix = Path(release.windows_exe.name).suffix
    except Exception:
        suffix = ""
    if not suffix:
        suffix = ".zip"
    return f"JaisTechKhataBookDesktop-{release.version}{suffix}"

def _download_apk_filename(release: DesktopRelease) -> str:
    return f"JaisTechKhataBookAndroid-{release.version}.apk"


@require_GET
def latest_desktop_release_api(request):
    """
    Token-protected API: returns latest published desktop release metadata.

    Desktop clients can call this when online:
      GET /api/v1/desktop/releases/latest/
      Authorization: Token <CLOUD_API_TOKEN>
    """
    if not _is_authorized(request):
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    release = DesktopRelease.objects.filter(pk=1).first()
    if not release:
        return JsonResponse({"ok": True, "published": False})
    if not release.is_published or not release.windows_exe:
        return JsonResponse({"ok": True, "published": False})

    download_url = request.build_absolute_uri("/api/v1/desktop/releases/download/")
    download_filename = _download_filename(release)
    return JsonResponse(
        {
            "ok": True,
            "published": True,
            "version": release.version,
            "sha256": release.sha256,
            "download_url": download_url,
            "download_filename": download_filename,
            "notes": release.notes,
            "published_at": release.published_at.isoformat() if release.published_at else None,
        }
    )


@require_GET
def download_desktop_release(request):
    """
    Token-protected download endpoint for the latest published desktop bundle.
    """
    if not _is_authorized(request):
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    release = DesktopRelease.objects.filter(pk=1).first()
    if not release:
        return HttpResponseNotFound("No published desktop release.")
    if not release.is_published or not release.windows_exe:
        return HttpResponseNotFound("No published desktop release.")

    f = release.windows_exe.open("rb")
    filename = _download_filename(release)
    return FileResponse(f, as_attachment=True, filename=filename)


@require_GET
def public_download_desktop_release(request):
    """
    Public download endpoint for the latest published desktop bundle (ZIP/EXE).

    This is used by the marketing/landing home page download button.
    """
    if not _public_download_enabled():
        return JsonResponse({"detail": "Download disabled"}, status=403)

    release = DesktopRelease.objects.filter(pk=1).first()
    if not release:
        return HttpResponseNotFound("No published desktop release.")
    if not release.is_published or not release.windows_exe:
        return HttpResponseNotFound("No published desktop release.")

    try:
        f = release.windows_exe.open("rb")
    except FileNotFoundError:
        return HttpResponseNotFound("Desktop release file not found.")

    return FileResponse(f, as_attachment=True, filename=_download_filename(release))


@require_GET
def latest_android_release_api(request):
    """
    Token-protected API: returns latest published Android APK release metadata.

    Mobile clients can call this when online:
      GET /api/v1/android/releases/latest/
      Authorization: Token <CLOUD_API_TOKEN>
    """
    if not _is_authorized(request):
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    release = DesktopRelease.objects.filter(pk=1).first()
    if not release:
        return JsonResponse({"ok": True, "published": False})
    if not release.is_published or not getattr(release, "android_apk", None):
        return JsonResponse({"ok": True, "published": False})

    download_url = request.build_absolute_uri("/api/v1/android/releases/download/")
    return JsonResponse(
        {
            "ok": True,
            "published": True,
            "version": release.version,
            "sha256": getattr(release, "android_sha256", "") or "",
            "download_url": download_url,
            "notes": release.notes,
            "published_at": release.published_at.isoformat() if release.published_at else None,
        }
    )


@require_GET
def download_android_release(request):
    """
    Token-protected download endpoint for the latest published Android APK.
    """
    if not _is_authorized(request):
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    release = DesktopRelease.objects.filter(pk=1).first()
    if not release:
        return HttpResponseNotFound("No published Android release.")
    if not release.is_published or not getattr(release, "android_apk", None):
        return HttpResponseNotFound("No published Android release.")

    try:
        f = release.android_apk.open("rb")
    except FileNotFoundError:
        return HttpResponseNotFound("Android release file not found.")

    return FileResponse(f, as_attachment=True, filename=_download_apk_filename(release))


@require_GET
def public_download_android_release(request):
    """
    Public download endpoint for the latest published Android APK.

    This is used by the marketing/landing home page download button.
    """
    if not _android_public_download_enabled():
        return JsonResponse({"detail": "Download disabled"}, status=403)

    release = DesktopRelease.objects.filter(pk=1).first()
    if not release:
        return HttpResponseNotFound("No published Android release.")
    if not release.is_published or not getattr(release, "android_apk", None):
        return HttpResponseNotFound("No published Android release.")

    try:
        f = release.android_apk.open("rb")
    except FileNotFoundError:
        return HttpResponseNotFound("Android release file not found.")

    return FileResponse(f, as_attachment=True, filename=_download_apk_filename(release))
