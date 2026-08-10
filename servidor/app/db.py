"""Acceso a la base SQLite: conexión y creación del esquema."""

import sqlite3
from pathlib import Path

RUTA_ESQUEMA = Path(__file__).parent / "esquema.sql"


def conectar(ruta):
    """Abre la base y devuelve filas accesibles por nombre de columna."""
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def crear_esquema(con):
    """Crea las tablas si no existen. Se puede ejecutar cuantas veces haga falta."""
    con.executescript(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    con.commit()
