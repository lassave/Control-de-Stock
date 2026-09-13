"""Proyectos de inventario y sus pasadas de conteo."""

from app import reloj
from app.repos import pasada_item as pasada_item_repo


def etiqueta_pasada(numero):
    """La etiqueta visible de una pasada. El numero interno y el visible coinciden."""
    return f"Conteo {numero}"


def proyecto_abierto(con):
    fila = con.execute(
        "SELECT * FROM proyecto WHERE estado = 'abierta' LIMIT 1"
    ).fetchone()
    return dict(fila) if fila else None


def crear(con, nombre):
    """Crea el proyecto y abre su Conteo 1.

    Solo puede haber un proyecto abierto a la vez: los dispositivos se
    vinculan al proyecto abierto y con dos no habría forma de saber a
    cuál pertenece un conteo.
    """
    if proyecto_abierto(con) is not None:
        raise ValueError("Ya hay un proyecto abierto. Cerralo antes de crear otro.")

    ahora = reloj.ahora()

    # Las dos escrituras van juntas o no va ninguna: un proyecto sin pasada
    # no se puede usar para contar ni se puede cerrar.
    with con:
        cursor = con.execute(
            "INSERT INTO proyecto (nombre, fecha_creacion) VALUES (?, ?)",
            (nombre, ahora),
        )
        proyecto_id = cursor.lastrowid

        con.execute(
            "INSERT INTO pasada (proyecto_id, numero, fecha_apertura) VALUES (?, 1, ?)",
            (proyecto_id, ahora),
        )

    return proyecto_id


def obtener(con, proyecto_id):
    fila = con.execute("SELECT * FROM proyecto WHERE id = ?", (proyecto_id,)).fetchone()
    if fila is None:
        raise ValueError(f"No existe el proyecto {proyecto_id}")
    return dict(fila)


def listar(con):
    filas = con.execute("SELECT * FROM proyecto ORDER BY id DESC").fetchall()
    return [dict(fila) for fila in filas]


def pasada_abierta(con, proyecto_id):
    fila = con.execute(
        "SELECT * FROM pasada WHERE proyecto_id = ? AND estado = 'abierta' "
        "ORDER BY numero DESC LIMIT 1",
        (proyecto_id,),
    ).fetchone()
    if fila is None:
        raise ValueError(f"El proyecto {proyecto_id} no tiene ninguna pasada abierta")

    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def ultima_pasada(con, proyecto_id):
    """La pasada de mayor número, esté abierta o cerrada. `None` si no hay.

    `pasada_abierta` no sirve para mirar hacia atrás: tira `ValueError` en
    cuanto el proyecto se cierra, que es justo cuando alguien revisa quién
    contó qué. Acá un proyecto cerrado es un caso normal, no un error.
    """
    fila = con.execute(
        "SELECT * FROM pasada WHERE proyecto_id = ? ORDER BY numero DESC LIMIT 1",
        (proyecto_id,),
    ).fetchone()
    if fila is None:
        return None

    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def obtener_pasada(con, proyecto_id, pasada_id):
    """Una pasada puntual del proyecto, o `None` si no existe o es de otro."""
    fila = con.execute(
        "SELECT * FROM pasada WHERE id = ? AND proyecto_id = ?",
        (pasada_id, proyecto_id),
    ).fetchone()
    if fila is None:
        return None
    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def pasadas_abiertas(con, proyecto_id):
    """Todas las pasadas abiertas del proyecto, ordenadas por número.

    Con una sola pasada nunca importó si había una o varias; con recuentos
    concurrentes, puede haber más de una a la vez.
    """
    filas = con.execute(
        "SELECT * FROM pasada WHERE proyecto_id = ? AND estado = 'abierta' "
        "ORDER BY numero",
        (proyecto_id,),
    ).fetchall()
    pasadas = [dict(fila) for fila in filas]
    for pasada in pasadas:
        pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasadas


def pasada_general_abierta(con, proyecto_id):
    """La pasada abierta de menor número que no es un recuento.

    Un recuento tiene filas en `pasada_item`; la general nunca las tiene.
    Devuelve `None` si no queda ninguna pasada general abierta —puede pasar
    si se cerró y solo quedan recuentos parciales abiertos—.
    """
    for pasada in pasadas_abiertas(con, proyecto_id):
        if not pasada_item_repo.es_parcial(con, pasada["id"]):
            return pasada
    return None


def pasada_activa_de_operario(con, proyecto_id, operario_id):
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

    for pasada in pasadas_abiertas(con, proyecto_id):
        if not pasada_item_repo.es_parcial(con, pasada["id"]):
            continue
        if asignaciones_repo.de_operario(con, pasada["id"], operario_id):
            return pasada

    general = pasada_general_abierta(con, proyecto_id)
    if general is not None:
        return general

    raise ValueError(
        f"El operario {operario_id} no tiene ninguna pasada activa en el "
        f"proyecto {proyecto_id}"
    )


