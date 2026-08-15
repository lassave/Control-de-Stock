# Mostrar los códigos de barra en el tablero — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** que el tablero y la exportación de resumen muestren todos los
códigos de barra de cada artículo, no solo el primero.

**Arquitectura:** la consulta del tablero suma una columna calculada —los
códigos del artículo, concatenados en el orden en que se cargaron— que ya
queda disponible tanto para el panel como para la exportación de resumen,
porque esta última reusa `tablero.filas(...)`.

**Tech Stack:** FastAPI, SQLite (SQL directo), pytest, JavaScript sin
dependencias.

**Especificación:**
`docs/superpowers/specs/2026-08-15-codigos-de-barra-en-tablero-design.md`

## Global Constraints

- **Todo dato del servidor se escapa antes de ir al HTML.** Los códigos de
  barra son dato del cliente como cualquier otro; se escriben con
  `esc(...)`, igual que el resto de las columnas del tablero.
- **Textos en castellano rioplatense**, sin jerga técnica.
- **Mensajes de commit en castellano, en presente, describiendo el
  efecto**, y el cuerpo explica *por qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

## Entorno

El `python` del PATH es el acceso directo de la Microsoft Store y no
ejecuta nada: siempre el intérprete del venv por ruta.

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

## Lo que ya existe y se consume

- **La tabla `codigo_barras`** (`servidor/app/esquema.sql:66-72`): `id,
  articulo_id, codigo`. Sin restricción `UNIQUE` sobre `articulo_id`: un
  artículo puede tener más de una fila. `importacion.importar` inserta una
  al importar (`servidor/app/servicios/importacion.py:238-247`, usa el SKU
  si el maestro no trae columna de código); el alta rápida inserta otra
  (`servidor/app/repos/articulos.py:55-66`, `_asociar_codigo`, idempotente).
- **`tablero._consulta_base()`** (`servidor/app/servicios/tablero.py:77-137`):
  ya tiene el patrón exacto a reusar — una subconsulta con `GROUP_CONCAT`
  para juntar las observaciones de todos los conteos vigentes de un
  artículo (líneas 121-125). El nuevo campo sigue el mismo molde, contra
  otra tabla.
- **`exportacion.resumen_por_sku`** (`servidor/app/servicios/exportacion.py:47-70`):
  recorre `tablero.filas(...)` y arma cada fila del CSV a mano, columna por
  columna, contra la lista `COLUMNAS_RESUMEN` (línea 14-18). Todo lo que
  entra a `_armar_fila` en `tablero.py` queda disponible acá sin tocar la
  consulta de nuevo.
- **`dibujarFila(fila)`** en `servidor/panel/app.js:70-105`: arma cada
  `<tr>` del tablero con `esc(...)` en cada celda que viene del servidor.
  El encabezado de la tabla está en `servidor/panel/index.html:47-55`.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `servidor/app/servicios/tablero.py` | Calcula `codigos_de_barra` por artículo. |
| `servidor/app/servicios/exportacion.py` | La suma al CSV de resumen. |
| `servidor/panel/index.html` | La columna nueva en el encabezado. |
| `servidor/panel/app.js` | La celda nueva en cada fila. |

---

### Task 1: El tablero calcula los códigos de barra

**Files:**
- Modify: `servidor/app/servicios/tablero.py`
- Modify: `servidor/app/servicios/exportacion.py`
- Test: `servidor/tests/test_tablero.py`
- Test: `servidor/tests/test_exportacion.py`

**Interfaces:**
- Produces: cada fila de `tablero.filas(...)` gana la clave
  `"codigos_de_barra": str | None` — los códigos del artículo separados
  por `", "`, en el orden en que se cargaron, o `None` si no tiene ninguno.
  El CSV de `exportacion.resumen_por_sku(...)` gana la columna
  `codigos_de_barra`, al lado de `sku`.

- [ ] **Step 1: Escribir los tests del tablero**

Agregar a `servidor/tests/test_tablero.py`, al final del archivo:

```python
def test_trae_el_codigo_de_barra_del_articulo(con, escenario):
    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    # El maestro del escenario no trae columna de código: importacion.py usa
    # el SKU como código cuando no viene ninguno.
    assert fila["codigos_de_barra"] == "A"


def test_trae_varios_codigos_en_el_orden_en_que_se_cargaron(con, escenario):
    articulo_id = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    con.execute(
        "INSERT INTO codigo_barras (articulo_id, codigo) VALUES (?, ?)",
        (articulo_id, "7791111111111"),
    )
    con.commit()

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["codigos_de_barra"] == "A, 7791111111111"


def test_sin_ningun_codigo_no_rompe_la_fila(con, escenario):
    articulo_id = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    con.execute("DELETE FROM codigo_barras WHERE articulo_id = ?", (articulo_id,))
    con.commit()

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["codigos_de_barra"] is None
```

- [ ] **Step 2: Escribir el test de la exportación**

Agregar a `servidor/tests/test_exportacion.py`, al final del archivo:

```python
def test_resumen_trae_los_codigos_de_barra(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_a = next(f for f in filas if f["sku"] == "A")

    assert fila_a["codigos_de_barra"] == "A"
```

Reemplazar el test `test_resumen_tiene_las_columnas_del_spec` existente por:

