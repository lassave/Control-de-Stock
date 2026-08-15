# Asignar sectores a cada operario — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** que desde el panel se le asignen ubicaciones a cada operario
para la pasada en curso, y que un conteo hecho fuera de lo asignado quede
marcado — en el tablero y en la exportación de detalle — sin bloquear nada
en el momento.

**Arquitectura:** completa un modelo de datos que ya existía sin usar (la
tabla `asignacion` y la columna `conteo.fuera_asignacion`). Un repositorio
nuevo (`asignaciones.py`) concentra el CRUD de asignaciones y la consulta de
ubicaciones del maestro; `conteos.registrar` calcula `fuera_asignacion` una
sola vez, al guardar; el tablero y la exportación lo muestran; el panel
suma la pantalla para repartir.

**Tech Stack:** FastAPI, SQLite (SQL directo), pytest, JavaScript sin
dependencias (`<dialog>` nativo del navegador).

**Especificación:**
`docs/superpowers/specs/2026-08-15-asignacion-de-sectores-design.md`

## Global Constraints

- **Fechas ISO 8601 UTC como texto** (`2026-08-15T14:32:05Z`). La única
  fuente es `servidor/app/reloj.py` (`reloj.ahora()`).
- **Todo dato del servidor se escapa antes de ir al HTML.** Lo que arma
  marcado con backticks pasa por `esc(...)`; hay un test que lo audita
  sobre todo `app.js`, no función por función.
- **Nada externo en el navegador**: ni CDN, ni fuentes, ni librerías
  remotas. El diálogo de sectores usa `<dialog>`, nativo del navegador.
- **`stock_sistema` y `costo_unitario` nunca salen por `/api/dispositivo/*`.**
  Este plan no toca esos endpoints.
- **Nada se edita ni se borra — pero eso es sobre los conteos, no sobre la
  asignación.** Un conteo es un hecho que ya pasó: se audita entero, para
  siempre. Una asignación es logística de antes de contar —a quién le toca
  qué—, y reemplazarla con la de ahora no reescribe ningún hecho: los
  conteos ya guardados conservan el `fuera_asignacion` que tenían al
  guardarse, pase lo que pase con el reparto después.
- **Textos en castellano rioplatense**, sin jerga técnica, también en los
  mensajes de error.
- **Mensajes de commit en castellano, en presente, describiendo el
  efecto**, y el cuerpo explica *por qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

## Entorno

