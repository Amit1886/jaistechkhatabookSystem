import json


def generate_qr(data: str, size: int = 200) -> bytes:
    return b""


def generate_batch_qr(items: list, size: int = 200) -> list:
    return [generate_qr(item, size) for item in items]
