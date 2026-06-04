import logging
import re


_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_ACCESS_LOGGER_NAMES = {"django.server", "django.channels.server", "daphne.server"}
_ACCESS_PREFIXES = ("HTTP ", "WebSocket ")


class DesktopFileLogFilter(logging.Filter):
    """
    Keep the desktop log file readable:

    - Drop noisy ASGI/WSGI access lines (they're already visible in the console).
    - Strip ANSI color escape codes so the file stays plain-text.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        message_plain = _ANSI_ESCAPE_RE.sub("", message) if message else message

        if record.name in _ACCESS_LOGGER_NAMES and (message_plain or "").startswith(_ACCESS_PREFIXES):
            return False

        if message_plain != message:
            record.msg = message_plain
            record.args = ()

        return True