El `python` del PATH es el acceso directo de la Microsoft Store y no
ejecuta nada: siempre el intérprete del venv por ruta.

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
# Un archivo puntual:
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_conteos.py -v --rootdir .\servidor
```

## Lo que ya existe y se consume

- **La tabla `asignacion`** (`servidor/app/esquema.sql:108-114`):
  `pasada_id, operario_id, ubicacion, fecha_asignacion`, con clave primaria
  compuesta por los tres primeros. Sin repositorio propio todavía.
- **`conteo.fuera_asignacion`** (`esquema.sql:82-96`): columna `INTEGER
  NOT NULL DEFAULT 0`. Hoy `conteos.registrar` la graba siempre en `0`
  (`servidor/app/repos/conteos.py:165`).
- **`sesiones.sesion_abierta(con)`** y **`sesiones.pasada_abierta(con,
  sesion_id)`** en `servidor/app/repos/sesiones.py`: la sesión y la pasada
  vigentes. `pasada_abierta` levanta `ValueError` si la sesión no tiene
  ninguna pasada abierta (sesión cerrada).
- **`operarios.listar(con)`** y **`operarios.obtener(con, operario_id)`**
  en `servidor/app/repos/operarios.py`: devuelven diccionarios con `id,
  nombre, token_dispositivo, activo`. `obtener` devuelve `None` si no
  existe.
- **`tablero._consulta_base()`** en `servidor/app/servicios/tablero.py`:
  la CTE `vigentes` ya trae `c.*` de cada conteo de la pasada de número más
  alto en que se contó cada artículo — `fuera_asignacion` ya está ahí
  adentro, solo falta agregarlo al `SELECT` final.
- **`exportacion.detalle`** en `servidor/app/servicios/exportacion.py`: una
  fila por escaneo, con `operario`, `pasada`, `ubicacion`, `ubicacion_real`
  y `anulado`. El patrón de columna nueva ya existe ahí (`anulado`: `"SI"`
  o `""`).
- **El patrón de marca del tablero**: `posible_error_carga` en
  `_armar_fila` (`tablero.py`) se dibuja en `panel/app.js::dibujarFila`
  como `<span class="marca" title="...">`. La clase CSS `.marca` ya existe
  en `panel/estilos.css:146-154`.
- **La clase CSS `.casilla`** (`panel/estilos.css:156-166`) y su uso en
  `panel/index.html:36-39`: `<label class="casilla"><input
  type="checkbox">texto</label>`. Es el estilo a reusar para cada
  ubicación del diálogo de sectores.
- **`estado.sesion`** en `panel/app.js`: la sesión abierta, según la
  encuentra `cargarSesiones()` (línea 177) recorriendo `/api/sesiones`. Se
  fija antes de que `iniciar()` llame a `cargarOperarios()` (línea
  486-496).
- **Las rutas de la API de este plan van anidadas bajo `/api/sesiones/{sesion_id}/...`**,
  a diferencia de como las nombra el diseño (`GET /api/ubicaciones`, `PUT
  /api/operarios/{id}/asignacion`, sin sesión en la URL). Es un ajuste
  deliberado sobre el diseño, no un error: cada endpoint nuevo de este plan
  depende de una sesión concreta —las ubicaciones son las de su maestro, la
  asignación es de su pasada—, y todos los endpoints existentes que ya
  dependen de una sesión (`/sesiones/{id}/tablero`,
  `/sesiones/{id}/exportar/...`) siguen ese mismo patrón. `GET /api/operarios`
  no lleva sesión en la URL a propósito: los operarios son globales, y solo
  necesita saber cuál es la sesión abierta para completar
  `ubicaciones_asignadas`, cosa que resuelve por su cuenta.
- **El guardián de escapado** en `servidor/tests/test_panel_estatico.py`:
  escanea toda plantilla entre backticks que contenga `<`, y exige que
  cualquier interpolación `${...}` que mencione una de las variables de
  `DATOS_DEL_SERVIDOR` (`fila|sesion|operario|vista|resultado|estado`)
  pase por `esc(...)`. Alcanza con **envolver siempre en `esc(...)` todo
  dato que venga del servidor** para pasarlo, sin necesidad de tocar esa
  lista.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `servidor/app/repos/asignaciones.py` *(nuevo)* | CRUD de `asignacion`, ubicaciones distintas del maestro, y la lista de operarios con lo que tienen asignado. |
| `servidor/app/repos/conteos.py` | Calcula `fuera_asignacion` al registrar. |
| `servidor/app/servicios/tablero.py` | Suma `fuera_asignacion` a la fila del tablero. |
| `servidor/app/servicios/exportacion.py` | Suma la columna al detalle exportado. |
| `servidor/app/api/panel.py` | Endpoints de ubicaciones y de asignación; `GET /operarios` pasa a incluir lo asignado. |
| `servidor/panel/index.html` | El diálogo de sectores. |
| `servidor/panel/app.js` | Lo completa, lo abre y lo guarda. |
| `servidor/panel/estilos.css` | El tamaño del diálogo y el espaciado de las casillas. |

---

### Task 1: El repositorio de asignaciones

**Files:**
- Create: `servidor/app/repos/asignaciones.py`
- Test: `servidor/tests/test_asignaciones.py`

**Interfaces:**
- Produces:
  - `asignaciones.reemplazar(con, pasada_id, operario_id, ubicaciones: list[str]) -> list[str]`
  - `asignaciones.de_operario(con, pasada_id, operario_id) -> list[str]`
  - `asignaciones.ubicaciones_distintas(con, sesion_id) -> list[str]`
  - `asignaciones.operarios_con_ubicaciones(con) -> list[dict]` — cada dict
    de `operarios.listar` más la clave `"ubicaciones_asignadas"`.

- [ ] **Step 1: Escribir los tests**

Crear `servidor/tests/test_asignaciones.py`:

```python
import pytest

from app.repos import asignaciones, operarios, sesiones
from app.servicios import importacion


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,ubic\n"
        "A,Tornillo,Deposito A\n"
        "B,Tuerca,Deposito B\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "ubicacion": "ubic",
    })
    juan = operarios.crear(con, "Juan")
    pasada = sesiones.pasada_abierta(con, sesion_id)
    return {"sesion_id": sesion_id, "juan": juan, "pasada_id": pasada["id"]}


def test_reemplazar_guarda_las_ubicaciones(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"],
        ["Deposito A", "Deposito B"],
    )

    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == ["Deposito A", "Deposito B"]


def test_reemplazar_borra_lo_anterior(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito B"]
    )

    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == ["Deposito B"]


def test_sin_asignar_devuelve_vacio(con, escenario):
    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == []


def test_reemplazar_por_vacio_deja_sin_asignacion(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    asignaciones.reemplazar(con, escenario["pasada_id"], escenario["juan"]["id"], [])

    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == []


def test_una_pasada_nueva_arranca_sin_asignaciones(con, escenario):
    """Un reconteo es justamente para que otra persona revise un sector."""
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-16T10:00:00Z"),
    )
    pasada_2_id = cursor.lastrowid

    assert asignaciones.de_operario(con, pasada_2_id, escenario["juan"]["id"]) == []


def test_ubicaciones_distintas_del_maestro(con, escenario):
    assert asignaciones.ubicaciones_distintas(con, escenario["sesion_id"]) == [
        "Deposito A", "Deposito B",
    ]


def test_ubicaciones_distintas_ignora_articulos_sin_ubicacion(con):
    sesion_id = sesiones.crear(con, "Cliente Y")
    contenido = "sku,detalle\nA,Tornillo\n".encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert asignaciones.ubicaciones_distintas(con, sesion_id) == []


def test_operarios_con_ubicaciones_sin_sesion_abierta(con):
    """Sin sesión abierta no hay pasada a la cual asignar nada."""
    operarios.crear(con, "Juan")

    lista = asignaciones.operarios_con_ubicaciones(con)

    assert lista[0]["ubicaciones_asignadas"] == []


