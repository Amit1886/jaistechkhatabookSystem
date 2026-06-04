from __future__ import annotations

from django.db import models, transaction
from django.db.models import Count

from leads.models import Lead, LeadActivity


def _company_from_user(user):
    return getattr(getattr(user, "userprofile", None), "company", None)


@transaction.atomic
def assign_lead(lead: Lead, *, assigned_to, actor=None, reason: str = "") -> Lead:
    lead.assigned_to = assigned_to
    lead.save(update_fields=["assigned_to", "updated_at"])
    LeadActivity.objects.create(
        lead=lead,
        actor=actor,
        activity_type="assign",
        note=(reason or "")[:500],
        payload={"assigned_to": getattr(assigned_to, "id", None)},
    )
    return lead


def auto_assign_lead(*, lead: Lead, fallback_user=None):
    """
    Best-effort lead assignment:
    - Prefer agents matching the lead's pincode (via userprofile.pincode)
    - Otherwise leave unassigned or use fallback_user if provided.
    """

    if lead.assigned_to_id:
        return lead

    from django.contrib.auth import get_user_model

    User = get_user_model()
    company = lead.company

    if lead.pincode_id:
        candidates = (
            User.objects.filter(role__in=["agent", "super_agent"], userprofile__pincode_id=lead.pincode_id)
            .distinct()
            .only("id")
        )
        candidate_ids = list(candidates.values_list("id", flat=True))
        if candidate_ids:
            # pick least-loaded by open leads
            loads = (
                Lead.objects.filter(company=company, assigned_to_id__in=candidate_ids)
                .exclude(status__in=["won", "lost"])
                .values("assigned_to_id")
                .annotate(c=Count("id"))
            )
            load_map = {r["assigned_to_id"]: r["c"] for r in loads}
            chosen = min(candidate_ids, key=lambda uid: load_map.get(uid, 0))
            lead.assigned_to_id = chosen
            lead.save(update_fields=["assigned_to", "updated_at"])
            return lead

    if fallback_user:
        lead.assigned_to = fallback_user
        lead.save(update_fields=["assigned_to", "updated_at"])
    return lead
