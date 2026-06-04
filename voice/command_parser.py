from __future__ import annotations

from whatsapp.parser import ParsedCommand, parse_accounting_command


def parse_voice_command(text: str) -> ParsedCommand | None:
    # Voice commands share the same grammar as WhatsApp accounting.
    return parse_accounting_command(text)

