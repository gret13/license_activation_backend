"""Privacy-preserving JSONL logging with retained files on bind mounts."""

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

LOGGER_NAME = "license_activation"
ALLOWED_LOG_FIELDS = frozenset(
    {"request_id", "client_ip_id", "license_id", "activation_id", "device_id",
     "event", "reason", "status_code", "path", "elapsed_ms"}
)


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": (
                datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z")
            ),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for field in ALLOWED_LOG_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def setup_logging(directory: Path | None = None) -> logging.Logger:
    if directory is None:
        directory = Path("logs")
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    for filename, min_level in (("app.log", logging.INFO), ("error.log", logging.ERROR)):
        handler = RotatingFileHandler(
            directory / filename, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
        )
        handler.setLevel(min_level)
        handler.setFormatter(JsonLineFormatter())
        logger.addHandler(handler)
    return logger


def pseudonym(secret: str, input_value: str) -> str:
    return hmac.new(secret.encode("utf-8"), input_value.encode("utf-8"), hashlib.sha256).hexdigest()


def log_event(level: int, event: str, **safe_fields: Any) -> None:
    extra = {key: val for key, val in safe_fields.items() if key in ALLOWED_LOG_FIELDS}
    logging.getLogger(LOGGER_NAME).log(level, event, extra=extra)
