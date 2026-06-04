from __future__ import annotations

from fraud_detection.models import FraudSignal


def _company_from_user(user):
    return getattr(getattr(user, "userprofile", None), "company", None)


def raise_signal(
    *,
    signal_type: str,
    user=None,
    related_user=None,
    severity: str = "low",
    description: str = "",
    payload: dict | None = None,
) -> FraudSignal:
    company = _company_from_user(user) if user else None
    return FraudSignal.objects.create(
        company=company,
        signal_type=(signal_type or "")[:60],
        severity=severity or "low",
        user=user,
        related_user=related_user,
        description=(description or "")[:300],
        payload=payload or {},
    )


def check_user_referral_integrity(*, user):
    if not user:
        return None
    if getattr(user, "referred_by_id", None) and user.referred_by_id == user.id:
        return raise_signal(
            signal_type="self_referral",
            user=user,
            related_user=user,
            severity="high",
            description="User referred themselves.",
            payload={"user_id": user.id},
        )
    return None

