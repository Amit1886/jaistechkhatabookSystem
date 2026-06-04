from __future__ import annotations

from typing import Optional

from django.db import IntegrityError, transaction

from khataapp.core_engine.models.engine import BusinessGrowthEngine


@transaction.atomic
def get_or_create_engine_for_update(owner) -> BusinessGrowthEngine:
    """
    Return the user's BusinessGrowthEngine row with a DB lock (select_for_update).
    Creates the row if missing.
    """
    engine = BusinessGrowthEngine.objects.select_for_update().filter(owner=owner).first()
    if engine:
        return engine
    try:
        return BusinessGrowthEngine.objects.create(owner=owner)
    except IntegrityError:
        # Race: someone else created it.
        return BusinessGrowthEngine.objects.select_for_update().get(owner=owner)


def get_engine(owner) -> Optional[BusinessGrowthEngine]:
    if not owner or not getattr(owner, "is_authenticated", False):
        return None
    return BusinessGrowthEngine.objects.filter(owner=owner).first()

