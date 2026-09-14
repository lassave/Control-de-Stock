"""Operarios y los tokens con los que se vinculan sus dispositivos.

Los operarios son globales, no de una sesión: se dan de alta una vez y se
reutilizan en todos los inventarios.
"""

import secrets
import sqlite3

# Se enumeran las columnas en vez de usar «*» para que el PIN no viaje en
# cada respuesta: el panel necesita el token, para armar el QR, pero nunca
# el PIN.
CAMPOS = "id, nombre, token_dispositivo, activo"


def crear(con, nombre, pin=None):
    """Da de alta un operario y le asigna su token de vinculación.

    Si el nombre corresponde a alguien desactivado, lo reactiva con un token
    nuevo. Sin esto, desactivar a una persona dejaba su nombre bloqueado para
    siempre y sin forma de volver a darla de alta. El token se renueva a
    propósito: el celular que quedó desvinculado no tiene que revivir solo.
    """
    nombre = (nombre or "").strip() if isinstance(nombre, str) else ""
    if not nombre:
        raise ValueError("El operario necesita un nombre")

    existente = con.execute(
        "SELECT id, activo FROM operario WHERE nombre = ?", (nombre,)
    ).fetchone()

    if existente and existente["activo"]:
        raise ValueError(f"Ya existe un operario llamado «{nombre}»")

    token = secrets.token_urlsafe(32)

    try:
        with con:
            if existente:
                con.execute(
                    "UPDATE operario SET activo = 1, pin = ?, token_dispositivo = ? "
                    "WHERE id = ?",
                    (pin, token, existente["id"]),
                )
                operario_id = existente["id"]
            else:
                cursor = con.execute(
                    "INSERT INTO operario (nombre, pin, token_dispositivo) "
                    "VALUES (?, ?, ?)",
                    (nombre, pin, token),
                )
                operario_id = cursor.lastrowid
    except sqlite3.IntegrityError as error:
        # Solo puede pasar si otro hilo dio de alta el mismo nombre entre la
        # consulta y la escritura. Cualquier otra violación se deja pasar tal
        # cual: convertirla en «ya existe» mentiría sobre lo que ocurrió.
        if "operario.nombre" in str(error):
            raise ValueError(f"Ya existe un operario llamado «{nombre}»") from error
        raise

    return obtener(con, operario_id)


def obtener(con, operario_id):
    fila = con.execute(
        f"SELECT {CAMPOS} FROM operario WHERE id = ?", (operario_id,)
    ).fetchone()
    return dict(fila) if fila else None


def listar(con):
    filas = con.execute(
        f"SELECT {CAMPOS} FROM operario WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [dict(fila) for fila in filas]


def por_token(con, token):
    fila = con.execute(
        f"SELECT {CAMPOS} FROM operario WHERE token_dispositivo = ? AND activo = 1",
        (token,),
    ).fetchone()
    return dict(fila) if fila else None


def desactivar(con, operario_id):
    with con:
        cursor = con.execute(
            "UPDATE operario SET activo = 0 WHERE id = ?", (operario_id,)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No existe el operario {operario_id}")


def listar_para_identificar(con):
    """Nombres activos para elegir al identificarse sin QR.

    Nunca el PIN ni el token: esta lista arma un botón por nombre en el
    celular, no vincula a nadie por sí sola.
    """
    filas = con.execute(
        "SELECT id, nombre, pin FROM operario WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [
        {"id": fila["id"], "nombre": fila["nombre"], "tiene_pin": bool(fila["pin"])}
        for fila in filas
    ]


def para_identificar(con, nombre):
    """El operario por nombre, con su PIN y su token.

    A diferencia de `listar_para_identificar` y `por_token`, esta sí trae el
    PIN: es la única consulta que lo necesita, para compararlo contra el que
    mandó el celular. No sale de acá hacia ninguna respuesta HTTP.
    """
    fila = con.execute(
        "SELECT id, nombre, pin, token_dispositivo FROM operario "
        "WHERE nombre = ? AND activo = 1",
        (nombre,),
    ).fetchone()
    return dict(fila) if fila else None