def listar_pasadas(con, proyecto_id):
    """Todas las pasadas del proyecto, marcando cuáles son recuentos."""
    filas = con.execute(
        "SELECT * FROM pasada WHERE proyecto_id = ? ORDER BY numero", (proyecto_id,)
    ).fetchall()
    pasadas = [dict(fila) for fila in filas]
    for pasada in pasadas:
        pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
        articulos = pasada_item_repo.de_pasada(con, pasada["id"])
        pasada["es_parcial"] = bool(articulos)
        pasada["cantidad_sku"] = len(articulos)
    return pasadas


def abrir_pasada(con, proyecto_id, articulo_ids):
    """Abre un recuento nuevo con esos SKU marcados en `pasada_item`.

    Transaccional: la pasada y sus filas de `pasada_item` se graban juntas
    o no se graba nada.
    """
    proyecto = obtener(con, proyecto_id)
    if proyecto["estado"] != "abierta":
        raise ValueError(f"El proyecto {proyecto_id} está cerrado")
    if not articulo_ids:
        raise ValueError("Hay que marcar al menos un SKU para el recuento")

    ahora = reloj.ahora()
    with con:
        siguiente_numero = con.execute(
            "SELECT COALESCE(MAX(numero), 0) + 1 FROM pasada WHERE proyecto_id = ?",
            (proyecto_id,),
        ).fetchone()[0]
        cursor = con.execute(
            "INSERT INTO pasada (proyecto_id, numero, fecha_apertura) VALUES (?, ?, ?)",
            (proyecto_id, siguiente_numero, ahora),
        )
        pasada_id = cursor.lastrowid
        for articulo_id in articulo_ids:
            con.execute(
                "INSERT OR IGNORE INTO pasada_item (pasada_id, articulo_id) VALUES (?, ?)",
                (pasada_id, articulo_id),
            )

    pasada = obtener_pasada(con, proyecto_id, pasada_id)
    pasada["es_parcial"] = True
    pasada["cantidad_sku"] = len(pasada_item_repo.de_pasada(con, pasada_id))
    return pasada


def borrar_pasada(con, proyecto_id, pasada_id):
    """Borra un recuento abierto por error, antes de que nadie cuente ahí.

    Solo mientras no tiene ningún conteo: en cuanto hay uno, es historial —
    corregirlo es una anulación, no un borrado, la misma regla que rige
    cualquier otro conteo. La pasada general (Conteo 1) tampoco se puede
    borrar: siempre tiene que quedar una pasada donde contar.
    """
    pasada = obtener_pasada(con, proyecto_id, pasada_id)
    if pasada is None:
        raise ValueError(f"No existe la pasada {pasada_id} en este proyecto")

    if not pasada_item_repo.es_parcial(con, pasada_id):
        raise ValueError("No se puede borrar la pasada general del proyecto")

    tiene_conteos = con.execute(
        "SELECT 1 FROM conteo WHERE pasada_id = ? LIMIT 1", (pasada_id,)
    ).fetchone() is not None
    if tiene_conteos:
        raise ValueError(
            "Ya tiene conteos cargados: no se puede borrar, hay que dejarla como está"
        )

    with con:
        con.execute("DELETE FROM pasada_item WHERE pasada_id = ?", (pasada_id,))
        con.execute("DELETE FROM asignacion WHERE pasada_id = ?", (pasada_id,))
        con.execute("DELETE FROM pasada WHERE id = ?", (pasada_id,))


def cerrar(con, proyecto_id):
    obtener(con, proyecto_id)  # falla con un mensaje claro si no existe
    ahora = reloj.ahora()

    with con:
        con.execute(
            "UPDATE pasada SET estado = 'cerrada', fecha_cierre = ? "
            "WHERE proyecto_id = ? AND estado = 'abierta'",
            (ahora, proyecto_id),
        )
        con.execute("UPDATE proyecto SET estado = 'cerrada' WHERE id = ?", (proyecto_id,))


def fijar_tolerancia(con, proyecto_id, pct, min_abs_milesimas):
    obtener(con, proyecto_id)

    # La base lo rechazaría igual, pero con un mensaje de SQLite que no le
    # dice nada a quien está corriendo el inventario.
    if not isinstance(min_abs_milesimas, int) or isinstance(min_abs_milesimas, bool):
        raise ValueError(
            "La tolerancia mínima se expresa en milésimas, con un número entero."
        )

    with con:
        con.execute(
            "UPDATE proyecto SET tolerancia_pct = ?, tolerancia_min_abs = ? WHERE id = ?",
            (pct, min_abs_milesimas, proyecto_id),
        )