def test_operarios_con_ubicaciones_de_la_pasada_abierta(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    lista = asignaciones.operarios_con_ubicaciones(con)
    juan = next(o for o in lista if o["id"] == escenario["juan"]["id"])

    assert juan["ubicaciones_asignadas"] == ["Deposito A"]
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_asignaciones.py -v --rootdir .\servidor`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repos.asignaciones'`

- [ ] **Step 3: Crear el repositorio**

Crear `servidor/app/repos/asignaciones.py`:

```python
"""A quién le toca cada ubicación, pasada por pasada.

No es historial de conteos: es logística de antes de contar. Reemplazar el
reparto no reescribe ningún hecho — los conteos ya guardados conservan el
`fuera_asignacion` que tenían al guardarse (ver `repos/conteos.py`).
"""

from app import reloj
from app.repos import operarios, sesiones


def reemplazar(con, pasada_id, operario_id, ubicaciones):
    """Reemplaza el reparto completo de un operario para esta pasada."""
    ahora = reloj.ahora()
    limpias = sorted({
        u.strip() for u in ubicaciones
        if isinstance(u, str) and u.strip()
    })

    with con:
        con.execute(
            "DELETE FROM asignacion WHERE pasada_id = ? AND operario_id = ?",
            (pasada_id, operario_id),
        )
        con.executemany(
            "INSERT INTO asignacion (pasada_id, operario_id, ubicacion, "
            "fecha_asignacion) VALUES (?, ?, ?, ?)",
            [(pasada_id, operario_id, u, ahora) for u in limpias],
        )

    return limpias


def de_operario(con, pasada_id, operario_id):
    filas = con.execute(
        "SELECT ubicacion FROM asignacion WHERE pasada_id = ? AND operario_id = ? "
        "ORDER BY ubicacion",
        (pasada_id, operario_id),
    ).fetchall()
    return [fila["ubicacion"] for fila in filas]


def ubicaciones_distintas(con, sesion_id):
    """Las ubicaciones del maestro de esta sesión, para elegir qué asignar."""
    filas = con.execute(
        "SELECT DISTINCT ubicacion FROM articulo "
        "WHERE sesion_id = ? AND fusionado_en IS NULL "
        "AND ubicacion IS NOT NULL AND ubicacion != '' "
        "ORDER BY ubicacion",
        (sesion_id,),
    ).fetchall()
    return [fila["ubicacion"] for fila in filas]


def operarios_con_ubicaciones(con):
    """Los operarios activos, cada uno con lo que tiene asignado en la
    pasada de la sesión abierta.

    Sin sesión abierta no hay pasada a la cual asignar nada, así que todos
    quedan con la lista vacía.
    """
    lista = operarios.listar(con)

    sesion = sesiones.sesion_abierta(con)
    if sesion is None:
        for operario in lista:
            operario["ubicaciones_asignadas"] = []
        return lista

    pasada = sesiones.pasada_abierta(con, sesion["id"])
    for operario in lista:
        operario["ubicaciones_asignadas"] = de_operario(
            con, pasada["id"], operario["id"]
        )
    return lista
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_asignaciones.py -v --rootdir .\servidor`
Expected: PASS, 9 tests.

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/asignaciones.py servidor/tests/test_asignaciones.py
git commit -m "Agrega el repositorio de asignaciones de sectores

La tabla asignacion ya existia en el esquema, pensada y nunca usada. Este
repositorio completa la idea: quien tiene asignada cada ubicacion en cada
pasada, y de donde salen las ubicaciones para elegir -las del maestro de
la sesion actual-.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: El conteo se marca fuera de asignación al guardarse

**Files:**
- Modify: `servidor/app/repos/conteos.py`
- Test: `servidor/tests/test_conteos.py`

**Interfaces:**
- Consumes: `asignaciones.de_operario(con, pasada_id, operario_id) -> list[str]` (Task 1)

- [ ] **Step 1: Escribir los tests**

Agregar a `servidor/tests/test_conteos.py`, después del import existente:

```python
from app.repos import asignaciones, conteos, operarios, sesiones
```

(reemplaza la línea `from app.repos import conteos, operarios, sesiones` ya
existente al principio del archivo).

Agregar estos tests al final del archivo:

```python
def test_sin_asignacion_no_se_marca(con, escenario):
    conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="Deposito A"),
    )

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 0


def test_contar_en_la_ubicacion_asignada_no_se_marca(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(
        con, pasada["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="Deposito A"),
    )

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 0


def test_contar_fuera_de_lo_asignado_se_marca(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(
        con, pasada["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="Deposito B"),
    )

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 1


def test_sin_ubicacion_conocida_no_se_marca(con, escenario):
    """El artículo del escenario no tiene ubicación en el maestro, y este
    evento tampoco trae una corrección: no hay con qué comparar."""
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(
        con, pasada["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1"))

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 0


def test_usa_la_ubicacion_del_articulo_si_no_hay_correccion(con):
    sesion_id = sesiones.crear(con, "Cliente Z")
    contenido = "sku,detalle,ubic\nA,Tornillo,Deposito A\n".encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "ubicacion": "ubic",
    })
    juan = operarios.crear(con, "Juan")
    pasada = sesiones.pasada_abierta(con, sesion_id)
    asignaciones.reemplazar(con, pasada["id"], juan["id"], ["Deposito B"])

    conteos.registrar(con, sesion_id, juan["id"], {
        "uuid": "u-1", "codigo": "A", "cantidad": 1000,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
    })

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 1
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_conteos.py -v --rootdir .\servidor -k fuera_de_asignacion or fuera_asignacion or usa_la_ubicacion`
Expected: FAIL — todos dan `fuera_asignacion == 1` cuando se esperaba `0`, o viceversa: hoy siempre se graba `0`.

- [ ] **Step 3: Calcular `fuera_asignacion` al registrar**

En `servidor/app/repos/conteos.py`, cambiar el import del principio:

```python
from app import reloj
from app.repos import asignaciones, sesiones
```

Agregar, antes de `def registrar(`:

```python
def _fuera_de_asignacion(con, pasada_id, operario_id, ubicacion_efectiva):
    """Si este conteo cae fuera de lo que tiene asignado el operario.

    Se calcula una sola vez, al guardar: es un hecho de este conteo, no una
    pregunta que se vuelve a hacer cada vez que alguien mira el tablero. Si
    más tarde cambia el reparto, los conteos ya hechos no cambian de opinión.
    """
    if ubicacion_efectiva is None:
        # Nada con qué comparar: ni el artículo ni la corrección del
        # operario dicen dónde estaba.
        return 0

    asignadas = asignaciones.de_operario(con, pasada_id, operario_id)
    if not asignadas:
        # Sin ninguna asignación cargada no hay restricción: si se marcara
        # todo, el tablero se llenaría de avisos el primer día que se usa
        # la función, antes de terminar de repartir sectores a todo el
        # equipo.
        return 0

    return 0 if ubicacion_efectiva in asignadas else 1
```

Dentro de `registrar(...)`, reemplazar:

```python
    pasada = sesiones.pasada_abierta(con, sesion_id)

    con.execute(
        """
        INSERT INTO conteo (
            uuid, sesion_id, pasada_id, articulo_id, cantidad, operario_id,
            ubicacion_real, observaciones, fuera_asignacion,
            timestamp_dispositivo, timestamp_servidor, anula_uuid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            evento["uuid"], sesion_id, pasada["id"], articulo["id"],
            cantidad, operario_id,
            evento.get("ubicacion_real"), evento.get("observaciones"),
            evento["timestamp_dispositivo"], reloj.ahora(), anula,
        ),
    )
    con.commit()
    return "registrado"
```

por:

```python
    pasada = sesiones.pasada_abierta(con, sesion_id)

    # La ubicación real prevalece sobre la del maestro: es la que el
    # operario corrigió a mano, y es la que de verdad recorrió.
    ubicacion_efectiva = evento.get("ubicacion_real") or articulo["ubicacion"]
    fuera = _fuera_de_asignacion(con, pasada["id"], operario_id, ubicacion_efectiva)

    con.execute(
        """
        INSERT INTO conteo (
            uuid, sesion_id, pasada_id, articulo_id, cantidad, operario_id,
            ubicacion_real, observaciones, fuera_asignacion,
            timestamp_dispositivo, timestamp_servidor, anula_uuid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evento["uuid"], sesion_id, pasada["id"], articulo["id"],
            cantidad, operario_id,
            evento.get("ubicacion_real"), evento.get("observaciones"), fuera,
            evento["timestamp_dispositivo"], reloj.ahora(), anula,
        ),
    )
    con.commit()
    return "registrado"
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_conteos.py -v --rootdir .\servidor`
Expected: PASS, todos — los que ya había más los 5 nuevos.

- [ ] **Step 5: Correr toda la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS. Ningún otro archivo llama a `registrar` con una firma
distinta, así que nada más debería moverse.

- [ ] **Step 6: Commit**

```bash
git add servidor/app/repos/conteos.py servidor/tests/test_conteos.py
git commit -m "Calcula fuera_asignacion al registrar el conteo

La columna existia en el esquema y siempre se grababa en 0. Se calcula una
sola vez, al guardar: es un hecho de este conteo, no algo que se recalcula
cada vez que alguien mira el tablero. Sin ninguna asignacion cargada no se
marca nada, para no llenar el tablero de avisos el primer dia que se usa
la funcion.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: El tablero y la exportación muestran la marca

**Files:**
- Modify: `servidor/app/servicios/tablero.py`
- Modify: `servidor/app/servicios/exportacion.py`
- Test: `servidor/tests/test_tablero.py`
- Test: `servidor/tests/test_exportacion.py`

**Interfaces:**
- Produces: cada fila de `tablero.filas(...)` gana la clave
  `"fuera_asignacion": bool`. El CSV de `exportacion.detalle(...)` gana la
  columna `fuera_asignacion` (`"SI"` o `""`), al final de
  `COLUMNAS_DETALLE`.

- [ ] **Step 1: Escribir los tests del tablero**

Agregar a `servidor/tests/test_tablero.py`, cambiando el import del
principio:

```python
from app.repos import asignaciones, conteos, operarios, sesiones
```

(reemplaza la línea `from app.repos import conteos, operarios, sesiones` ya
existente).

Agregar al final del archivo:

```python
def test_marca_fuera_de_asignacion(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(con, pasada["id"], escenario["juan"]["id"], ["P-2"])

    contar(con, escenario, "A", 24000, "u-1")  # A está en P-1, Juan tiene P-2

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")
    assert fila["fuera_asignacion"] is True


def test_sin_marca_cuando_coincide_la_asignacion(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(con, pasada["id"], escenario["juan"]["id"], ["P-1"])

    contar(con, escenario, "A", 24000, "u-1")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")
    assert fila["fuera_asignacion"] is False


def test_sin_contar_no_se_marca(con, escenario):
    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "B")
    assert fila["fuera_asignacion"] is False
```

- [ ] **Step 2: Escribir los tests de la exportación**

Agregar a `servidor/tests/test_exportacion.py`, cambiando el import del
principio:

```python
from app.repos import asignaciones, conteos, operarios, sesiones
```

(reemplaza la línea `from app.repos import conteos, operarios, sesiones` ya
existente).

Reemplazar el test `test_detalle_tiene_las_columnas_del_spec` existente por:

```python
def test_detalle_tiene_las_columnas_del_spec(con, escenario):
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert list(filas[0].keys()) == [
        "fecha", "fecha_sincronizacion", "pasada", "operario", "sku",
        "descripcion", "unidad", "cantidad", "ubicacion", "ubicacion_real",
        "observaciones", "anulado", "fuera_asignacion",
    ]
```

Agregar al final del archivo:

```python
def test_detalle_sin_asignacion_no_marca(con, escenario):
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert filas[0]["fuera_asignacion"] == ""


def test_detalle_marca_fuera_de_asignacion(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(con, pasada["id"], escenario["juan"]["id"], ["Otro deposito"])
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "B", "cantidad": 50000,
        "timestamp_dispositivo": "2026-08-10T10:10:00Z",
    })

    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))
    fila_b = next(f for f in filas if f["sku"] == "B")

    assert fila_b["fuera_asignacion"] == "SI"
