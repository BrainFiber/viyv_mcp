"""Structured audit logging built on Python's standard logging module.

The logger name ``viyv_mcp.security.audit`` allows users to attach custom
handlers without touching viyv_mcp internals.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

AUDIT_LOGGER_NAME = "viyv_mcp.security.audit"


def setup_audit_logger(log_path: str | None = None) -> logging.Logger:
    """Configure and return the audit logger.

    * *log_path* provided  → append JSONL to that file.
    * *log_path* ``None``  → write to stderr (development default).
    """
    audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # avoid duplicate output via root logger

    # Avoid adding duplicate handlers on repeated calls
    if audit_logger.handlers:
        return audit_logger

    if log_path:
        handler: logging.Handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stderr)

    # Raw message only — the JSON record already contains all metadata
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
    return audit_logger


def emit_audit_record(audit_logger: logging.Logger, record: dict[str, Any]) -> None:
    """Serialize *record* as a single JSON line and emit via the audit logger."""
    record.setdefault("ts", datetime.now(timezone.utc).isoformat())
    record.setdefault("type", "audit")
    audit_logger.info(json.dumps(record, ensure_ascii=False, default=str))
