"""Exportación a CSV del resumen por SKU y del detalle escaneo por escaneo.

Se usa punto y coma como separador y coma decimal, que es lo que espera
Excel en configuración regional argentina. Con coma como separador, Excel
parte las cantidades decimales en dos columnas.
"""

import csv
import io

from app import cantidades
from app.repos import sesiones
from app.servicios import tablero

COLUMNAS_RESUMEN = [
    "id_orden", "tipo", "material", "sku", "descripcion", "grupo",
    "ubicacion", "ubicacion_real", "unidad", "stock_sistema",
    "ultimo_conteo", "dif", "costo_unitario", "dif_valorizada",
    "estado", "fecha", "observaciones",
]

COLUMNAS_DETALLE = [
    "fecha", "fecha_sincronizacion", "pasada", "operario", "sku",
    "descripcion", "unidad", "cantidad", "ubicacion", "ubicacion_real",
    "observaciones", "anulado", "fuera_asignacion",
]


def _milesimas(valor):
    return "" if valor is None else cantidades.a_texto(valor)


def _centavos(valor):
    return cantidades.a_texto_importe(valor)


def _escribir(columnas, filas):
    salida = io.StringIO()
    escritor = csv.DictWriter(
        salida, fieldnames=columnas, delimiter=";", lineterminator="\n"
    )
    escritor.writeheader()
    for fila in filas:
        escritor.writerow(fila)
    return salida.getvalue()


def resumen_por_sku(con, sesion_id, filtros=None):
    filas = []
    for fila in tablero.filas(con, sesion_id, filtros):
        filas.append({
            "id_orden": fila["id_orden"],
            "tipo": fila["tipo"] or "",
            "material": fila["material"] or "",
            "sku": fila["sku"],
            "descripcion": fila["descripcion"],
            "grupo": fila["grupo"] or "",
            "ubicacion": fila["ubicacion"] or "",
            "ubicacion_real": fila["ubicacion_real"] or "",
            "unidad": fila["unidad"],
            "stock_sistema": _milesimas(fila["stock_sistema"]),
            "ultimo_conteo": _milesimas(fila["ultimo_conteo"]),
            "dif": _milesimas(fila["dif"]),
            "costo_unitario": _centavos(fila["costo_unitario"]),
            "dif_valorizada": _centavos(fila["dif_valorizada"]),
            "estado": fila["estado"],
            "fecha": fila["fecha"] or "",
            "observaciones": fila["observaciones"] or "",
        })
    return _escribir(COLUMNAS_RESUMEN, filas)


def detalle(con, sesion_id, filtros=None):
    """Una fila por escaneo. Acepta los mismos filtros que el resumen.

    Los dos archivos se leen juntos, y uno filtrado junto a otro completo
    invita a conclusiones falsas: el detalle mostraría escaneos de artículos
    que en el resumen no figuran.
    """
    anulados = {
        fila["anula_uuid"]
        for fila in con.execute(
            "SELECT anula_uuid FROM conteo "
            "WHERE sesion_id = ? AND anula_uuid IS NOT NULL",
            (sesion_id,),
        )
    }

    crudas = con.execute(
        """
        SELECT c.uuid, c.cantidad, c.ubicacion_real, c.observaciones,
               c.timestamp_dispositivo, c.timestamp_servidor, c.anula_uuid,
               c.fuera_asignacion,
               a.id AS articulo_id, a.sku, a.descripcion, a.unidad, a.ubicacion,
               o.nombre AS operario, p.numero AS pasada_numero
        FROM conteo c
        JOIN articulo a ON a.id = c.articulo_id
        JOIN operario o ON o.id = c.operario_id
        JOIN pasada p ON p.id = c.pasada_id
        WHERE c.sesion_id = ?
        ORDER BY c.rowid
        """,
        (sesion_id,),
    ).fetchall()

    if filtros:
        # El filtro se aplica sobre el artículo, no sobre el escaneo: el
        # tablero ya sabe resolverlo y así los dos archivos describen
        # exactamente la misma población.
        permitidos = {fila["id"] for fila in tablero.filas(con, sesion_id, filtros)}
        crudas = [fila for fila in crudas if fila["articulo_id"] in permitidos]

    filas = []
    for fila in crudas:
        es_anulacion = fila["anula_uuid"] is not None
        filas.append({
            # La fecha del escaneo, no la de la sincronización: los celulares
            # sincronizan en lote y una mañana entera compartiría instante.
            "fecha": fila["timestamp_dispositivo"],
            "fecha_sincronizacion": fila["timestamp_servidor"],
            "pasada": sesiones.etiqueta_pasada(fila["pasada_numero"]),
            "operario": fila["operario"],
            "sku": fila["sku"],
            "descripcion": fila["descripcion"],
            "unidad": fila["unidad"],
            "cantidad": _milesimas(fila["cantidad"]),
            "ubicacion": fila["ubicacion"] or "",
            "ubicacion_real": fila["ubicacion_real"] or "",
            "observaciones": fila["observaciones"] or "",
            "anulado": "SI" if (es_anulacion or fila["uuid"] in anulados) else "",
            "fuera_asignacion": "SI" if fila["fuera_asignacion"] else "",
        })
    return _escribir(COLUMNAS_DETALLE, filas)
