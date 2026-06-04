from __future__ import annotations

try:
    from celery import shared_task
except Exception:
    shared_task = None

from superapp.services.dashboard import build_super_dashboard_snapshot
from superapp.services.tax_engine import build_tax_report


def _shared_task(func):
    return shared_task(func) if shared_task else func


@_shared_task
def refresh_super_dashboard_snapshot(period="today"):
    snapshot = build_super_dashboard_snapshot(period=period)
    return snapshot.id


@_shared_task
def generate_monthly_tax_summary(period):
    report = build_tax_report("tax_summary", period)
    return report.id

