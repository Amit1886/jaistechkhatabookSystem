from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from saas.models import RoleTemplatePermission, UserPermissionGraph, UserPermissionOverride

from .models import DashboardWidget, DynamicModule, ThemeConfig, Workspace
from .services import broadcast_enterprise_event


@receiver([post_save, post_delete], sender=DynamicModule)
def module_changed(sender, instance, **kwargs):
    broadcast_enterprise_event("modules", {"type": "module.changed", "key": instance.key})


@receiver([post_save, post_delete], sender=DashboardWidget)
@receiver([post_save, post_delete], sender=Workspace)
@receiver([post_save, post_delete], sender=ThemeConfig)
def dashboard_changed(sender, instance, **kwargs):
    broadcast_enterprise_event("dashboard", {"type": "dashboard.changed", "model": sender.__name__, "id": instance.pk})


@receiver([post_save, post_delete], sender=RoleTemplatePermission)
@receiver([post_save, post_delete], sender=UserPermissionGraph)
@receiver([post_save, post_delete], sender=UserPermissionOverride)
def permissions_changed(sender, instance, **kwargs):
    broadcast_enterprise_event("permissions", {"type": "permissions.changed", "model": sender.__name__, "id": instance.pk})
