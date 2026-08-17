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
        # executemany no existe en ConexionPorHilo: son pocos registros,
        # un execute por fila alcanza.
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


def de_operario_en_sesion(con, sesion_id, operario_id):
    """Lo que le toca al operario en su pasada activa de esta sesión.

    Tira `ValueError` si no tiene ninguna pasada activa. Es a propósito:
    quien pregunte tiene que decidir qué contestar, y para el celular la
    respuesta correcta no es «no te toca nada» —eso le borraría el reparto
    que ya tiene bajado— sino «ahora no puedo contestarte».

    `es_parcial` y `articulos_permitidos` le dicen al celular si está en un
    recuento y, si es así, qué puede contar: sin eso no puede bloquear el
    escaneo localmente, y el conteo tiene que andar sin señal.
    """
    from app.repos import pasada_item

    pasada = sesiones.pasada_activa_de_operario(con, sesion_id, operario_id)
    es_parcial = pasada_item.es_parcial(con, pasada["id"])

    return {
        "pasada_id": pasada["id"],
        "pasada_numero": pasada["numero"],
        "pasada_etiqueta": pasada["etiqueta"],
        "es_parcial": es_parcial,
        "articulos_permitidos": pasada_item.de_pasada(con, pasada["id"]) if es_parcial else [],
        "ubicaciones": de_operario(con, pasada["id"], operario_id),
    }


def asignados_por_articulo(con, sesion_id):
    """A quién le toca cada artículo, según su ubicación, en la última pasada.

    Compartida entre `tablero` y `reparto`: la misma pregunta —quién es
    responsable de este artículo— tiene que contestarse igual en los dos
    lugares donde se muestra.
    """
    pasada = sesiones.ultima_pasada(con, sesion_id)
    if pasada is None:
        return {}

    filas = con.execute(
        """
        SELECT a.id AS articulo_id, o.nombre
        FROM articulo a
        JOIN asignacion s ON s.ubicacion = a.ubicacion AND s.pasada_id = ?
        JOIN operario o ON o.id = s.operario_id
        WHERE a.sesion_id = ? AND a.fusionado_en IS NULL
        ORDER BY a.id, o.nombre
        """,
        (pasada["id"], sesion_id),
    ).fetchall()

    resultado = {}
    for fila in filas:
        resultado.setdefault(fila["articulo_id"], []).append(fila["nombre"])
    return resultado


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
    quedan con la lista vacía. Lo mismo si la sesión está abierta pero su
    pasada no: hoy eso no pasa —crear y cerrar mueven las dos juntas— pero
    el reconteo va a abrir esa ventana, y este endpoint lo consume el panel
    entero. Una lista vacía es una respuesta; un 500 no.
    """
    lista = operarios.listar(con)

    sesion = sesiones.sesion_abierta(con)
    pasada = sesiones.ultima_pasada(con, sesion["id"]) if sesion else None
    if pasada is None or pasada["estado"] != "abierta":
        for operario in lista:
            operario["ubicaciones_asignadas"] = []
        return lista

    for operario in lista:
        operario["ubicaciones_asignadas"] = de_operario(
            con, pasada["id"], operario["id"]
        )
    return lista
