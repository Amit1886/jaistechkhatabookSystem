from __future__ import annotations

from celery import shared_task
from django.utils import timezone


@shared_task
def process_catalog_rollouts(limit: int = 50):
    """
    Apply scheduled rollouts and optionally revert expired ones.

    - When a rollout becomes ACTIVE, we set vendor's default catalog to rollout.catalog_id
      and store the previous value in rollout.metadata["previous_default_catalog_id"].
    - When ends_at passes and revert_on_end=True, we revert to the previous default and mark COMPLETED.

    Phase A: markets_json is informational only (no per-market routing).
    """

    from vendors.models import VendorCatalogRollout
    from vendors.services.catalogs import get_default_catalog_id, set_default_catalog
    from vendors.models import VendorCatalog

    now = timezone.now()
    changed = 0

    # Activate due rollouts.
    due = (
        VendorCatalogRollout.objects.select_related("vendor", "catalog")
        .filter(status=VendorCatalogRollout.Status.SCHEDULED)
        .filter(starts_at__isnull=False, starts_at__lte=now)
        .order_by("starts_at")[:limit]
    )
    for r in due:
        try:
            prev = get_default_catalog_id(r.vendor)
            r.metadata = dict(r.metadata or {})
            r.metadata.setdefault("previous_default_catalog_id", prev)
            set_default_catalog(r.vendor, r.catalog)
            r.status = VendorCatalogRollout.Status.ACTIVE
            r.applied_at = now
            r.last_error = ""
            r.save(update_fields=["metadata", "status", "applied_at", "last_error", "updated_at"])
            changed += 1
        except Exception as exc:
            r.status = VendorCatalogRollout.Status.FAILED
            r.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            r.save(update_fields=["status", "last_error", "updated_at"])

    # Revert expired rollouts.
    exp = (
        VendorCatalogRollout.objects.select_related("vendor", "catalog")
        .filter(status=VendorCatalogRollout.Status.ACTIVE)
        .filter(ends_at__isnull=False, ends_at__lte=now)
        .order_by("ends_at")[:limit]
    )
    for r in exp:
        try:
            if r.revert_on_end:
                prev = None
                try:
                    prev = (r.metadata or {}).get("previous_default_catalog_id")
                    prev = int(prev) if prev is not None else None
                except Exception:
                    prev = None

                prev_catalog = None
                if prev:
                    prev_catalog = VendorCatalog.objects.filter(vendor=r.vendor, id=prev).first()
                set_default_catalog(r.vendor, prev_catalog)
                r.reverted_at = now

            r.status = VendorCatalogRollout.Status.COMPLETED
            r.last_error = ""
            r.save(update_fields=["status", "reverted_at", "last_error", "updated_at"])
            changed += 1
        except Exception as exc:
            r.status = VendorCatalogRollout.Status.FAILED
            r.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            r.save(update_fields=["status", "last_error", "updated_at"])

    return changed

