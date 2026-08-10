"""Sesiones de inventario y sus pasadas de conteo."""

from app import reloj


def etiqueta_pasada(numero):
    """La etiqueta visible de una pasada. El numero interno y el visible coinciden."""
    return f"Conteo {numero}"


def sesion_abierta(con):
    fila = con.execute(
        "SELECT * FROM sesion WHERE estado = 'abierta' LIMIT 1"
    ).fetchone()
    return dict(fila) if fila else None


def crear(con, nombre):
    """Crea la sesión y abre su Conteo 1.

    Solo puede haber una sesión abierta a la vez: los dispositivos se
    vinculan a la sesión abierta y con dos no habría forma de saber a
    cuál pertenece un conteo.
    """
    if sesion_abierta(con) is not None:
        raise ValueError("Ya hay una sesión abierta. Cerrala antes de crear otra.")

    ahora = reloj.ahora()
    cursor = con.execute(
        "INSERT INTO sesion (nombre, fecha_creacion) VALUES (?, ?)",
        (nombre, ahora),
    )
    sesion_id = cursor.lastrowid

    con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 1, ?)",
        (sesion_id, ahora),
    )
    con.commit()
    return sesion_id


def obtener(con, sesion_id):
    fila = con.execute("SELECT * FROM sesion WHERE id = ?", (sesion_id,)).fetchone()
    if fila is None:
        raise ValueError(f"No existe la sesión {sesion_id}")
    return dict(fila)


def listar(con):
    filas = con.execute("SELECT * FROM sesion ORDER BY id DESC").fetchall()
    return [dict(fila) for fila in filas]


def pasada_abierta(con, sesion_id):
    fila = con.execute(
        "SELECT * FROM pasada WHERE sesion_id = ? AND estado = 'abierta' "
        "ORDER BY numero DESC LIMIT 1",
        (sesion_id,),
    ).fetchone()
    if fila is None:
        raise ValueError(f"La sesión {sesion_id} no tiene ninguna pasada abierta")

    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def cerrar(con, sesion_id):
    ahora = reloj.ahora()
    con.execute(
        "UPDATE pasada SET estado = 'cerrada', fecha_cierre = ? "
        "WHERE sesion_id = ? AND estado = 'abierta'",
        (ahora, sesion_id),
    )
    con.execute("UPDATE sesion SET estado = 'cerrada' WHERE id = ?", (sesion_id,))
    con.commit()


def fijar_tolerancia(con, sesion_id, pct, min_abs_milesimas):
    con.execute(
        "UPDATE sesion SET tolerancia_pct = ?, tolerancia_min_abs = ? WHERE id = ?",
        (pct, min_abs_milesimas, sesion_id),
    )
    con.commit()
