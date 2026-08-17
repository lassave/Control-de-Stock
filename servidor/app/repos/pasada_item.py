"""Qué SKU entran en una pasada parcial: un recuento.

Existía en el esquema desde el primer día del proyecto, sin código propio.
Una pasada sin ninguna fila acá es una pasada general —acepta cualquier
artículo del maestro—; una con al menos una es un recuento, y solo acepta
los marcados.
"""


def agregar(con, pasada_id, articulo_ids):
    """Marca esos artículos para la pasada. Reintentar con los mismos ids
    no duplica ni falla."""
    with con:
        for articulo_id in articulo_ids:
            con.execute(
                "INSERT OR IGNORE INTO pasada_item (pasada_id, articulo_id) "
                "VALUES (?, ?)",
                (pasada_id, articulo_id),
            )


def es_parcial(con, pasada_id):
    """Si la pasada tiene algún SKU marcado: es un recuento, no la general."""
    fila = con.execute(
        "SELECT 1 FROM pasada_item WHERE pasada_id = ? LIMIT 1",
        (pasada_id,),
    ).fetchone()
    return fila is not None


def contiene(con, pasada_id, articulo_id):
    fila = con.execute(
        "SELECT 1 FROM pasada_item WHERE pasada_id = ? AND articulo_id = ?",
        (pasada_id, articulo_id),
    ).fetchone()
    return fila is not None


def de_pasada(con, pasada_id):
    filas = con.execute(
        "SELECT articulo_id FROM pasada_item WHERE pasada_id = ? "
        "ORDER BY articulo_id",
        (pasada_id,),
    ).fetchall()
    return [fila["articulo_id"] for fila in filas]
