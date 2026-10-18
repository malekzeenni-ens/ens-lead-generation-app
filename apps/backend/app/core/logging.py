from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_REDACTED_KEYS = {
    "access_token",
    "api_key",
    "app_secret",
    "authorization",
    "authorization_code",
    "code",
    "password",
    "secret",
    "session_token",
    "state",
    "token",
}

# Attributes every LogRecord carries regardless of what a call site logs; anything
# else on the record's __dict__ came from a caller's `extra={...}` kwarg.
_STANDARD_LOG_RECORD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()
) | {"message", "asctime"}


def redact(value: Any) -> Any:
    """Recursively mask known-sensitive dict keys (case-insensitive) anywhere in `value`."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in _REDACTED_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
        }
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            payload["correlation_id"] = correlation_id
        # Fold in any `extra={...}` kwargs so redact() actually covers them, not
        # just this method's own fixed fields.
        extra = {
            key: item
            for key, item in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_ATTRS and key != "correlation_id"
        }
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), ensure_ascii=False, default=str)


def configure_logging(log_directory: Path) -> None:
    """Send application logs to `<log_directory>/application.jsonl`.

    Idempotent for the same directory. A different directory replaces the previous file handler,
    which is closed, so the log always lands where the current settings say.
    """
    log_directory.mkdir(parents=True, exist_ok=True)
    target = (log_directory / "application.jsonl").resolve()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for existing in list(root.handlers):
        if not isinstance(existing, RotatingFileHandler):
            continue
        if Path(existing.baseFilename).resolve() == target:
            return
        root.removeHandler(existing)
        existing.close()
    handler = RotatingFileHandler(target, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
