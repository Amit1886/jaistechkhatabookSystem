from __future__ import annotations

from django.utils import timezone
from django.utils.text import slugify

from smart_bi.models import FestivalCampaign


def festival_context(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    today = timezone.localdate()
    try:
        campaign = (
            FestivalCampaign.objects.filter(
                owner=user,
                status=FestivalCampaign.Status.ACTIVE,
                start_date__lte=today,
                end_date__gte=today,
            )
            .order_by("-start_date", "-id")
            .first()
        )
    except Exception:
        campaign = None

    theme_slug = ""
    if campaign:
        theme_slug = slugify(getattr(campaign, "theme", "") or "")

    return {
        "active_festival_campaign": campaign,
        "festival_theme_class": (f"festival-theme-{theme_slug}" if theme_slug else ""),
    }
