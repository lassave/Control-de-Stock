"""Cuentas del panel y sus sesiones de login.

Separado de `operarios.py` a propósito: el operario que escanea códigos
y la cuenta que administra el panel son identidades sin relación entre
sí, y compartir tabla o vocabulario las confundiría.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from app import reloj
from app.servicios import autenticacion

CAMPOS_PUBLICOS = "id, usuario, activo"
DIAS_DE_SESION = 30


def crear(con, usuario, clave, rol="menor"):
    """Da de alta una cuenta. Solo el superusuario tiene TOTP —las cuentas
    de rol menor no lo necesitan: el login no lo pide para nadie, y ellas
    se recuperan por mail, no por segundo factor.

    Si genera un secreto, lo devuelve en texto plano: es la única vez que
    existe fuera de la base. Nadie vuelve a pedirlo después.
    """
    usuario = (usuario or "").strip() if isinstance(usuario, str) else ""
    if not usuario:
        raise ValueError("La cuenta necesita un usuario")
    if not clave or len(clave) < 8:
        raise ValueError("La contraseña tiene que tener al menos 8 caracteres")

    clave_hash = autenticacion.hashear_clave(clave)
    secreto = autenticacion.generar_secreto_totp() if rol == "superusuario" else None

    try:
        with con:
            cursor = con.execute(
                "INSERT INTO cuenta_panel (usuario, clave_hash, otp_secreto, rol) "
                "VALUES (?, ?, ?, ?)",
                (usuario, clave_hash, secreto, rol),
            )
            cuenta_id = cursor.lastrowid
    except sqlite3.IntegrityError as error:
        if "cuenta_panel.usuario" in str(error):
            raise ValueError(f"Ya existe una cuenta con el usuario «{usuario}»") from error
        raise

    return {"id": cuenta_id, "usuario": usuario, "otp_secreto": secreto, "rol": rol}


def por_usuario(con, usuario):
    """Con clave_hash, otp_secreto y rol: solo para login/recuperación, nunca se expone."""
    fila = con.execute(
        "SELECT id, usuario, clave_hash, otp_secreto, rol FROM cuenta_panel "
        "WHERE usuario = ? AND activo = 1",
        (usuario,),
    ).fetchone()
    return dict(fila) if fila else None


def listar(con):
    filas = con.execute(
        f"SELECT {CAMPOS_PUBLICOS} FROM cuenta_panel WHERE activo = 1 ORDER BY usuario"
    ).fetchall()
    return [dict(fila) for fila in filas]


def desactivar(con, cuenta_id):
    with con:
        cursor = con.execute(
            "UPDATE cuenta_panel SET activo = 0 WHERE id = ?", (cuenta_id,)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No existe la cuenta {cuenta_id}")


def crear_sesion(con, cuenta_id):
    token = secrets.token_urlsafe(32)
    with con:
        con.execute(
            "INSERT INTO sesion_panel (token, cuenta_id, creado_en) VALUES (?, ?, ?)",
            (token, cuenta_id, reloj.ahora()),
        )
    return token


def sesion_valida(con, token):
    """La cuenta dueña de esta sesión, o None si no existe, venció, o la cuenta se dio de baja."""
    fila = con.execute(
        "SELECT s.creado_en, c.id, c.usuario, c.activo "
        "FROM sesion_panel s JOIN cuenta_panel c ON c.id = s.cuenta_id "
        "WHERE s.token = ?",
        (token,),
    ).fetchone()
    if fila is None or not fila["activo"]:
        return None

    creado = datetime.strptime(fila["creado_en"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    if datetime.now(timezone.utc) - creado > timedelta(days=DIAS_DE_SESION):
        return None

    return {"id": fila["id"], "usuario": fila["usuario"]}


def borrar_sesion(con, token):
    with con:
        con.execute("DELETE FROM sesion_panel WHERE token = ?", (token,))
