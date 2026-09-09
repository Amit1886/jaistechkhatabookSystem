import json


def get_animation_presets() -> list:
    return [
        {"name": "fade-in", "duration": 500, "easing": "ease-in"},
        {"name": "slide-up", "duration": 400, "easing": "ease-out"},
        {"name": "zoom-in", "duration": 600, "easing": "ease-in-out"},
    ]


def apply_animation(element_id: int, preset_name: str) -> dict:
    return {
        "element_id": element_id,
        "animation": preset_name,
    }
