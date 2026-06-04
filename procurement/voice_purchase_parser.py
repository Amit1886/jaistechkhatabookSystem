from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


_WS = re.compile(r"\s+")
_SPLIT = re.compile(r"[.;\n]+")


@dataclass(frozen=True)
class ParsedVoicePurchase:
    ok: bool
    supplier_name: str
    items: list[dict[str, Any]]
    error: str = ""


def _clean_unit(unit: str) -> str:
    u = (unit or "").strip().lower()
    if u.endswith("s") and len(u) > 2:
        u = u[:-1]
    u = u.replace("kgs", "kg").replace("kilogram", "kg")
    u = u.replace("gms", "g").replace("grams", "g").replace("gram", "g")
    u = u.replace("litre", "l").replace("liter", "l").replace("ltr", "l")
    return u[:30]


def parse_voice_purchase(text: str) -> ParsedVoicePurchase:
    raw = (text or "").strip()
    if not raw:
        return ParsedVoicePurchase(ok=False, supplier_name="", items=[], error="Empty command")

    raw = _WS.sub(" ", raw).strip()
    parts = [p.strip() for p in _SPLIT.split(raw) if p.strip()]
    if not parts:
        return ParsedVoicePurchase(ok=False, supplier_name="", items=[], error="Empty command")

    supplier_name = ""
    items: list[dict[str, Any]] = []

    # Find supplier segment first
    for p in parts:
        m = re.search(r"\bsupplier\b\s+(?P<name>.+)$", p, flags=re.IGNORECASE)
        if m:
            supplier_name = (m.group("name") or "").strip()
            break

    for p in parts:
        low = p.lower().strip()
        if low.startswith("supplier "):
            continue
        # Format: "<name> <qty> <unit> [at <rate>]"
        m = re.search(
            r"^(?P<name>.+?)\s+(?P<qty>\d+(?:\.\d+)?)\s+(?P<unit>[a-zA-Z]+)(?:\s+(?:at|rate)\s+(?P<rate>\d+(?:\.\d+)?))?$",
            p.strip(),
            flags=re.IGNORECASE,
        )
        if not m:
            continue
        name = (m.group("name") or "").strip()
        qty = (m.group("qty") or "").strip()
        unit = _clean_unit(m.group("unit") or "")
        rate = (m.group("rate") or "").strip()
        if not name or not qty:
            continue
        item: dict[str, Any] = {"name": name[:200], "qty": qty, "unit": unit}
        if rate:
            item["rate"] = rate
        items.append(item)

    if not supplier_name:
        supplier_name = "Voice Supplier"
    if not items:
        return ParsedVoicePurchase(ok=False, supplier_name=supplier_name[:200], items=[], error="No items parsed")
    return ParsedVoicePurchase(ok=True, supplier_name=supplier_name[:200], items=items)