```python
def test_resumen_tiene_las_columnas_del_spec(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))

    assert list(filas[0].keys()) == [
        "id_orden", "tipo", "material", "sku", "codigos_de_barra", "descripcion",
        "grupo", "ubicacion", "ubicacion_real", "unidad", "stock_sistema",
        "ultimo_conteo", "dif", "costo_unitario", "dif_valorizada",
        "estado", "fecha", "observaciones",
    ]
```

- [ ] **Step 3: Correr y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_tablero.py .\servidor\tests\test_exportacion.py -v --rootdir .\servidor`
Expected: FAIL — `KeyError: 'codigos_de_barra'` en el tablero, y la
aserción de columnas del resumen no coincide.

- [ ] **Step 4: Sumar el campo a la consulta del tablero**

En `servidor/app/servicios/tablero.py`, dentro de `_consulta_base()`,
agregar la subconsulta entre la de `observaciones` y `SUM(v.cantidad) AS
total,`:

```python
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
```

(Es la misma consulta que ya está: solo se agrega el bloque
`codigos_de_barra` nuevo, entre `observaciones` y `SUM(v.cantidad)`.)

En `_armar_fila(...)`, agregar la clave al diccionario que devuelve, al
lado de `"sku"`:

```python
        "sku": fila["sku"],
        "codigos_de_barra": fila["codigos_de_barra"],
        "descripcion": fila["descripcion"],
```

- [ ] **Step 5: Sumar la columna a la exportación de resumen**

En `servidor/app/servicios/exportacion.py`, agregar `"codigos_de_barra"` a
`COLUMNAS_RESUMEN`, al lado de `"sku"`:

```python
COLUMNAS_RESUMEN = [
    "id_orden", "tipo", "material", "sku", "codigos_de_barra", "descripcion",
    "grupo", "ubicacion", "ubicacion_real", "unidad", "stock_sistema",
    "ultimo_conteo", "dif", "costo_unitario", "dif_valorizada",
    "estado", "fecha", "observaciones",
]
```

En `resumen_por_sku(...)`, agregar la clave al diccionario de cada fila, al
lado de `"sku"`:

```python
            "sku": fila["sku"],
            "codigos_de_barra": fila["codigos_de_barra"] or "",
            "descripcion": fila["descripcion"],
```

- [ ] **Step 6: Correr y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_tablero.py .\servidor\tests\test_exportacion.py -v --rootdir .\servidor`
Expected: PASS, todos.

- [ ] **Step 7: Correr toda la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add servidor/app/servicios/tablero.py servidor/app/servicios/exportacion.py \
        servidor/tests/test_tablero.py servidor/tests/test_exportacion.py
git commit -m "El tablero calcula los codigos de barra de cada articulo

La tabla codigo_barras ya guardaba uno o mas codigos por articulo, pero
nada los leia. Se agregan concatenados y en el orden en que se cargaron,
con el mismo patron que ya usa la consulta para las observaciones. La
exportacion de resumen los hereda gratis, porque ya reusa tablero.filas.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: El panel los muestra

**Files:**
- Modify: `servidor/panel/index.html`
- Modify: `servidor/panel/app.js`

**Interfaces:**
- Consumes: `fila.codigos_de_barra` (Task 1).

- [ ] **Step 1: El encabezado de la columna**

En `servidor/panel/index.html`, agregar `<th>Código de barras</th>` después
de `<th>SKU</th>`:

```html
              <th>#</th><th>Tipo</th><th>Material</th><th>SKU</th>
              <th>Código de barras</th>
              <th>Descripción</th><th>Grupo</th><th>Ubicación</th>
```

- [ ] **Step 2: La celda de cada fila**

En `servidor/panel/app.js`, dentro de `dibujarFila(fila)`, agregar la celda
después de la del SKU:

```javascript
      <td>${esc(fila.sku)}</td>
      <td>${esc(fila.codigos_de_barra)}</td>
      <td>${esc(fila.descripcion)}</td>
```

- [ ] **Step 3: Correr toda la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS. El test que audita el escapado de `app.js` ya cubre esta
celda nueva sin que haga falta tocarlo: `fila.codigos_de_barra` empieza con
`fila.`, que ya está en la lista de datos del servidor que el guardián
vigila, y está envuelta en `esc(...)`.

- [ ] **Step 4: Verificar en el navegador**

```powershell
.\"Iniciar servidor.bat"
```

1. Crear una sesión e importar un maestro. Confirmar que aparece la
   columna **"Código de barras"** al lado de SKU, con el código de cada
   artículo.
2. Exportar el resumen por SKU y confirmar que el CSV tiene la columna
   `codigos_de_barra` en la misma posición.
3. Si el maestro que se usó no tiene columna de código de barras, cada
   artículo va a mostrar su propio SKU como código —es el comportamiento
   ya existente de `importacion.py`, no algo nuevo de esta tarea—.

- [ ] **Step 5: Commit**

```bash
git add servidor/panel/index.html servidor/panel/app.js
git commit -m "Muestra los codigos de barra en el tablero

El dato ya estaba calculado desde la tarea anterior; esto solo agrega la
columna en el encabezado y la celda en cada fila, escapada igual que el
resto de las columnas.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Verificación final del plan

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Todo en verde, y sobre todo: **el tablero y la exportación de resumen
muestran todos los códigos de barra de cada artículo, en el orden en que
se cargaron.**
