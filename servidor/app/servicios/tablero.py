"""Cálculo del tablero: valor vigente, diferencia y estado de cada artículo."""

from app.repos import sesiones

SIN_CONTAR = "SIN CONTAR"
CONSOLIDADO = "CONSOLIDADO"
A_RECONTAR = "A RECONTAR"


def estado_de(dif, stock, pct, min_abs, hubo_conteo):
    """Estado de un artículo según la tolerancia de la sesión.

    Entra en tolerancia si la diferencia cae dentro del porcentaje o dentro
    del mínimo absoluto, el que resulte mayor. El porcentaje solo no sirve:
    un artículo con stock 3 quedaría afuera por una unidad.
    """
    if not hubo_conteo:
        return SIN_CONTAR

    limite = max(abs(stock) * pct / 100, min_abs)
    return CONSOLIDADO if abs(dif) <= limite else A_RECONTAR


def parece_error_de_carga(contado, stock):
    """Detecta diferencias con forma de error de tipeo.

    Es una marca para revisar primero, no una corrección: la cantidad puede
    estar bien y la diferencia ser real. Pero da una lista corta de
    candidatos antes de mandar medio depósito a recontar.

    En la app no se puede avisar de esto sin romper el conteo a ciegas —
    habría que conocer el stock del sistema—, así que vive solo acá.
    """
    if contado is None or contado == stock or stock == 0 or contado == 0:
        return None

    dc = str(abs(contado))
    ds = str(abs(stock))

    # Las cantidades vienen en milésimas: los ceros de la escala no son
    # dígitos que alguien haya tecleado. Se compara el núcleo, que es lo que
    # se marcó en la pantalla.
    nucleo_c = dc.rstrip("0")
    nucleo_s = ds.rstrip("0")

    # 240 por 24: el número quedó multiplicado por una potencia de diez
    # porque se tecleó un cero de más.
    if nucleo_c == nucleo_s and len(dc) != len(ds):
        return "dígito de más"

    # 5 tecleado dos veces queda 55: lo cargado es todo el mismo dígito y es
    # más largo que el del sistema.
    if (
        len(set(nucleo_c)) == 1
        and nucleo_c[0] == nucleo_s[0]
        and len(nucleo_c) > len(nucleo_s)
    ):
        return "dígito repetido"

    # 42 por 24: los mismos dígitos en otro orden.
    if len(nucleo_c) == len(nucleo_s) and sorted(nucleo_c) == sorted(nucleo_s):
        return "dígitos permutados"

    # 2 por 24: se soltó la tecla antes de tiempo y falta el último dígito.
    corto, largo = sorted((nucleo_c, nucleo_s), key=len)
    if len(largo) - len(corto) == 1 and largo.startswith(corto):
        return "dígito de más"

    return None


def _consulta_base():
    """Artículos con su total contado, sin las filas anuladas.

    Una anulación es una fila que apunta a otra por anula_uuid. Se excluyen
    las dos: la anulación (que no suma) y la anulada.
    """
    return """
        SELECT
            a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion,
            a.grupo, a.ubicacion, a.unidad, a.stock_sistema, a.costo_unitario,
            a.origen,
            (
                SELECT GROUP_CONCAT(c2.ubicacion_real)
                FROM conteo c2
                WHERE c2.articulo_id = a.id AND c2.ubicacion_real IS NOT NULL
            ) AS ubicacion_real,
            (
                SELECT GROUP_CONCAT(c3.observaciones, ' | ')
                FROM conteo c3
                WHERE c3.articulo_id = a.id AND c3.observaciones IS NOT NULL
            ) AS observaciones,
            SUM(c.cantidad) AS total,
            COUNT(c.uuid) AS cantidad_conteos,
            MAX(c.timestamp_servidor) AS fecha
        FROM articulo a
        LEFT JOIN conteo c
            ON c.articulo_id = a.id
            AND c.anula_uuid IS NULL
            AND c.uuid NOT IN (
                SELECT anula_uuid FROM conteo WHERE anula_uuid IS NOT NULL
            )
        WHERE a.sesion_id = ? AND a.fusionado_en IS NULL
        GROUP BY a.id
        ORDER BY a.id_orden
    """


