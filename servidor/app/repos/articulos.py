"""Alta de artículos que no vienen del maestro.

Cuando el operario escanea un código que no está en el maestro, el artículo
se crea acá con `origen = 'alta_rapida'`. En el panel y en la exportación
salen identificados aparte, para resolverlos después en el ERP.
"""

from app import reloj
from app.repos import conteos, operarios

CAMPOS_PUBLICOS = (
    "id, id_orden, tipo, material, sku, descripcion, grupo, ubicacion, unidad"
)


def _publico(con, articulo_id):
    fila = con.execute(
        f"SELECT {CAMPOS_PUBLICOS} FROM articulo WHERE id = ?", (articulo_id,)
    ).fetchone()
    return dict(fila)


def _texto(datos, campo):
    """El campo como texto limpio, o vacío si vino cualquier otra cosa.

    El cuerpo del alta llega del JSON del celular: un número donde va la
    descripción explotaría al recortarlo y saldría como error del servidor,
    en vez de decirle al operario qué le falta al alta.
    """
    valor = datos.get(campo)
    return valor.strip() if isinstance(valor, str) else ""


def _asociar_codigo(con, articulo_id, codigo):
    """Asocia el código si todavía no lo tiene. Idempotente a propósito."""
    if not codigo:
        return
    ya_esta = con.execute(
        "SELECT 1 FROM codigo_barras WHERE articulo_id = ? AND codigo = ?",
        (articulo_id, codigo),
    ).fetchone()
    if not ya_esta:
        con.execute(
            "INSERT INTO codigo_barras (articulo_id, codigo) VALUES (?, ?)",
            (articulo_id, codigo),
        )


def _siguiente_sku_generado(con, sesion_id):
    """AR-1, AR-2, … para los productos que no tienen etiqueta legible.

    Se saltea los que ya están: el maestro del cliente puede traer SKUs con
    esta misma forma, y repetir uno rompe la unicidad por sesión. El alta
    fallaría con el operario esperando frente a la mercadería.
    """
    usados = {
        fila["sku"]
        for fila in con.execute(
            "SELECT sku FROM articulo WHERE sesion_id = ? AND sku LIKE 'AR-%'",
            (sesion_id,),
        )
    }
    numero = len(usados) + 1
    while f"AR-{numero}" in usados:
        numero += 1
    return f"AR-{numero}"


def crear_alta_rapida(con, sesion_id, operario_id, datos):
    """Crea el artículo y le asocia el código escaneado.

    Si el código ya identifica a un artículo de la sesión —porque otro
    operario lo dio de alta hace un segundo, o porque coincide con el SKU de
    uno del maestro— devuelve ese, sin crear nada. Dos filas para el mismo
    producto partirían su conteo en dos.
    """
    codigo = _texto(datos, "codigo")
    descripcion = _texto(datos, "descripcion")
    unidad = _texto(datos, "unidad").upper() or "UN"
    ubicacion = _texto(datos, "ubicacion") or None

    if not descripcion:
        raise ValueError("El artículo necesita una descripción")

    unidades = {fila["codigo"] for fila in con.execute("SELECT codigo FROM unidad")}
    if unidad not in unidades:
        raise ValueError(f"La unidad «{unidad}» no está en el catálogo")

    if codigo:
        existente = conteos.buscar_por_codigo(con, sesion_id, codigo)
        if existente:
            return existente

        por_sku = con.execute(
            "SELECT id FROM articulo WHERE sesion_id = ? AND sku = ?",
            (sesion_id, codigo),
        ).fetchone()
        if por_sku:
            with con:
                _asociar_codigo(con, por_sku["id"], codigo)
            return _publico(con, por_sku["id"])

    operario = operarios.obtener(con, operario_id)
    ahora = reloj.ahora()

    with con:
        sku = codigo or _siguiente_sku_generado(con, sesion_id)

        # El orden define el recorrido y la planilla del operario: el artículo
        # nuevo va al final, nunca en el medio de lo ya recorrido.
        mayor = con.execute(
            "SELECT COALESCE(MAX(id_orden), 0) AS m FROM articulo WHERE sesion_id = ?",
            (sesion_id,),
        ).fetchone()["m"]

        cursor = con.execute(
            """
            INSERT INTO articulo (
                sesion_id, id_orden, sku, descripcion, ubicacion, unidad,
                stock_sistema, origen, creado_por, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, 0, 'alta_rapida', ?, ?)
            """,
            (sesion_id, mayor + 1, sku, descripcion, ubicacion, unidad,
             operario["nombre"] if operario else None, ahora),
        )
        articulo_id = cursor.lastrowid

        _asociar_codigo(con, articulo_id, codigo)

    return _publico(con, articulo_id)
