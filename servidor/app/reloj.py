"""Hora del servidor, centralizada para poder fijarla en los tests."""

from datetime import datetime, timezone


def ahora():
    """Timestamp ISO 8601 en UTC: 2026-08-10T14:32:05Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def desde_epoch(segundos):
    """El mismo formato, para una fecha que ya existe: la de un archivo.

    Vive acá y no en quien la usa porque el formato de fecha del sistema
    tiene una sola fuente, y una fecha de archivo que saliera en otro
    formato se leería como si fuera de otro sistema.
    """
    return datetime.fromtimestamp(segundos, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
