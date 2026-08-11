"""Operarios y los tokens con los que se vinculan sus dispositivos.

Los operarios son globales, no de una sesión: se dan de alta una vez y se
reutilizan en todos los inventarios.
"""

import secrets
import sqlite3


def crear(con, nombre, pin=None):
    token = secrets.token_urlsafe(32)
    try:
        cursor = con.execute(
            "INSERT INTO operario (nombre, pin, token_dispositivo) VALUES (?, ?, ?)",
            (nombre, pin, token),
        )
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Ya existe un operario llamado «{nombre}»") from error

    con.commit()
    return _obtener(con, cursor.lastrowid)


def _obtener(con, operario_id):
    fila = con.execute("SELECT * FROM operario WHERE id = ?", (operario_id,)).fetchone()
    return dict(fila) if fila else None


def listar(con):
    filas = con.execute(
        "SELECT * FROM operario WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [dict(fila) for fila in filas]


def por_token(con, token):
    fila = con.execute(
        "SELECT * FROM operario WHERE token_dispositivo = ? AND activo = 1",
        (token,),
    ).fetchone()
    return dict(fila) if fila else None


def desactivar(con, operario_id):
    con.execute("UPDATE operario SET activo = 0 WHERE id = ?", (operario_id,))
    con.commit()
