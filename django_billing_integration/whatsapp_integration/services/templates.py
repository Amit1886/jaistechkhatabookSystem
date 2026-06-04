from __future__ import annotations

import re


_TPL = re.compile(r"{{\\s*([a-zA-Z0-9_]+)\\s*}}")


def render_template(text: str, data: dict) -> str:
    d = data or {}

    def repl(m):
        key = m.group(1)
        v = d.get(key, "")
        return "" if v is None else str(v)

    return _TPL.sub(repl, text or "")

