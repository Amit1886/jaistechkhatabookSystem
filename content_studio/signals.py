from __future__ import annotations

import logging

from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DesignProject, DesignVersion

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DesignProject)
def _ensure_initial_version(sender, instance: DesignProject, created: bool, **kwargs):
    """Create an initial version snapshot when a project is first saved."""
    if not created:
        return
    DesignVersion.objects.create(
        project=instance,
        version_number="v1",
        snapshot=instance.metadata or {},
        note="Initial version",
        created_by=instance.owner,
    )
    logger.info("Created initial DesignVersion for project %s", instance.pk)


@receiver(post_save)
def _ensure_default_brand_kit(sender, instance, created: bool, **kwargs):
    """Ensure every user has a default brand kit attached."""
    if not created:
        return
    UserModel = apps.get_model("accounts", "User")
    if sender is not UserModel:
        return
    if not getattr(instance, "is_active", True):
        return
    BrandKit = apps.get_model("content_studio", "BrandKit")
    BrandKit.objects.get_or_create(
        owner=instance,
        is_default=True,
        defaults={
            "name": "My Brand Kit",
            "primary_color": "#000000",
            "secondary_color": "#FFFFFF",
            "font_family": "Arial",
        },
    )
