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
    # porque se tecleó un cero de más. Y 12 por 120, que es el mismo desvío
    # para el otro lado: acá también importa la dirección, porque lo que el
    # tablero informa es qué buscar cuando se va a recontar.
    if nucleo_c == nucleo_s and len(dc) != len(ds):
        return "dígito de más" if len(dc) > len(ds) else "dígito faltante"

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
    # Se distingue de «dígito de más» a propósito: el tablero es donde alguien
    # decide qué ir a recontar, y decirle que sobra un dígito cuando falta lo
    # manda a mirar para el lado equivocado.
    corto, largo = sorted((nucleo_c, nucleo_s), key=len)
    if len(largo) - len(corto) == 1 and largo.startswith(corto):
        return "dígito de más" if nucleo_c == largo else "dígito faltante"

    return None


def _consulta_base():
    """Artículos con el valor vigente de su última pasada contada.

    Dos reglas viven en esta consulta.

    Las anulaciones se descartan de a pares: una anulación es una fila que
    apunta a otra por anula_uuid, y se excluyen las dos, la que anula —que no
    suma— y la anulada.

    Y el total es el de la pasada de número más alto en la que el artículo
    fue contado, no la suma de todas. Si en el Conteo 1 se registraron 48 y
    en el Conteo 2 se cuentan 50, el valor vigente es 50: sumar daría 98, que
    no significa nada. Un artículo que no entró en la última pasada conserva
    el valor de la última en la que sí se contó.
    """
    return """
        WITH vigentes AS (
            -- El rowid se arrastra con nombre propio: una CTE no tiene rowid
            -- implícito y «SELECT c.*» no lo incluye, así que sin esto el
            -- desempate por orden de llegada no tiene con qué resolverse.
            SELECT c.*, c.rowid AS orden_llegada, p.numero AS pasada_numero
            FROM conteo c
            JOIN pasada p ON p.id = c.pasada_id
            WHERE c.anula_uuid IS NULL
              AND c.uuid NOT IN (
                  SELECT anula_uuid FROM conteo WHERE anula_uuid IS NOT NULL
              )
        ),
        ultima_pasada AS (
            SELECT articulo_id, MAX(pasada_numero) AS numero
            FROM vigentes
            GROUP BY articulo_id
        )
        SELECT
            a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion,
            a.grupo, a.ubicacion, a.unidad, a.stock_sistema, a.costo_unitario,
            a.origen,
            (
                SELECT v2.ubicacion_real
                FROM vigentes v2
                WHERE v2.articulo_id = a.id AND v2.ubicacion_real IS NOT NULL
                ORDER BY v2.timestamp_servidor DESC, v2.orden_llegada DESC
                LIMIT 1
            ) AS ubicacion_real,
            (
                SELECT GROUP_CONCAT(v3.observaciones, ' | ')
                FROM vigentes v3
                WHERE v3.articulo_id = a.id AND v3.observaciones IS NOT NULL
            ) AS observaciones,
            SUM(v.cantidad) AS total,
            COUNT(v.uuid) AS cantidad_conteos,
            MAX(v.timestamp_servidor) AS fecha
        FROM articulo a
        LEFT JOIN ultima_pasada u ON u.articulo_id = a.id
        LEFT JOIN vigentes v
            ON v.articulo_id = a.id AND v.pasada_numero = u.numero
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
