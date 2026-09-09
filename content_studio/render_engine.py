from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def render_design(project_data: dict) -> bytes:
    return b""


def render_project(project) -> dict:
    """Build a structured scene dict from a DesignProject and its elements."""
    from .models import DesignElement

    elements = []
    for element in DesignElement.objects.filter(project=project):
        elements.append(
            {
                "id": element.pk,
                "type": element.element_type,
                "x": element.x,
                "y": element.y,
                "width": element.width,
                "height": element.height,
                "rotation": element.rotation,
                "opacity": element.opacity,
                "content": element.content,
                "style": element.style or {},
                "z_index": element.z_index,
            }
        )

    brand_kit = None
    if getattr(project, "brand_kit", None):
        brand_kit = {
            "primary_color": project.brand_kit.primary_color,
            "secondary_color": project.brand_kit.secondary_color,
            "font_family": project.brand_kit.font_family,
        }

    scene = {
        "title": project.title,
        "width": project.width,
        "height": project.height,
        "background_color": project.background_color,
        "brand_kit": brand_kit,
        "pages": [
            {
                "id": page.pk,
                "name": page.name,
                "width": page.width,
                "height": page.height,
                "order": page.order,
            }
            for page in project.pages.all()
        ],
        "elements": elements,
    }
    logger.info("Rendered project %s with %d elements", project.pk, len(elements))
    return scene
