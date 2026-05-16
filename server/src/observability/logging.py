from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.observability.context import get_request_id


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = get_request_id()
        record.request_id = request_id if request_id is not None else "-"
        return True


class JsonLogFormatter(logging.Formatter):
    _RESERVED_KEYS = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "request_id",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._RESERVED_KEYS and not key.startswith("_")
        }
        if extra:
            payload.update(extra)

        return json.dumps(payload, ensure_ascii=False, default=str)


class PlainLogFormatter(logging.Formatter):
    _RESERVED_KEYS = JsonLogFormatter._RESERVED_KEYS

    def format(self, record: logging.LogRecord) -> str:
        base_message = super().format(record)
        extra = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._RESERVED_KEYS and not key.startswith("_")
        }
        if not extra:
            return base_message

        serialized_extra = " ".join(
            f"{key}={self._serialize_value(value)}" for key, value in extra.items()
        )
        return f"{base_message} {serialized_extra}"

    @staticmethod
    def _serialize_value(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers and getattr(root_logger, "_nerdex_logging_configured", False):
        return

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())

    if settings.logging.format == "json":
        formatter: logging.Formatter = JsonLogFormatter()
    else:
        formatter = PlainLogFormatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
            defaults={"request_id": "-"},
        )
    handler.setFormatter(formatter)

    logging.basicConfig(level=settings.logging.level, handlers=[handler], force=True)

    root_logger = logging.getLogger()
    setattr(root_logger, "_nerdex_logging_configured", True)
