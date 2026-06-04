from __future__ import annotations

import re

_DIGITS = re.compile(r"[^0-9]")


def digits_only(value: str) -> str:
    return _DIGITS.sub("", value or "").strip()


def normalize_wa_phone(value: str, *, default_country_code: str = "") -> str:
    """
    Normalize a phone number for WhatsApp providers (digits only, country code preferred).

    - Removes non-digits and common prefixes like 00.
    - If `default_country_code` is set, auto-prefixes for 10-digit numbers.

    Examples (default_country_code="91"):
    - "9555733478" -> "919555733478"
    - "+91 95557 33478" -> "919555733478"
    - "09555733478" -> "919555733478"
    """
    d = digits_only(value)
    if not d:
        return ""

    # Convert "00<cc><number>" to "<cc><number>"
    while d.startswith("00"):
        d = d[2:]

    cc = digits_only(default_country_code)
    if cc:
        if len(d) == 10:
            d = cc + d
        elif len(d) == 11 and d.startswith("0"):
            d = cc + d[1:]

    return d