```

- [ ] **Step 3: Correr y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_tablero.py .\servidor\tests\test_exportacion.py -v --rootdir .\servidor`
Expected: FAIL — `KeyError: 'fuera_asignacion'` en el tablero, y la
aserción de columnas del detalle no coincide.

- [ ] **Step 4: Sumar la marca al tablero**

En `servidor/app/servicios/tablero.py`, dentro de `_consulta_base()`,
agregar `MAX(v.fuera_asignacion) AS fuera_asignacion` junto a las otras
columnas agregadas del `SELECT` final (al lado de `SUM(v.cantidad) AS
total`):

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
            SUM(v.cantidad) AS total,
            COUNT(v.uuid) AS cantidad_conteos,
            MAX(v.fuera_asignacion) AS fuera_asignacion,
            MAX(v.timestamp_servidor) AS fecha
        FROM articulo a
```

(Es la misma consulta que ya está: solo se agrega la línea `MAX(v.fuera_asignacion) ...`
entre `COUNT(v.uuid) AS cantidad_conteos,` y `MAX(v.timestamp_servidor) AS fecha,`.)

En `_armar_fila(...)`, agregar la clave al diccionario que devuelve, al
lado de `"posible_error_carga"`:

```python
        "posible_error_carga": posible_error,
        # MAX() sobre un LEFT JOIN sin conteos da NULL, y bool(None) es
        # False: un artículo sin contar no puede estar fuera de asignación.
        "fuera_asignacion": bool(fila["fuera_asignacion"]),
        "fecha": fila["fecha"],
