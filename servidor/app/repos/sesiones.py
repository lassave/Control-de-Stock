"""Sesiones de inventario y sus pasadas de conteo."""

from app import reloj
from app.repos import pasada_item as pasada_item_repo


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

    # Las dos escrituras van juntas o no va ninguna: una sesión sin pasada
    # no se puede usar para contar ni se puede cerrar.
    with con:
        cursor = con.execute(
            "INSERT INTO sesion (nombre, fecha_creacion) VALUES (?, ?)",
            (nombre, ahora),
        )
        sesion_id = cursor.lastrowid

        con.execute(
            "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 1, ?)",
            (sesion_id, ahora),
        )

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


def ultima_pasada(con, sesion_id):
    """La pasada de mayor número, esté abierta o cerrada. `None` si no hay.

    `pasada_abierta` no sirve para mirar hacia atrás: tira `ValueError` en
    cuanto la sesión se cierra, que es justo cuando alguien revisa quién
    contó qué. Acá una sesión cerrada es un caso normal, no un error.
    """
    fila = con.execute(
        "SELECT * FROM pasada WHERE sesion_id = ? ORDER BY numero DESC LIMIT 1",
        (sesion_id,),
    ).fetchone()
    if fila is None:
        return None

    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def obtener_pasada(con, sesion_id, pasada_id):
    """Una pasada puntual de la sesión, o `None` si no existe o es de otra."""
    fila = con.execute(
        "SELECT * FROM pasada WHERE id = ? AND sesion_id = ?",
        (pasada_id, sesion_id),
    ).fetchone()
    if fila is None:
        return None
    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def pasadas_abiertas(con, sesion_id):
    """Todas las pasadas abiertas de la sesión, ordenadas por número.

    Con una sola pasada nunca importó si había una o varias; con recuentos
    concurrentes, puede haber más de una a la vez.
    """
    filas = con.execute(
        "SELECT * FROM pasada WHERE sesion_id = ? AND estado = 'abierta' "
        "ORDER BY numero",
        (sesion_id,),
    ).fetchall()
    pasadas = [dict(fila) for fila in filas]
    for pasada in pasadas:
        pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasadas


def pasada_general_abierta(con, sesion_id):
    """La pasada abierta de menor número que no es un recuento.

    Un recuento tiene filas en `pasada_item`; la general nunca las tiene.
    Devuelve `None` si no queda ninguna pasada general abierta —puede pasar
    si se cerró y solo quedan recuentos parciales abiertos—.
    """
    for pasada in pasadas_abiertas(con, sesion_id):
        if not pasada_item_repo.es_parcial(con, pasada["id"]):
            return pasada
    return None


def pasada_activa_de_operario(con, sesion_id, operario_id):
    """En qué pasada está trabajando este operario ahora mismo.

    1. Si tiene una asignación en un recuento abierto, esa es su pasada
       activa —un operario nunca puede tener asignación en más de un
       recuento abierto a la vez, eso se impide al asignar (ver
       `repos/asignaciones.py`), así que acá no hay ambigüedad que
       desempatar.
    2. Si no, la pasada general abierta.
    3. Si no hay ninguna de las dos, `ValueError`: no se lo mete en una
       pasada que no le corresponde.
    """
    from app.repos import asignaciones as asignaciones_repo

    for pasada in pasadas_abiertas(con, sesion_id):
        if not pasada_item_repo.es_parcial(con, pasada["id"]):
            continue
        if asignaciones_repo.de_operario(con, pasada["id"], operario_id):
            return pasada

    general = pasada_general_abierta(con, sesion_id)
    if general is not None:
        return general

    raise ValueError(
        f"El operario {operario_id} no tiene ninguna pasada activa en la "
        f"sesión {sesion_id}"
    )


def cerrar(con, sesion_id):
    obtener(con, sesion_id)  # falla con un mensaje claro si no existe
    ahora = reloj.ahora()

    with con:
        con.execute(
            "UPDATE pasada SET estado = 'cerrada', fecha_cierre = ? "
            "WHERE sesion_id = ? AND estado = 'abierta'",
            (ahora, sesion_id),
        )
        con.execute("UPDATE sesion SET estado = 'cerrada' WHERE id = ?", (sesion_id,))


def fijar_tolerancia(con, sesion_id, pct, min_abs_milesimas):
    obtener(con, sesion_id)

    # La base lo rechazaría igual, pero con un mensaje de SQLite que no le
    # dice nada a quien está corriendo el inventario.
    if not isinstance(min_abs_milesimas, int) or isinstance(min_abs_milesimas, bool):
        raise ValueError(
            "La tolerancia mínima se expresa en milésimas, con un número entero."
        )

    with con:
        con.execute(
            "UPDATE sesion SET tolerancia_pct = ?, tolerancia_min_abs = ? WHERE id = ?",
            (pct, min_abs_milesimas, sesion_id),
        )
