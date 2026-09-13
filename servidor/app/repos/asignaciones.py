"""A quién le toca cada ubicación, pasada por pasada.

No es historial de conteos: es logística de antes de contar. Reemplazar el
reparto no reescribe ningún hecho — los conteos ya guardados conservan el
`fuera_asignacion` que tenían al guardarse (ver `repos/conteos.py`).
"""

from app import reloj
from app.repos import operarios, proyectos


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


def de_operario_en_proyecto(con, proyecto_id, operario_id):
    """Lo que le toca al operario en su pasada activa de este proyecto.

    Tira `ValueError` si no tiene ninguna pasada activa. Es a propósito:
    quien pregunte tiene que decidir qué contestar, y para el celular la
    respuesta correcta no es «no te toca nada» —eso le borraría el reparto
    que ya tiene bajado— sino «ahora no puedo contestarte».

    `es_parcial` y `articulos_permitidos` le dicen al celular si está en un
    recuento y, si es así, qué puede contar: sin eso no puede bloquear el
    escaneo localmente, y el conteo tiene que andar sin señal.
    """
    from app.repos import pasada_item

    pasada = proyectos.pasada_activa_de_operario(con, proyecto_id, operario_id)
    es_parcial = pasada_item.es_parcial(con, pasada["id"])

    return {
        "pasada_id": pasada["id"],
        "pasada_numero": pasada["numero"],
        "pasada_etiqueta": pasada["etiqueta"],
        "es_parcial": es_parcial,
        "articulos_permitidos": pasada_item.de_pasada(con, pasada["id"]) if es_parcial else [],
        "ubicaciones": de_operario(con, pasada["id"], operario_id),
    }


def asignados_por_articulo(con, proyecto_id):
    """A quién le toca cada artículo, entre todas las pasadas abiertas.

    Compartida entre `tablero` y `reparto`: la misma pregunta —quién es
    responsable de este artículo— tiene que contestarse igual en los dos
    lugares donde se muestra.

    Con recuentos concurrentes, un artículo puede tener más de un
    responsable a la vez: quien lo tiene asignado en la pasada general
    —que aplica a toda la ubicación— y quien lo tiene en un recuento, pero
    solo si ese artículo puntual está marcado ahí. La asignación de un
    recuento a una ubicación no se derrama sobre los artículos que ese
    recuento no incluye.

    Con el proyecto ya cerrado no queda ninguna pasada abierta que mirar, y
    quién hizo qué se revisa sobre todo en ese momento: ahí se cae a la
    última pasada del proyecto, abierta o no, como funcionaba antes de que
    existieran los recuentos concurrentes.
    """
    if proyectos.pasadas_abiertas(con, proyecto_id):
        condicion_pasada = "p.proyecto_id = ? AND p.estado = 'abierta'"
        parametro_pasada = proyecto_id
    else:
        ultima = proyectos.ultima_pasada(con, proyecto_id)
        if ultima is None:
            return {}
        condicion_pasada = "p.id = ?"
        parametro_pasada = ultima["id"]

    filas = con.execute(
        f"""
        SELECT a.id AS articulo_id, o.nombre
        FROM articulo a
        JOIN asignacion s ON s.ubicacion = a.ubicacion
        JOIN pasada p ON p.id = s.pasada_id AND {condicion_pasada}
        JOIN operario o ON o.id = s.operario_id
        WHERE a.proyecto_id = ? AND a.fusionado_en IS NULL
          AND (
            NOT EXISTS (SELECT 1 FROM pasada_item pi WHERE pi.pasada_id = p.id)
            OR EXISTS (
                SELECT 1 FROM pasada_item pi
                WHERE pi.pasada_id = p.id AND pi.articulo_id = a.id
            )
          )
        ORDER BY a.id, o.nombre
        """,
        (parametro_pasada, proyecto_id),
    ).fetchall()

    resultado = {}
    for fila in filas:
        nombres = resultado.setdefault(fila["articulo_id"], [])
        # La misma persona puede tener asignada la ubicación tanto en la
        # general como en un recuento: no se repite su nombre.
        if fila["nombre"] not in nombres:
            nombres.append(fila["nombre"])
    return resultado


def ubicaciones_distintas(con, proyecto_id):
    """Las ubicaciones del maestro de este proyecto, para elegir qué asignar."""
    filas = con.execute(
        "SELECT DISTINCT ubicacion FROM articulo "
        "WHERE proyecto_id = ? AND fusionado_en IS NULL "
        "AND ubicacion IS NOT NULL AND ubicacion != '' "
        "ORDER BY ubicacion",
        (proyecto_id,),
    ).fetchall()
    return [fila["ubicacion"] for fila in filas]


def operarios_con_ubicaciones(con):
    """Los operarios activos, cada uno con lo que tiene asignado en **su**
    pasada activa.

    No es la misma pasada para todos: con un recuento abierto, quien está
    asignado ahí ve las ubicaciones del recuento, y quien no, las de la
    pasada general. Sin proyecto abierto, o sin ninguna pasada activa para un
    operario en particular, esa persona queda con la lista vacía — es una
    respuesta, no un error que tenga que romper el endpoint para todos.
    """
    lista = operarios.listar(con)

    proyecto = proyectos.proyecto_abierto(con)
    if proyecto is None:
        for operario in lista:
            operario["ubicaciones_asignadas"] = []
        return lista

    for operario in lista:
        try:
            pasada = proyectos.pasada_activa_de_operario(con, proyecto["id"], operario["id"])
            operario["ubicaciones_asignadas"] = de_operario(con, pasada["id"], operario["id"])
        except ValueError:
            operario["ubicaciones_asignadas"] = []
    return lista
