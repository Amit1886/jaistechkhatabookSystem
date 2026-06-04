from __future__ import annotations

from datetime import date as date_type, timedelta
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from khataapp.core_engine.models.tasks import DailyTaskCompletion, DailyTaskDefinition
from khataapp.core_engine.services.admin_control import get_engine_flags
from khataapp.core_engine.services.plan_access import can_access_feature
from khataapp.core_engine.services.reward_service import add_rewards
from khataapp.core_engine.utils.engine import get_or_create_engine_for_update


DEFAULT_TASKS = [
    {
        "key": "daily_login",
        "title": "Daily Login",
        "description": "Login daily to build your streak.",
        "coins_reward": 1,
        "points_reward": 5,
        "sort_order": 10,
    },
    {
        "key": "add_party",
        "title": "Add a Party",
        "description": "Add a new customer or supplier.",
        "coins_reward": 2,
        "points_reward": 10,
        "sort_order": 20,
    },
    {
        "key": "add_transaction",
        "title": "Add a Transaction",
        "description": "Record at least one transaction today.",
        "coins_reward": 2,
        "points_reward": 10,
        "sort_order": 30,
    },
    {
        "key": "create_invoice",
        "title": "Create an Invoice",
        "description": "Generate an invoice to get billing rewards.",
        "coins_reward": 3,
        "points_reward": 15,
        "sort_order": 40,
    },
]


@transaction.atomic
def ensure_default_tasks() -> None:
    for t in DEFAULT_TASKS:
        DailyTaskDefinition.objects.get_or_create(
            key=t["key"],
            defaults={
                "title": t["title"],
                "description": t.get("description", ""),
                "is_active": True,
                "sort_order": t.get("sort_order", 0),
                "coins_reward": t.get("coins_reward", 0),
                "points_reward": t.get("points_reward", 0),
            },
        )


def _compute_streak_days(owner, day: date_type) -> int:
    """
    Streak is based on consecutive days with at least one completion.
    """
    days = (
        DailyTaskCompletion.objects.filter(owner=owner, day__lte=day)
        .values_list("day", flat=True)
        .distinct()
        .order_by("-day")
    )
    streak = 0
    expected = day
    for d in days:
        if d != expected:
            break
        streak += 1
        expected = expected - timedelta(days=1)
    return streak


@transaction.atomic
def complete_task(
    *,
    owner,
    task_key: str,
    day: Optional[date_type] = None,
    meta: Optional[dict] = None,
    actor=None,
) -> bool:
    if not owner or not getattr(owner, "is_authenticated", False):
        return False
    if not can_access_feature(owner, "engine.daily_tasks").allowed:
        return False

    flags = get_engine_flags()
    if not flags.enable_daily_tasks:
        return False

    ensure_default_tasks()

    task = DailyTaskDefinition.objects.filter(key=task_key, is_active=True).first()
    if not task:
        return False

    day = day or timezone.localdate()
    try:
        completion = DailyTaskCompletion.objects.create(owner=owner, task=task, day=day, meta=meta or {})
    except IntegrityError:
        return False

    # Award rewards for completing tasks.
    if task.coins_reward or task.points_reward:
        add_rewards(
            owner=owner,
            coins_delta=int(task.coins_reward or 0),
            points_delta=int(task.points_reward or 0),
            source="task",
            amount_reference=0,
            related_obj=completion,
            meta={"task_key": task_key, "day": str(day), **(meta or {})},
            actor=actor,
        )

    # Update streak on engine.
    engine = get_or_create_engine_for_update(owner)
    engine.daily_task_streak = max(0, _compute_streak_days(owner, day))
    engine.save(update_fields=["daily_task_streak", "updated_at"])
    return True


def record_daily_login(*, owner, actor=None) -> None:
    complete_task(owner=owner, task_key="daily_login", day=timezone.localdate(), meta={"source": "login"}, actor=actor)

