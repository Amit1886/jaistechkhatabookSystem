from __future__ import annotations

from notifications.models import Notification


def _company_from_user(user):
    return getattr(getattr(user, "userprofile", None), "company", None)


def notify_user(*, user, title: str, body: str = "", level: str = "info", data: dict | None = None) -> Notification:
    company = _company_from_user(user)
    return Notification.objects.create(
        company=company,
        user=user,
        title=(title or "")[:200],
        body=body or "",
        level=level or "info",
        data=data or {},
    )

