"""Structured logging via structlog, with secret redaction.

Decrypted BYOK keys, passwords and tokens must never reach the logs — the
``_redact`` processor scrubs any field whose name looks sensitive.
"""
from __future__ import annotations

import logging
import sys

import structlog

from .config import settings

_SENSITIVE = (
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "fernet",
    "encrypted",
)


def _redact(_logger, _method, event_dict):
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in _SENSITIVE):
            event_dict[key] = "***redacted***"
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact,
    ]
    if settings.is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
