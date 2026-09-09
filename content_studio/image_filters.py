import json


def apply_filter(image_data: bytes, filter_name: str, params: dict) -> bytes:
    return image_data


def get_available_filters() -> list:
    return [
        {"name": "grayscale", "params": {}},
        {"name": "blur", "params": {"radius": 5}},
        {"name": "brightness", "params": {"value": 1.2}},
    ]
