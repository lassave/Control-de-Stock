"""Alta de artículos que no vienen del maestro.

Cuando el operario escanea un código que no está en el maestro, el artículo
se crea acá con `origen = 'alta_rapida'`. En el panel y en la exportación
salen identificados aparte, para resolverlos después en el ERP.
"""

import sqlite3

from app import reloj
from app.repos import conteos, operarios

CAMPOS_PUBLICOS = (
    "id, id_orden, tipo, material, sku, descripcion, grupo, ubicacion, unidad"
)

# Cómo se nombra cada campo cuando hay que explicarle al operario qué está
# mal: el mensaje lo lee alguien parado frente a la mercadería, no quien
# escribió el JSON.
ETIQUETAS = {
    "codigo": "código",
    "descripcion": "descripción",
    "unidad": "unidad",
    "ubicacion": "ubicación",
}


def _publico(con, articulo_id):
    fila = con.execute(
        f"SELECT {CAMPOS_PUBLICOS} FROM articulo WHERE id = ?", (articulo_id,)
    ).fetchone()
    return dict(fila)


def _texto(datos, campo):
    """El campo como texto limpio. Ausente es vacío; de otro tipo, se rechaza.

    El cuerpo del alta llega del JSON del celular, así que puede venir
    cualquier cosa en cualquier campo: un código de barras serializado como
    número, que es lo natural para un EAN, explotaría al recortarlo y saldría
    como error del servidor.

    Se rechaza en vez de descartarlo porque tomarlo como vacío es peor que el
    error: el artículo se daría de alta con un SKU generado y sin el código
    asociado, el escaneo siguiente de la misma etiqueta no lo encontraría y
    crearía otro, uno por escaneo, que es justo lo que este módulo evita.
    """
    valor = datos.get(campo)
    if valor is None:
        return ""
    if not isinstance(valor, str):
        raise ValueError(f"«{ETIQUETAS[campo]}» tiene que venir como texto")
    return valor.strip()


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

    Sigue al mayor que ya está, no a la cantidad: el maestro del cliente puede
    traer SKUs con esta misma forma, y repetir uno rompe la unicidad por
    sesión —el alta fallaría con el operario esperando frente a la
    mercadería—. Contarlos, además, numeraba salteando y para atrás: con un
    AR-3 del maestro salían AR-2, AR-4, AR-5, que de correlativo no tiene
    nada para quien lee la planilla.
    """
    mayor = 0
    for fila in con.execute(
        "SELECT sku FROM articulo WHERE sesion_id = ? AND sku LIKE 'AR-%'",
        (sesion_id,),
    ):
        try:
            numero = int(fila["sku"][len("AR-"):])
        except ValueError:
            continue  # 'AR-BRONCE' del maestro no participa de la numeración
        mayor = max(mayor, numero)
    return f"AR-{mayor + 1}"


def _resolver_existente(con, sesion_id, codigo):
    """El artículo de la sesión que ya identifica ese código, o None.

    Contempla las dos formas de «ya está»: que el código esté asociado a un
    artículo, o que coincida con el SKU de uno del maestro que traía otro
    código de barras. En el segundo caso le asocia el código escaneado.
    """
    if not codigo:
        return None

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

    return None


# Cuántas veces se reintenta un alta sin código cuyo SKU generado se lo llevó
# otro pedido en el medio. Con dos o tres celulares dando de alta a la vez,
# más de un choque seguido es prácticamente imposible.
INTENTOS_DE_ALTA = 3


def _insertar(con, sesion_id, codigo, campos, operario, ahora):
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
            (sesion_id, mayor + 1, sku, campos["descripcion"], campos["ubicacion"],
             campos["unidad"], operario["nombre"] if operario else None, ahora),
        )
        articulo_id = cursor.lastrowid

        # Sin etiqueta legible se asocia el SKU generado: el conteo resuelve el
        # artículo solo por `codigo_barras`, así que sin esta fila el artículo
        # existiría sin poder contarse nunca. Es la misma convención que usa la
        # importación del maestro.
        _asociar_codigo(con, articulo_id, codigo or sku)

    return articulo_id


def crear_alta_rapida(con, sesion_id, operario_id, datos):
    """Crea el artículo y le asocia el código escaneado.

    Si el código ya identifica a un artículo de la sesión —porque otro
    operario lo dio de alta hace un segundo, o porque coincide con el SKU de
    uno del maestro— devuelve ese, sin crear nada. Dos filas para el mismo
    producto partirían su conteo en dos.

    `creado` distingue las dos cosas. Sin ese campo la pantalla no puede
    avisar «ese código ya estaba: Tornillo» cuando el operario escribió otra
    descripción, y cada cliente terminaría inventando su propia heurística.
    """
    # El tipo se verifica antes que nada: sobre algo que no es un diccionario,
    # `.get` lanzaría AttributeError, que el endpoint no atrapa, y el pedido
    # saldría como error del servidor en vez de como pedido mal armado.
    if not isinstance(datos, dict):
        raise ValueError("El pedido tiene que traer los datos del artículo")

    codigo = _texto(datos, "codigo")
    descripcion = _texto(datos, "descripcion")
    unidad = _texto(datos, "unidad").upper() or "UN"
    ubicacion = _texto(datos, "ubicacion") or None

    if not descripcion:
        raise ValueError("El artículo necesita una descripción")

    unidades = {fila["codigo"] for fila in con.execute("SELECT codigo FROM unidad")}
    if unidad not in unidades:
        raise ValueError(f"La unidad «{unidad}» no está en el catálogo")

    existente = _resolver_existente(con, sesion_id, codigo)
    if existente:
        return {**existente, "creado": False}

    operario = operarios.obtener(con, operario_id)
    ahora = reloj.ahora()
    campos = {"descripcion": descripcion, "ubicacion": ubicacion, "unidad": unidad}

    for intento in range(INTENTOS_DE_ALTA):
        try:
            articulo_id = _insertar(con, sesion_id, codigo, campos, operario, ahora)
        except sqlite3.IntegrityError:
            # Otro pedido dio de alta lo mismo entre la búsqueda y el INSERT.
            # El choque no es ValueError, así que sin esto sale como error del
            # servidor aunque el artículo ya esté creado y el alta sea, en los
            # hechos, exitosa.
            existente = _resolver_existente(con, sesion_id, codigo)
            if existente:
                return {**existente, "creado": False}
            if codigo or intento == INTENTOS_DE_ALTA - 1:
                # Con código el SKU es fijo: reintentar daría el mismo choque.
                # Sin código el SKU es un correlativo, y volver a generarlo
                # toma el siguiente libre; devolver el ajeno sería peor, porque
                # es otro producto, no el mismo.
                raise
        else:
            return {**_publico(con, articulo_id), "creado": True}