def _armar_fila(fila, sesion):
    hubo_conteo = fila["cantidad_conteos"] > 0
    total = fila["total"] if hubo_conteo else None
    dif = total - fila["stock_sistema"] if hubo_conteo else None

    costo = fila["costo_unitario"]
    dif_valorizada = None
    if dif is not None and costo is not None:
        # dif está en milésimas y el costo en centavos: el producto queda en
        # centavos al dividir por mil.
        dif_valorizada = dif * costo // 1000

    estado = estado_de(
        dif or 0, fila["stock_sistema"],
        sesion["tolerancia_pct"], sesion["tolerancia_min_abs"],
        hubo_conteo,
    )

    # Solo tiene sentido revisar el tipeo de lo que quedó fuera de tolerancia.
    posible_error = (
        parece_error_de_carga(total, fila["stock_sistema"])
        if estado == A_RECONTAR else None
    )

    return {
        "id": fila["id"],
        "id_orden": fila["id_orden"],
        "tipo": fila["tipo"],
        "material": fila["material"],
        "sku": fila["sku"],
        "descripcion": fila["descripcion"],
        "grupo": fila["grupo"],
        "ubicacion": fila["ubicacion"],
        "ubicacion_real": fila["ubicacion_real"],
        "unidad": fila["unidad"],
        "stock_sistema": fila["stock_sistema"],
        "costo_unitario": costo,
        "ultimo_conteo": total,
        "dif": dif,
        "dif_valorizada": dif_valorizada,
        "estado": estado,
        "posible_error_carga": posible_error,
        "fecha": fila["fecha"],
        "observaciones": fila["observaciones"],
        "origen": fila["origen"],
    }


def _pasa_filtros(fila, filtros):
    for campo in ("tipo", "material", "grupo", "ubicacion", "estado"):
        esperado = filtros.get(campo)
        if esperado and fila[campo] != esperado:
            return False

    if filtros.get("solo_errores_carga") and not fila["posible_error_carga"]:
        return False

    texto = (filtros.get("texto") or "").strip().lower()
    if texto:
        blanco = f"{fila['sku']} {fila['descripcion']}".lower()
        if texto not in blanco:
            return False

    return True


def filas(con, sesion_id, filtros=None):
    """Las filas del tablero, ya calculadas y filtradas."""
    sesion = sesiones.obtener(con, sesion_id)
    crudas = con.execute(_consulta_base(), (sesion_id,)).fetchall()
    resultado = [_armar_fila(fila, sesion) for fila in crudas]

    if filtros:
        resultado = [fila for fila in resultado if _pasa_filtros(fila, filtros)]

    return resultado


def resumen(con, sesion_id):
    """Las métricas de cabecera del tablero."""
    todas = filas(con, sesion_id)
    total = len(todas)
    contados = sum(1 for fila in todas if fila["estado"] != SIN_CONTAR)

    desvio_neto = sum(
        fila["dif_valorizada"] for fila in todas if fila["dif_valorizada"]
    )
    desvio_absoluto = sum(
        abs(fila["dif_valorizada"]) for fila in todas if fila["dif_valorizada"]
    )

    return {
        "articulos": total,
        "contados": contados,
        "sin_contar": total - contados,
        "consolidados": sum(1 for f in todas if f["estado"] == CONSOLIDADO),
        "a_recontar": sum(1 for f in todas if f["estado"] == A_RECONTAR),
        "altas_rapidas": sum(1 for f in todas if f["origen"] == "alta_rapida"),
        "posibles_errores_carga": sum(1 for f in todas if f["posible_error_carga"]),
        "avance_pct": round(contados * 100 / total, 1) if total else 0,
        "desvio_neto": desvio_neto,
        "desvio_absoluto": desvio_absoluto,
    }
