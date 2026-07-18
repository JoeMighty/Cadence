"""A small on-disk error log the user can read and attach to a bug report.

Local only, nothing is ever sent anywhere. Job failures and unhandled request
errors land here with a timestamp and traceback, size-capped by rotation.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from . import settings

_logger: Optional[logging.Logger] = None


def _get() -> logging.Logger:
    global _logger
    if _logger is None:
        settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
        lg = logging.getLogger("cadence.errors")
        lg.setLevel(logging.ERROR)
        lg.propagate = False
        handler = RotatingFileHandler(
            settings.LOG_PATH, maxBytes=512_000, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        lg.addHandler(handler)
        _logger = lg
    return _logger


def record(context: str, exc: BaseException) -> None:
    """Append an error with its traceback. Never raises."""
    try:
        _get().error(context, exc_info=exc)
    except Exception:
        pass


def tail(max_chars: int = 20000) -> str:
    """The most recent slice of the log, for showing in the app."""
    try:
        text = settings.LOG_PATH.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError:
        return ""
    return text[-max_chars:]


def clear() -> None:
    try:
        settings.LOG_PATH.write_text("", encoding="utf-8")
    except OSError:
        pass