```

- [ ] **Step 5: Sumar la columna a la exportación**

En `servidor/app/servicios/exportacion.py`, agregar `"fuera_asignacion"` al
final de `COLUMNAS_DETALLE`:

```python
COLUMNAS_DETALLE = [
    "fecha", "fecha_sincronizacion", "pasada", "operario", "sku",
    "descripcion", "unidad", "cantidad", "ubicacion", "ubicacion_real",
    "observaciones", "anulado", "fuera_asignacion",
]
```

En `detalle(...)`, agregar `c.fuera_asignacion` al `SELECT` de la consulta
cruda:

```python
        SELECT c.uuid, c.cantidad, c.ubicacion_real, c.observaciones,
               c.timestamp_dispositivo, c.timestamp_servidor, c.anula_uuid,
               c.fuera_asignacion,
               a.id AS articulo_id, a.sku, a.descripcion, a.unidad, a.ubicacion,
               o.nombre AS operario, p.numero AS pasada_numero
        FROM conteo c
```

Y en el bucle que arma `filas`, agregar la clave al diccionario, al lado de
`"anulado"`:

```python
            "anulado": "SI" if (es_anulacion or fila["uuid"] in anulados) else "",
            "fuera_asignacion": "SI" if fila["fuera_asignacion"] else "",
        })
```

- [ ] **Step 6: Correr y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_tablero.py .\servidor\tests\test_exportacion.py -v --rootdir .\servidor`
Expected: PASS, todos.

- [ ] **Step 7: Mostrar la marca en el panel**

En `servidor/panel/app.js`, dentro de `dibujarFila(fila)`, agregar una
segunda marca, con el mismo patrón que `marca` (el de
`posible_error_carga`):

