"""A quién le toca cada ubicación, pasada por pasada.

No es historial de conteos: es logística de antes de contar. Reemplazar el
reparto no reescribe ningún hecho — los conteos ya guardados conservan el
`fuera_asignacion` que tenían al guardarse (ver `repos/conteos.py`).
"""

from app import reloj
from app.repos import operarios, sesiones


def reemplazar(con, pasada_id, operario_id, ubicaciones):
    """Reemplaza el reparto completo de un operario para esta pasada."""
    ahora = reloj.ahora()
    limpias = sorted({
        u.strip() for u in ubicaciones
        if isinstance(u, str) and u.strip()
    })

    with con:
        con.execute(
            "DELETE FROM asignacion WHERE pasada_id = ? AND operario_id = ?",
            (pasada_id, operario_id),
        )
        # executemany no existe en ConexionPorHilo: son pocos registros, un execute por fila alcanza.
        for u in limpias:
            con.execute(
                "INSERT INTO asignacion (pasada_id, operario_id, ubicacion, "
                "fecha_asignacion) VALUES (?, ?, ?, ?)",
                (pasada_id, operario_id, u, ahora),
            )

    return limpias


def de_operario(con, pasada_id, operario_id):
    filas = con.execute(
        "SELECT ubicacion FROM asignacion WHERE pasada_id = ? AND operario_id = ? "
        "ORDER BY ubicacion",
        (pasada_id, operario_id),
    ).fetchall()
    return [fila["ubicacion"] for fila in filas]


def ubicaciones_distintas(con, sesion_id):
    """Las ubicaciones del maestro de esta sesión, para elegir qué asignar."""
    filas = con.execute(
        "SELECT DISTINCT ubicacion FROM articulo "
        "WHERE sesion_id = ? AND fusionado_en IS NULL "
        "AND ubicacion IS NOT NULL AND ubicacion != '' "
        "ORDER BY ubicacion",
        (sesion_id,),
    ).fetchall()
    return [fila["ubicacion"] for fila in filas]


def operarios_con_ubicaciones(con):
    """Los operarios activos, cada uno con lo que tiene asignado en la
    pasada de la sesión abierta.

    Sin sesión abierta no hay pasada a la cual asignar nada, así que todos
    quedan con la lista vacía.
    """
    lista = operarios.listar(con)

    sesion = sesiones.sesion_abierta(con)
    if sesion is None:
        for operario in lista:
            operario["ubicaciones_asignadas"] = []
        return lista

    pasada = sesiones.pasada_abierta(con, sesion["id"])
    for operario in lista:
        operario["ubicaciones_asignadas"] = de_operario(
            con, pasada["id"], operario["id"]
        )
    return lista
