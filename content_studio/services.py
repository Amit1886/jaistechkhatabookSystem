from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.db.models import Max

from .models import (
    BrandKit,
    DesignProject,
    DesignElement,
    DesignPage,
    DesignTemplate,
    DesignVersion,
)
from .render_engine import render_project

logger = logging.getLogger(__name__)


def create_brand_kit(*, owner, name: str, **kwargs) -> BrandKit:
    with transaction.atomic():
        brand_kit = BrandKit.objects.create(owner=owner, name=name, **kwargs)
    logger.info("Created BrandKit %s for owner %s", brand_kit.pk, owner.pk)
    return brand_kit


def get_default_brand_kit(owner) -> BrandKit | None:
    return BrandKit.objects.filter(owner=owner, is_default=True).first()


def create_design_project(*, owner, title: str, **kwargs) -> DesignProject:
    with transaction.atomic():
        project = DesignProject.objects.create(owner=owner, title=title, **kwargs)
    logger.info("Created DesignProject %s for owner %s", project.pk, owner.pk)
    return project


def duplicate_design_project(*, project: DesignProject, owner) -> DesignProject:
    with transaction.atomic():
        new_project = DesignProject.objects.create(
            owner=owner,
            title=f"{project.title} (Copy)",
            brand_kit=project.brand_kit,
            width=project.width,
            height=project.height,
            background_color=project.background_color,
        )
        for element in project.elements.all():
            DesignElement.objects.create(
                project=new_project,
                element_type=element.element_type,
                x=element.x,
                y=element.y,
                width=element.width,
                height=element.height,
                rotation=element.rotation,
                opacity=element.opacity,
                content=element.content,
                style=element.style,
                z_index=element.z_index,
            )
    logger.info("Duplicated DesignProject %s to %s", project.pk, new_project.pk)
    return new_project


def save_design_version(*, project: DesignProject, note: str = "", created_by) -> DesignVersion:
    latest = project.versions.aggregate(Max("version_number"))["version_number__max"] or "v0"
    try:
        version_num = int(latest.lstrip("v")) + 1
    except ValueError:
        version_num = 1
    version_number = f"v{version_num}"
    with transaction.atomic():
        version = DesignVersion.objects.create(
            project=project,
            version_number=version_number,
            snapshot=project.metadata,
            note=note,
            created_by=created_by,
        )
    logger.info("Saved DesignVersion %s for project %s", version.pk, project.pk)
    return version


def add_element(*, project: DesignProject, element_type: str, **kwargs) -> DesignElement:
    element = DesignElement.objects.create(project=project, element_type=element_type, **kwargs)
    logger.info("Added %s element to project %s", element_type, project.pk)
    return element


def reorder_elements(*, project: DesignProject, element_ids: list[int]) -> None:
    elements = DesignElement.objects.filter(project=project, pk__in=element_ids)
    for index, element in enumerate(elements):
        element.z_index = index
        element.save(update_fields=["z_index"])


def create_template_from_project(*, project: DesignProject, title: str, category: str) -> DesignTemplate:
    template = DesignTemplate.objects.create(
        title=title,
        category=category,
        config=project.metadata,
    )
    logger.info("Created DesignTemplate %s from project %s", template.pk, project.pk)
    return template


def update_project_scene(
    *,
    project: DesignProject,
    elements: list | None = None,
    pages: list | None = None,
    metadata: dict | None = None,
    width: int | None = None,
    height: int | None = None,
    background_color: str | None = None,
) -> dict:
    """Persist the full editor scene state atomically."""
    with transaction.atomic():
        if width is not None:
            project.width = int(width)
        if height is not None:
            project.height = int(height)
        if background_color is not None:
            project.background_color = background_color
        if metadata is not None:
            project.metadata = metadata
        project.save(update_fields=["width", "height", "background_color", "metadata"])

        if elements is not None:
            project.elements.all().delete()
            for elem in elements:
                DesignElement.objects.create(
                    project=project,
                    element_type=elem.get("element_type", elem.get("type", "text")),
                    x=float(elem.get("x", 0)),
                    y=float(elem.get("y", 0)),
                    width=float(elem.get("width", 100)),
                    height=float(elem.get("height", 100)),
                    rotation=float(elem.get("rotation", 0)),
                    opacity=float(elem.get("opacity", 1.0)),
                    content=elem.get("content", ""),
                    style=elem.get("style", {}),
                    z_index=int(elem.get("z_index", elem.get("z", 0))),
                )

        if pages is not None:
            project.pages.all().delete()
            for idx, page in enumerate(pages):
                DesignPage.objects.create(
                    project=project,
                    name=page.get("name", f"Page {idx + 1}"),
                    width=int(page.get("width", project.width)),
                    height=int(page.get("height", project.height)),
                    order=idx,
                )

    UsageRecord.objects.create(
        user=project.owner,
        project=project,
        action="scene_saved",
    )
    return {
        "status": "saved",
        "project_id": project.pk,
        "element_count": project.elements.count(),
        "page_count": project.pages.count(),
    }


def export_project(project: DesignProject, *, export_format: str = "json") -> dict:
    """Build a serializable scene representation for export."""
    if export_format == "json":
        return {
            "title": project.title,
            "width": project.width,
            "height": project.height,
            "background_color": project.background_color,
            "brand_kit": {
                "primary_color": project.brand_kit.primary_color,
                "secondary_color": project.brand_kit.secondary_color,
                "font_family": project.brand_kit.font_family,
            }
            if project.brand_kit
            else None,
            "elements": [
                {
                    "type": e.element_type,
                    "x": e.x,
                    "y": e.y,
                    "width": e.width,
                    "height": e.height,
                    "rotation": e.rotation,
                    "opacity": e.opacity,
                    "content": e.content,
                    "style": e.style,
                    "z_index": e.z_index,
                }
                for e in project.elements.all()
            ],
            "pages": list(project.pages.values("name", "width", "height", "order")),
        }
    return render_project(project)