```javascript
function dibujarFila(fila) {
  const clase = ESTADOS[fila.estado] || "";
  const marca = fila.posible_error_carga
    ? `<span class="marca" title="Revisar antes de recontar: ` +
      `${esc(fila.posible_error_carga)}">⌨ ${esc(fila.posible_error_carga)}</span>`
    : "";
  const marcaAsignacion = fila.fuera_asignacion
    ? `<span class="marca" title="Alguno de los conteos de este artículo se ` +
      `hizo fuera de la ubicación asignada al operario. El detalle exportado ` +
      `dice quién y dónde.">⚑ fuera de sector</span>`
    : "";
  const fecha = (fila.fecha || "").replace("T", " ").replace("Z", "");

  return `
    <tr>
      <td class="num">${esc(fila.id_orden)}</td>
      <td>${esc(fila.tipo)}</td>
      <td>${esc(fila.material)}</td>
      <td>${esc(fila.sku)}</td>
      <td>${esc(fila.descripcion)}</td>
      <td>${esc(fila.grupo)}</td>
      <td>${esc(fila.ubicacion)}</td>
      <td>${esc(fila.ubicacion_real)}</td>
      <td>${esc(fila.unidad)}</td>
      <td class="num">${esc(milesimasATexto(fila.stock_sistema))}</td>
      <td class="num">${esc(milesimasATexto(fila.ultimo_conteo))}</td>
      <td class="num">${esc(milesimasATexto(fila.dif))}</td>
      <td>
        <span class="estado ${clase}">${esc(fila.estado)}</span>
        ${marca}
        ${marcaAsignacion}
      </td>
      <td>${esc(fecha)}</td>
      <td>${esc(fila.observaciones)}</td>
    </tr>`;
}
```

`marcaAsignacion` no interpola ningún dato del servidor —el texto es fijo—,
así que no hace falta `esc(...)` ahí; el resto de la función sigue igual.

- [ ] **Step 8: Correr toda la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add servidor/app/servicios/tablero.py servidor/app/servicios/exportacion.py \
        servidor/panel/app.js servidor/tests/test_tablero.py servidor/tests/test_exportacion.py
git commit -m "Muestra los conteos fuera de asignacion en el tablero y la exportacion

Un articulo con algun conteo fuera de lo asignado en su pasada vigente
queda marcado en el tablero -senal de que hay algo para revisar, no un
desglose conteo por conteo- y el CSV de detalle dice exactamente quien y
donde.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: La asignación desde el panel

**Files:**
- Modify: `servidor/app/api/panel.py`
- Modify: `servidor/panel/index.html`
- Modify: `servidor/panel/app.js`
- Modify: `servidor/panel/estilos.css`
- Test: `servidor/tests/test_api.py`
- Test: `servidor/tests/test_panel_estatico.py`

**Interfaces:**
- Consumes: `asignaciones.ubicaciones_distintas`, `asignaciones.reemplazar`,
  `asignaciones.operarios_con_ubicaciones` (Task 1).
- Produces:
  - `GET /api/sesiones/{sesion_id}/ubicaciones` → `list[str]`
  - `PUT /api/sesiones/{sesion_id}/operarios/{operario_id}/asignacion` con
    cuerpo `{"ubicaciones": [...]}` → `{"ubicaciones": [...]}`
  - `GET /api/operarios` ahora incluye `"ubicaciones_asignadas"` en cada
    operario.

- [ ] **Step 1: Escribir los tests de la API**

Agregar a `servidor/tests/test_api.py`, después de las constantes del
principio del archivo:

```python
CSV_CON_UBICACION = (
    "sku,detalle,ubic\n"
    "A,Tornillo,Deposito A\n"
    "B,Tuerca,Deposito B\n"
).encode("utf-8")


def importar_con_ubicacion(cliente, sesion_id):
    return cliente.post(
        f"/api/sesiones/{sesion_id}/maestro",
        files={"archivo": ("maestro.csv", CSV_CON_UBICACION, "text/csv")},
        data={"mapeo": '{"sku": "sku", "descripcion": "detalle", "ubicacion": "ubic"}'},
    )
```

Agregar estos tests al final del archivo:

```python
def test_ubicaciones_de_la_sesion_abierta(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/ubicaciones")

    assert respuesta.status_code == 200
    assert respuesta.json() == ["Deposito A", "Deposito B"]


def test_ubicaciones_de_sesion_inexistente_da_404(cliente):
    assert cliente.get("/api/sesiones/9999/ubicaciones").status_code == 404


def test_operarios_traen_ubicaciones_asignadas_vacias_por_defecto(cliente, sesion):
    cliente.post("/api/operarios", json={"nombre": "Juan"})

    respuesta = cliente.get("/api/operarios")

    assert respuesta.json()[0]["ubicaciones_asignadas"] == []


def test_asignar_ubicaciones_a_un_operario(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ubicaciones"] == ["Deposito A"]

    lista = cliente.get("/api/operarios").json()
    juan = next(o for o in lista if o["id"] == operario["id"])
    assert juan["ubicaciones_asignadas"] == ["Deposito A"]


def test_asignar_reemplaza_lo_anterior(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"]},
    )

    cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito B"]},
    )

    lista = cliente.get("/api/operarios").json()
    juan = next(o for o in lista if o["id"] == operario["id"])
    assert juan["ubicaciones_asignadas"] == ["Deposito B"]


def test_asignar_a_un_operario_inexistente_da_404(cliente, sesion):
    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/9999/asignacion",
        json={"ubicaciones": []},
    )
    assert respuesta.status_code == 404


