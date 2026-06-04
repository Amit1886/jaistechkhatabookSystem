"""
Celery tasks entrypoint for the `khataapp` Django app.

Celery autodiscovery imports `<app>.tasks` for each installed app. We keep the
task implementations inside `khataapp/core_engine/tasks/` and import them here
to register them.
"""

from khataapp.core_engine.tasks.daily import update_engine_snapshots_daily  # noqa: F401

