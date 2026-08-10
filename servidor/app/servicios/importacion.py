"""Importación del maestro de artículos desde el CSV del ERP.

El mapeo de columnas se resuelve en pantalla y no en código: cada cliente
exporta con nombres y orden distintos, y tocar el código en cada
instalación no escala.
"""

from app import cantidades, reloj
from app.servicios import lectura_csv

CAMPOS = [
    "id_orden", "tipo", "material", "sku", "descripcion", "grupo",
    "ubicacion", "unidad", "stock_sistema", "costo_unitario", "codigo_barras",
]

CAMPOS_OBLIGATORIOS = ["sku", "descripcion"]

CAMPOS_TEXTO = ["tipo", "material", "sku", "descripcion", "grupo", "ubicacion"]


def previsualizar(contenido, cantidad=5):
    """Encabezados y primeras filas, para armar el mapeo en pantalla."""
    encabezados, filas = lectura_csv.leer(contenido)
    return {"encabezados": encabezados, "filas": filas[:cantidad]}


def _validar_mapeo(mapeo, encabezados):
    faltantes = [campo for campo in CAMPOS_OBLIGATORIOS if not mapeo.get(campo)]
    if faltantes:
        raise ValueError(
            "Faltan campos obligatorios en el mapeo: " + ", ".join(faltantes)
        )

    for campo, encabezado in mapeo.items():
        if campo not in CAMPOS:
            raise ValueError(f"El campo «{campo}» no es mapeable")
        if encabezado and encabezado not in encabezados:
            raise ValueError(
                f"La columna «{encabezado}» no existe en el archivo"
            )


def importar(con, sesion_id, contenido, mapeo, unidad_por_defecto="UN"):
    """Carga el maestro en la sesión. Devuelve el resumen de lo importado."""
    encabezados, filas = lectura_csv.leer(contenido)
    _validar_mapeo(mapeo, encabezados)

    indice = {campo: encabezados.index(col) for campo, col in mapeo.items() if col}
    ahora = reloj.ahora()

    resultado = {
        "importados": 0, "codigos": 0, "descartadas": [], "advertencias": [],
    }

    # Toda la importación es una sola transacción: un maestro a medio cargar
    # es peor que ninguno, porque el tablero lo muestra como si estuviera
    # completo y los artículos que faltan aparecen como no contados.
    with con:
        for numero_fila, fila in enumerate(filas, start=2):
            _cargar_fila(
                con, sesion_id, fila, numero_fila,
                indice, encabezados, unidad_por_defecto, ahora, resultado,
            )

    return resultado


def _cargar_fila(
    con, sesion_id, fila, numero_fila,
    indice, encabezados, unidad_por_defecto, ahora, resultado,
):
    """Carga una fila del maestro, acumulando los avisos en `resultado`."""
    descartadas = resultado["descartadas"]
    advertencias = resultado["advertencias"]

    def valor(campo):
        posicion = indice.get(campo)
        return fila[posicion] if posicion is not None else ""

    if len(fila) > len(encabezados):
        # Suele delatar una comilla sin cerrar o un separador dentro de un
        # campo. Se avisa y se sigue: el mapeo usa las columnas por posición.
        advertencias.append({
            "fila": numero_fila,
            "motivo": "Tiene más columnas que el encabezado",
        })

    sku = valor("sku")
    if not sku:
        descartadas.append({"fila": numero_fila, "motivo": "Sin SKU"})
        return

    descripcion = valor("descripcion") or sku
    siguiente_orden = resultado["importados"] + 1

    if "id_orden" in indice:
        try:
            id_orden = int(valor("id_orden"))
        except ValueError:
            id_orden = siguiente_orden
            advertencias.append({
                "fila": numero_fila,
                "motivo": f"Número de orden inválido, se usó {id_orden}",
            })
    else:
        id_orden = siguiente_orden

    stock = 0
    if "stock_sistema" in indice:
        try:
            stock = cantidades.a_milesimas(valor("stock_sistema"))
        except ValueError:
            advertencias.append({
                "fila": numero_fila,
                "motivo": f"Stock «{valor('stock_sistema')}» inválido, se usó 0",
            })

    costo = None
    if "costo_unitario" in indice and valor("costo_unitario"):
        try:
            costo = cantidades.a_centavos(valor("costo_unitario"))
        except ValueError:
            advertencias.append({
                "fila": numero_fila,
                "motivo": f"Costo «{valor('costo_unitario')}» inválido, quedó vacío",
            })

    unidad = valor("unidad").upper() or unidad_por_defecto

    con.execute(
        """
        INSERT INTO articulo (
            sesion_id, id_orden, tipo, material, sku, descripcion, grupo,
            ubicacion, unidad, stock_sistema, costo_unitario, origen, creado_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'importado', ?)
        ON CONFLICT (sesion_id, sku) DO UPDATE SET
            id_orden = excluded.id_orden,
            tipo = excluded.tipo,
            material = excluded.material,
            descripcion = excluded.descripcion,
            grupo = excluded.grupo,
            ubicacion = excluded.ubicacion,
            unidad = excluded.unidad,
            stock_sistema = excluded.stock_sistema,
            costo_unitario = excluded.costo_unitario
        """,
        (
            sesion_id, id_orden, valor("tipo") or None, valor("material") or None,
            sku, descripcion, valor("grupo") or None, valor("ubicacion") or None,
            unidad, stock, costo, ahora,
        ),
    )

    # No se usa lastrowid: en un upsert que actualiza en vez de insertar,
    # SQLite deja el rowid del último INSERT exitoso, que puede ser de
    # otra fila. El SELECT por (sesion_id, sku) siempre da el correcto.
    articulo_id = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = ?",
        (sesion_id, sku),
    ).fetchone()["id"]

    codigo = valor("codigo_barras") or sku
    ya_existe = con.execute(
        "SELECT 1 FROM codigo_barras WHERE articulo_id = ? AND codigo = ?",
        (articulo_id, codigo),
    ).fetchone()
    if not ya_existe:
        con.execute(
            "INSERT INTO codigo_barras (articulo_id, codigo) VALUES (?, ?)",
            (articulo_id, codigo),
        )
        resultado["codigos"] += 1

    resultado["importados"] += 1