def test_asignar_con_la_sesion_cerrada_da_409(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post(f"/api/sesiones/{sesion['id']}/cerrar")

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": []},
    )

    assert respuesta.status_code == 409


def test_asignar_sin_lista_de_ubicaciones_da_400(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={},
    )

    assert respuesta.status_code == 400
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -v --rootdir .\servidor -k ubicacion or asignar`
Expected: FAIL — 404 en las rutas nuevas (no existen todavía), y
`ubicaciones_asignadas` no está en la respuesta de `/api/operarios`.

- [ ] **Step 3: Agregar los endpoints**

En `servidor/app/api/panel.py`, cambiar el import de repos del principio:

```python
from app.repos import asignaciones, operarios, sesiones
```

Reemplazar `listar_operarios` por:

```python
@router.get("/operarios")
def listar_operarios(request: Request):
    return asignaciones.operarios_con_ubicaciones(_con(request))
```

Agregar, después de `ver_resumen` (que ya existe):

```python
@router.get("/sesiones/{sesion_id}/ubicaciones")
def listar_ubicaciones(sesion_id: int, request: Request):
    con = _con(request)
    try:
        sesiones.obtener(con, sesion_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return asignaciones.ubicaciones_distintas(con, sesion_id)
```

Agregar, después de `crear_operario` (que ya existe):

```python
@router.put("/sesiones/{sesion_id}/operarios/{operario_id}/asignacion")
async def asignar_ubicaciones(sesion_id: int, operario_id: int, request: Request):
    con = _con(request)
    cuerpo = await request.json()

    ubicaciones_pedidas = cuerpo.get("ubicaciones")
    if not isinstance(ubicaciones_pedidas, list):
        raise HTTPException(
            status_code=400, detail="«ubicaciones» tiene que ser una lista"
        )

    try:
        sesion = sesiones.obtener(con, sesion_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    if sesion["estado"] != "abierta":
        raise HTTPException(
            status_code=409,
            detail="No se puede asignar: la sesión ya está cerrada",
        )

    if operarios.obtener(con, operario_id) is None:
        raise HTTPException(
            status_code=404, detail=f"No existe el operario {operario_id}"
        )

    pasada = sesiones.pasada_abierta(con, sesion_id)
    guardadas = asignaciones.reemplazar(
        con, pasada["id"], operario_id, ubicaciones_pedidas
    )
    return {"ubicaciones": guardadas}
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -v --rootdir .\servidor`
Expected: PASS, todos.

- [ ] **Step 5: El diálogo en el HTML**

En `servidor/panel/index.html`, agregar antes de `</section>` que cierra
`<section id="vista-operarios" ...>` (después de `<ul id="lista-operarios"
...></ul>`):

```html
      <dialog id="dialogo-sectores">
        <h3 id="sectores-titulo"></h3>
        <div id="sectores-lista"></div>
        <menu>
          <button id="cerrar-sectores" type="button">Cancelar</button>
          <button id="guardar-sectores" type="button">Guardar</button>
        </menu>
      </dialog>
```

- [ ] **Step 6: El diálogo en el JavaScript**

En `servidor/panel/app.js`, reemplazar `dibujarOperario` por:

```javascript
function dibujarOperario(operario, haySesion) {
  // Sin sesión abierta no hay pasada a la cual asignar nada: el enlace no
  // aparece.
  const sectores = haySesion
    ? `<button class="secundario" data-sectores="${esc(operario.id)}">Sectores</button>`
    : "";
  return `
    <li class="operario">
      <div>
        <strong>${esc(operario.nombre)}</strong>
        <div class="token">
          <input readonly value="${esc(operario.token_dispositivo)}"
                 aria-label="Token de ${esc(operario.nombre)}">
          <button class="secundario" data-copiar="${esc(operario.token_dispositivo)}">
            Copiar
          </button>
          ${sectores}
        </div>
        <p class="ayuda">Escaneá este código desde la app para vincular el celular.</p>
      </div>
      <img class="qr" src="/api/operarios/${esc(operario.id)}/qr"
           alt="Código QR de vinculación de ${esc(operario.nombre)}">
    </li>`;
}

/** Una casilla de ubicación para el diálogo de sectores, tildada si ya está asignada. */
function dibujarCasillaUbicacion(ubicacion, asignadas) {
  const marcada = asignadas.includes(ubicacion) ? " checked" : "";
  return `<label class="casilla">
    <input type="checkbox" value="${esc(ubicacion)}"${marcada}> ${esc(ubicacion)}
  </label>`;
}

async function abrirSectores(operarioId) {
  const operario = estado.operarios.find((o) => String(o.id) === String(operarioId));
  if (!operario || !estado.sesion) return;

  const ubicaciones = await pedir(`/api/sesiones/${estado.sesion.id}/ubicaciones`);

  // Por textContent: es el nombre de una persona, dato como cualquier otro.
  $("#sectores-titulo").textContent = `Sectores de ${operario.nombre}`;
  $("#sectores-lista").innerHTML = ubicaciones.length
    ? ubicaciones.map((u) => dibujarCasillaUbicacion(u, operario.ubicaciones_asignadas)).join("")
    : "<p>El maestro todavía no tiene ubicaciones cargadas.</p>";

  $("#dialogo-sectores").dataset.operario = operarioId;
  $("#dialogo-sectores").showModal();
}

async function guardarSectores() {
  const dialogo = $("#dialogo-sectores");
  const operarioId = dialogo.dataset.operario;
  const ubicaciones = [...dialogo.querySelectorAll("input[type=checkbox]:checked")]
    .map((casilla) => casilla.value);

  try {
    await pedir(
      `/api/sesiones/${estado.sesion.id}/operarios/${operarioId}/asignacion`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ubicaciones }),
      },
    );
    dialogo.close();
    await cargarOperarios();
  } catch (error) {
    alert(error.message);
  }
}
```

Reemplazar `cargarOperarios` por:

```javascript
async function cargarOperarios() {
  const lista = await pedir("/api/operarios");
  // Se guarda para poder buscar por id al abrir el diálogo de sectores:
  // el click solo trae el id, no todo el operario.
  estado.operarios = lista;
  $("#lista-operarios").innerHTML =
    lista.map((o) => dibujarOperario(o, !!estado.sesion)).join("")
    || "<li>Todavía no hay operarios.</li>";
  await cargarInstalacion();
}
```

En `conectarEventos()`, reemplazar el bloque:

```javascript
  $("#lista-operarios").addEventListener("click", (evento) => {
    if (evento.target.dataset.copiar) copiarToken(evento.target);
  });
