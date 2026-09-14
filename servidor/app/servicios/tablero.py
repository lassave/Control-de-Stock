"""Cálculo del tablero: valor vigente, diferencia y estado de cada artículo."""

from app.repos import asignaciones, proyectos

SIN_CONTAR = "SIN CONTAR"
CONSOLIDADO = "CONSOLIDADO"
A_RECONTAR = "A RECONTAR"


def estado_de(dif, stock, pct, min_abs, hubo_conteo):
    """Estado de un artículo según la tolerancia del proyecto.

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


CTE_VIGENTES = """
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
"""
"""Qué conteo vale hoy, para cualquiera que pregunte.

Dos reglas viven acá, y las dos tienen que significar lo mismo en todos
lados: si el tablero y la pestaña de reparto las escribieran por separado,
tarde o temprano dirían cosas distintas del mismo SKU.

Las anulaciones se descartan de a pares: una anulación es una fila que
apunta a otra por anula_uuid, y se excluyen las dos, la que anula —que no
suma— y la anulada.

Y `ultima_pasada` marca la pasada de número más alto en la que cada
artículo fue contado. El total vigente es el de esa pasada, no la suma de
todas: si en el Conteo 1 se registraron 48 y en el Conteo 2 se cuentan 50,
el valor vigente es 50 —sumar daría 98, que no significa nada—. Un
artículo que no entró en la última pasada conserva el valor de la última
en la que sí se contó.
"""


def _consulta_base():
    """Artículos con el valor vigente de su última pasada contada."""
    return CTE_VIGENTES + """
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
            (
                -- Ordenado en una subconsulta aparte: GROUP_CONCAT no
                -- acepta ORDER BY en esta versión de SQLite, y sin orden
                -- explícito el resultado podría cambiar entre una consulta
                -- y la siguiente sin que nadie lo pidiera.
                SELECT GROUP_CONCAT(codigo, ', ')
                FROM (
                    SELECT codigo FROM codigo_barras
                    WHERE articulo_id = a.id
                    ORDER BY id
                )
            ) AS codigos_de_barra,
            SUM(v.cantidad) AS total,
            COUNT(v.uuid) AS cantidad_conteos,
            MAX(v.fuera_asignacion) AS fuera_asignacion,
            MAX(v.timestamp_servidor) AS fecha
        FROM articulo a
        LEFT JOIN ultima_pasada u ON u.articulo_id = a.id
        LEFT JOIN vigentes v
            ON v.articulo_id = a.id AND v.pasada_numero = u.numero
        WHERE a.proyecto_id = ? AND a.fusionado_en IS NULL
        GROUP BY a.id
        ORDER BY a.id_orden
    """


def _armar_fila(fila, proyecto, asignados):
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
        proyecto["tolerancia_pct"], proyecto["tolerancia_min_abs"],
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
        "codigos_de_barra": fila["codigos_de_barra"],
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
        # MAX() sobre un LEFT JOIN sin conteos da NULL, y bool(None) es
        # False: un artículo sin contar no puede estar fuera de asignación.
        "fuera_asignacion": bool(fila["fuera_asignacion"]),
        # Lista vacía = nadie tiene asignada la ubicación de este artículo,
        # el caso que conviene resaltar: es lo que corre riesgo de no
        # contarse.
        "asignado_a": asignados.get(fila["id"], []),
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

    if filtros.get("solo_agregados") and fila["origen"] != "alta_rapida":
        return False

    texto = (filtros.get("texto") or "").strip().lower()
    if texto:
        blanco = f"{fila['sku']} {fila['descripcion']}".lower()
        if texto not in blanco:
            return False

    return True


def filas(con, proyecto_id, filtros=None):
    """Las filas del tablero, ya calculadas y filtradas."""
    proyecto = proyectos.obtener(con, proyecto_id)
    crudas = con.execute(_consulta_base(), (proyecto_id,)).fetchall()
    asignados = asignaciones.asignados_por_articulo(con, proyecto_id)
    resultado = [_armar_fila(fila, proyecto, asignados) for fila in crudas]

    if filtros:
        resultado = [fila for fila in resultado if _pasa_filtros(fila, filtros)]

    return resultado


def resumen(con, proyecto_id):
    """Las métricas de cabecera del tablero."""
    todas = filas(con, proyecto_id)
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
