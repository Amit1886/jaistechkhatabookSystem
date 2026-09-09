import json


def resize_image(image_data: bytes, width: int, height: int) -> bytes:
    return image_data


def smart_resize(image_data: bytes, target_width: int, target_height: int) -> dict:
    return {
        "data": image_data,
        "width": target_width,
        "height": target_height,
    }
