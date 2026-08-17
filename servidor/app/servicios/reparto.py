"""A quién le toca cada ubicación y quién contó qué, fila por artículo.

Reusa `tablero.filas` para el estado y el total: son los mismos cálculos
—anulaciones descartadas de a pares, valor de la última pasada contada— y
escribirlos de nuevo acá garantizaría que tarde o temprano esta pestaña y el
tablero digan cosas distintas del mismo SKU.
"""

from app.repos import sesiones
from app.servicios.tablero import CTE_VIGENTES, filas as filas_del_tablero


def _asignados_por_articulo(con, sesion_id):
    """Operarios con esa ubicación asignada, en la última pasada de la sesión.

    La última pasada y no la abierta a propósito: quién tiene qué se mira
    sobre todo cuando el inventario ya cerró, y `pasada_abierta` tiraría
    `ValueError` justo en ese momento.
    """
    sesion = sesiones.obtener(con, sesion_id)
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
        (pasada["id"], sesion["id"]),
    ).fetchall()

    resultado = {}
    for fila in filas:
        resultado.setdefault(fila["articulo_id"], []).append(fila["nombre"])
    return resultado


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
    asignados = _asignados_por_articulo(con, sesion_id)
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
