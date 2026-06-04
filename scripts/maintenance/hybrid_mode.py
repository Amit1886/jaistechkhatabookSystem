from __future__ import annotations

import socket


def is_internet_available(
    host: str = "8.8.8.8",
    port: int = 53,
    timeout_seconds: float = 2.0,
) -> bool:
    """
    Internet connectivity check (CORE REQUIREMENT).

    Uses a TCP socket connection attempt to 8.8.8.8:53 (Google DNS).
    This is a practical "can we reach the internet" test without requiring DNS.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def current_connectivity_mode() -> str:
    return "ONLINE" if is_internet_available() else "OFFLINE"