```

por:

```javascript
  $("#lista-operarios").addEventListener("click", (evento) => {
    if (evento.target.dataset.copiar) copiarToken(evento.target);
    if (evento.target.dataset.sectores) abrirSectores(evento.target.dataset.sectores);
  });

  $("#guardar-sectores").addEventListener("click", guardarSectores);
  $("#cerrar-sectores").addEventListener("click", () => $("#dialogo-sectores").close());
```

- [ ] **Step 7: Un poco de estilo**

En `servidor/panel/estilos.css`, agregar al final:

```css
dialog { max-width: 28rem; border: 1px solid var(--borde); border-radius: 8px; }

#sectores-lista {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.6rem 0;
}
```

- [ ] **Step 8: Escribir el test del guardián de escapado y de estructura**

Agregar a `servidor/tests/test_panel_estatico.py`:

```python
def test_el_panel_ofrece_asignar_sectores():
    """Sin esto no hay forma de repartir ubicaciones desde el panel."""
    html = (RUTA_PANEL / "index.html").read_text(encoding="utf-8")
    js = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert 'id="dialogo-sectores"' in html
    assert "showModal" in js
    assert "/asignacion" in js
```

- [ ] **Step 9: Correr toda la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS. El test
`test_los_datos_del_servidor_se_escapan_antes_de_ir_al_html` ya audita todo
`app.js`; como `dibujarCasillaUbicacion` y `dibujarOperario` envuelven todo
en `esc(...)`, no hace falta tocar la lista `DATOS_DEL_SERVIDOR`.

- [ ] **Step 10: Verificar en el navegador**

```powershell
.\"Iniciar servidor.bat"
```

1. Crear una sesión, importar un maestro con columna de ubicación, y crear
   dos operarios.
2. En la pestaña Operarios, tocar **Sectores** en uno de ellos: tiene que
   verse un diálogo con una casilla por cada ubicación distinta del
   maestro.
3. Tildar una o dos, tocar **Guardar**: el diálogo se cierra y, al volver a
   abrir **Sectores** para ese mismo operario, las casillas siguen
   tildadas.
4. Con el celular (ver el plan de código a mano si hace falta), contar un
   artículo de una ubicación **distinta** de la asignada: en el tablero
   tiene que aparecer la marca **⚑ fuera de sector** al lado del estado, y
   al pasar el mouse por encima, el texto explicativo.
5. Exportar el detalle (botón de exportación que ya existe) y confirmar
   que la fila de ese conteo tiene `SI` en la columna `fuera_asignacion`.
6. Cerrar la sesión y volver a la pestaña Operarios: el enlace **Sectores**
   tiene que desaparecer de todos los operarios.

Si algún paso falla, no seguir: es lo que esta tarea viene a resolver.

- [ ] **Step 11: Commit**

```bash
git add servidor/app/api/panel.py servidor/panel/index.html servidor/panel/app.js \
        servidor/panel/estilos.css servidor/tests/test_api.py servidor/tests/test_panel_estatico.py
git commit -m "Suma la asignacion de sectores al panel

Un dialogo por operario, con una casilla por cada ubicacion del maestro
actual. Sin sesion abierta no aparece: no hay pasada a la cual asignar
nada. Cierra el circulo del modelo que ya existia sin usar.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Verificación final del plan

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Todo en verde, y sobre todo: **se le puede asignar a cada operario qué
ubicaciones le tocan en la pasada en curso, y un conteo hecho fuera de eso
queda marcado —en el tablero y en el detalle exportado— sin bloquear a
nadie en el momento.**
