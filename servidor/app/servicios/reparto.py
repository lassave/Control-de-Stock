"""A quién le toca cada ubicación y quién contó qué, fila por artículo.

Reusa `tablero.filas` para el estado y el total: son los mismos cálculos
—anulaciones descartadas de a pares, valor de la última pasada contada— y
escribirlos de nuevo acá garantizaría que tarde o temprano esta pestaña y el
tablero digan cosas distintas del mismo SKU.
"""

from app.repos import asignaciones, operarios, pasada_item, proyectos
from app.servicios.tablero import CTE_VIGENTES, filas as filas_del_tablero


def _contadores_por_articulo(con, proyecto_id):
    """Operarios que contaron cada artículo, en su pasada vigente.

    La misma definición de «vigente» que usa el tablero: descarta las
    anulaciones de a pares y solo mira la última pasada en que se contó.
    `GROUP BY ... o.id` deduplica a quien contó el mismo artículo más de
    una vez.
    """
    filas = con.execute(
        CTE_VIGENTES + """
        SELECT v.articulo_id, o.nombre
        FROM vigentes v
        JOIN ultima_pasada u
            ON u.articulo_id = v.articulo_id AND u.numero = v.pasada_numero
        JOIN operario o ON o.id = v.operario_id
        JOIN articulo a ON a.id = v.articulo_id
        WHERE a.proyecto_id = ?
        GROUP BY v.articulo_id, o.id
        ORDER BY v.articulo_id, o.nombre
        """,
        (proyecto_id,),
    ).fetchall()

    resultado = {}
    for fila in filas:
        resultado.setdefault(fila["articulo_id"], []).append(fila["nombre"])
    return resultado


def filas(con, proyecto_id, filtros=None):
    """Una fila por artículo: ubicación, a quién le toca, quién lo contó.

    No lleva `stock_sistema` ni `costo_unitario`: esta pestaña se exporta y
    el CSV de «quién hizo qué» circula, sin necesidad de que los costos
    viajen en el archivo.
    """
    base = filas_del_tablero(con, proyecto_id, filtros)
    asignados = asignaciones.asignados_por_articulo(con, proyecto_id)
    contadores = _contadores_por_articulo(con, proyecto_id)

    return [
        {
            "ubicacion": fila["ubicacion"],
            "id_orden": fila["id_orden"],
            "sku": fila["sku"],
            "descripcion": fila["descripcion"],
            "asignado_a": asignados.get(fila["id"], []),
            "contado_por": contadores.get(fila["id"], []),
            "contado": fila["ultimo_conteo"],
            "estado": fila["estado"],
        }
        for fila in base
    ]


def avance_por_operario(con, proyecto_id, filtros=None):
    """El resumen de cada operario: cuánto le tocó, cuánto contó él mismo.

    «Contado» es lo que el propio operario contó, no lo que contó cualquiera
    —a diferencia de «contado_por» en `filas`—: es la misma pregunta que se
    hace la pantalla «Lo mío» del celular, aplicada a todos a la vez. Solo
    aparecen los operarios con al menos una ubicación asignada; uno sin nada
    asignado no tiene ningún resumen que mostrar.
    """
    con_ubicaciones = asignaciones.operarios_con_ubicaciones(con)
    todas = filas(con, proyecto_id, filtros)

    resultado = []
    for operario in con_ubicaciones:
        ubicaciones_asignadas = operario["ubicaciones_asignadas"]
        if not ubicaciones_asignadas:
            continue

        nombre = operario["nombre"]
        propias = sorted(
            (fila for fila in todas if nombre in fila["asignado_a"]),
            key=lambda fila: fila["id_orden"],
        )
        detalle = [
            {
                "ubicacion": fila["ubicacion"],
                "sku": fila["sku"],
                "descripcion": fila["descripcion"],
                "estado": fila["estado"],
                "contado": nombre in fila["contado_por"],
            }
            for fila in propias
        ]
        total = len(detalle)
        contados = sum(1 for item in detalle if item["contado"])

        resultado.append({
            "operario": nombre,
            "ubicaciones": ubicaciones_asignadas,
            "total": total,
            "contados": contados,
            "sin_contar": total - contados,
            "avance_pct": round(contados / total * 100, 1) if total else 0.0,
            "detalle": detalle,
        })

    return resultado


def avance_de_pasada(con, proyecto_id, pasada_id):
    """El progreso de un recuento puntual, operario por operario.

    Distinto de `avance_por_operario`, que mira el valor vigente de hoy —la
    pasada más reciente en que cada SKU fue contado—: acá importa
    específicamente esta pasada, no la que terminó ganando después. Un SKU
    contado en el Conteo 1 no hace avanzar un recuento que se abrió después
    sobre ese mismo SKU.
    """
    pasada = proyectos.obtener_pasada(con, proyecto_id, pasada_id)
    if pasada is None:
        raise ValueError(f"No existe la pasada {pasada_id} en este proyecto")

    articulos_de_la_pasada = pasada_item.de_pasada(con, pasada_id)
    if not articulos_de_la_pasada:
        return []

    ubicacion_de = {
        fila["id"]: fila["ubicacion"]
        for fila in con.execute(
            "SELECT id, ubicacion FROM articulo WHERE proyecto_id = ? AND fusionado_en IS NULL",
            (proyecto_id,),
        ).fetchall()
    }

    # Neta las anulaciones de a pares, igual que CTE_VIGENTES: acá la
    # pregunta es «se contó en esta pasada», no «cuál es el valor vigente».
    contados = {
        fila["articulo_id"]
        for fila in con.execute(
            "SELECT DISTINCT articulo_id FROM conteo WHERE pasada_id = ? "
            "AND anula_uuid IS NULL AND uuid NOT IN "
            "(SELECT anula_uuid FROM conteo WHERE anula_uuid IS NOT NULL)",
            (pasada_id,),
        ).fetchall()
    }

    operario_ids = [
        fila["operario_id"]
        for fila in con.execute(
            "SELECT DISTINCT operario_id FROM asignacion WHERE pasada_id = ?",
            (pasada_id,),
        ).fetchall()
    ]

    resultado = []
    for operario_id in operario_ids:
        operario = operarios.obtener(con, operario_id)
        ubicaciones_asignadas = asignaciones.de_operario(con, pasada_id, operario_id)
        propios = [
            articulo_id for articulo_id in articulos_de_la_pasada
            if ubicacion_de.get(articulo_id) in ubicaciones_asignadas
        ]
        total = len(propios)
        cantidad_contados = sum(1 for articulo_id in propios if articulo_id in contados)

        resultado.append({
            "operario": operario["nombre"],
            "ubicaciones": ubicaciones_asignadas,
            "total": total,
            "contados": cantidad_contados,
            "sin_contar": total - cantidad_contados,
            "avance_pct": round(cantidad_contados / total * 100, 1) if total else 0.0,
        })

    return sorted(resultado, key=lambda item: item["operario"])
