"""A quién le toca cada ubicación y quién contó qué, fila por artículo.

Reusa `tablero.filas` para el estado y el total: son los mismos cálculos
—anulaciones descartadas de a pares, valor de la última pasada contada— y
escribirlos de nuevo acá garantizaría que tarde o temprano esta pestaña y el
tablero digan cosas distintas del mismo SKU.
"""

from app.repos import asignaciones
from app.servicios.tablero import CTE_VIGENTES, filas as filas_del_tablero


def _contadores_por_articulo(con, sesion_id):
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
        WHERE a.sesion_id = ?
        GROUP BY v.articulo_id, o.id
        ORDER BY v.articulo_id, o.nombre
        """,
        (sesion_id,),
    ).fetchall()

    resultado = {}
    for fila in filas:
        resultado.setdefault(fila["articulo_id"], []).append(fila["nombre"])
    return resultado


def filas(con, sesion_id, filtros=None):
    """Una fila por artículo: ubicación, a quién le toca, quién lo contó.

    No lleva `stock_sistema` ni `costo_unitario`: esta pestaña se exporta y
    el CSV de «quién hizo qué» circula, sin necesidad de que los costos
    viajen en el archivo.
    """
    base = filas_del_tablero(con, sesion_id, filtros)
    asignados = asignaciones.asignados_por_articulo(con, sesion_id)
    contadores = _contadores_por_articulo(con, sesion_id)

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


def avance_por_operario(con, sesion_id, filtros=None):
    """El resumen de cada operario: cuánto le tocó, cuánto contó él mismo.

    «Contado» es lo que el propio operario contó, no lo que contó cualquiera
    —a diferencia de «contado_por» en `filas`—: es la misma pregunta que se
    hace la pantalla «Lo mío» del celular, aplicada a todos a la vez. Solo
    aparecen los operarios con al menos una ubicación asignada; uno sin nada
    asignado no tiene ningún resumen que mostrar.
    """
    con_ubicaciones = asignaciones.operarios_con_ubicaciones(con)
    todas = filas(con, sesion_id, filtros)

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
