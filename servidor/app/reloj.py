"""Hora del servidor, centralizada para poder fijarla en los tests."""

from datetime import datetime, timezone


def ahora():
    """Timestamp ISO 8601 en UTC: 2026-08-10T14:32:05Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
