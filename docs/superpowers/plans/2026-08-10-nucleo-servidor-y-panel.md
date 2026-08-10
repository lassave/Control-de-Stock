# Núcleo del servidor y panel — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el servidor que recibe y consolida los conteos, más el panel mínimo para importar el maestro, ver el tablero y exportar los resultados.

**Architecture:** Servidor FastAPI con SQLite accedido por SQL directo (sin ORM), organizado en tres capas: repositorios que hablan con la base, servicios que aplican reglas de negocio, y routers que exponen la API. El panel es HTML/CSS/JS sin dependencias, servido por el mismo proceso, que consume esa API. Toda la lógica de negocio vive en los servicios y se prueba sin levantar el servidor.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, sqlite3 (biblioteca estándar), pytest, httpx. Panel en HTML/CSS/JavaScript vanilla.

Este plan corresponde a las secciones 3, 4, 5 (parcial), 10 y 11 del spec `docs/superpowers/specs/2026-08-10-control-de-stock-design.md`.

**Queda para planes posteriores:** conteos sucesivos (pasadas 2 en adelante), asignación de ubicaciones, detección de doble conteo, bitácora e historial por artículo, alta rápida desde el dispositivo, vinculación de códigos, respaldos por operario, importación de ajustes e informe de cierre. El esquema de base de datos ya contempla todo eso para no migrar la base a mitad del desarrollo.

**Sí entra acá:** el cálculo de la diferencia valorizada, porque es una columna del tablero y sale casi gratis una vez que el costo está en el maestro.

## Global Constraints

- **Cantidades en milésimas, siempre enteras.** Toda cantidad se guarda como `INTEGER` en milésimas: `24 UN` → `24000`, `3,5 KG` → `3500`. SQLite usa punto flotante para `REAL`, y sumar miles de decimales acumula error. Nunca guardar cantidades como `REAL`.
- **Importes en centavos, siempre enteros.** Misma razón.
- **Sin dependencias externas en el navegador.** Nada de CDN, fuentes remotas ni librerías descargadas: durante el conteo puede no haber internet. Todo se sirve desde el servidor.
- **`stock_sistema` y `costo_unitario` nunca salen en respuestas destinadas a dispositivos.** Requisito de conteo a ciegas (spec, sección 5).
- **Fechas en ISO 8601 UTC**, guardadas como texto: `2026-08-10T14:32:05Z`.
- **Textos de interfaz en castellano rioplatense**, sin jerga técnica.
- **Python 3.11 mínimo.** El intérprete del proyecto es el entorno virtual: `servidor\.venv\Scripts\python.exe`. En esta máquina el `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta nada, así que **todos los comandos usan el intérprete del venv por ruta**, no `python` a secas.
- Los mensajes de commit van en castellano, en presente, describiendo el efecto.

---

### Task 1: Andamiaje del proyecto y esquema de base de datos

**Files:**
- Create: `servidor/requirements.txt`
- Create: `servidor/app/__init__.py`
- Create: `servidor/app/esquema.sql`
- Create: `servidor/app/db.py`
- Create: `servidor/tests/__init__.py`
- Create: `servidor/tests/conftest.py`
- Create: `servidor/tests/test_db.py`

**Interfaces:**
- Consumes: nada (primera tarea)
- Produces:
  - `db.conectar(ruta: str | Path) -> sqlite3.Connection` — abre la base con `row_factory` de diccionario y claves foráneas activas
  - `db.crear_esquema(con: sqlite3.Connection) -> None` — ejecuta `esquema.sql`, idempotente
  - Fixture `con` de pytest: conexión en memoria con el esquema ya creado

- [ ] **Step 1: Crear `servidor/requirements.txt`**

```
fastapi==0.115.6
uvicorn==0.34.0
python-multipart==0.0.20
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Crear `servidor/app/esquema.sql` con el modelo completo**

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sesion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    fecha_creacion      TEXT NOT NULL,
    estado              TEXT NOT NULL DEFAULT 'abierta',
    tolerancia_pct      REAL NOT NULL DEFAULT 2.0,
    tolerancia_min_abs  INTEGER NOT NULL DEFAULT 1000,
    CHECK (estado IN ('abierta', 'cerrada')),
    CHECK (typeof(tolerancia_min_abs) = 'integer')
);

-- Una sola sesión abierta a la vez: los dispositivos se vinculan a «la»
-- sesión abierta. El repositorio ya lo valida, pero dos hilos pueden pasar
-- esa validación a la vez; este índice lo vuelve imposible.
CREATE UNIQUE INDEX IF NOT EXISTS ix_sesion_abierta
    ON sesion(estado) WHERE estado = 'abierta';

CREATE TABLE IF NOT EXISTS pasada (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id       INTEGER NOT NULL REFERENCES sesion(id),
    numero          INTEGER NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'abierta',
    fecha_apertura  TEXT NOT NULL,
    fecha_cierre    TEXT,
    abierta_por     TEXT,
    cerrada_por     TEXT,
    UNIQUE (sesion_id, numero),
    CHECK (estado IN ('abierta', 'cerrada'))
);

CREATE TABLE IF NOT EXISTS unidad (
    codigo            TEXT PRIMARY KEY,
    nombre            TEXT NOT NULL,
    admite_decimales  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS articulo (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id       INTEGER NOT NULL REFERENCES sesion(id),
    id_orden        INTEGER NOT NULL,
    tipo            TEXT,
    material        TEXT,
    sku             TEXT NOT NULL,
    descripcion     TEXT NOT NULL,
    grupo           TEXT,
    ubicacion       TEXT,
    unidad          TEXT NOT NULL DEFAULT 'UN' REFERENCES unidad(codigo),
    stock_sistema   INTEGER NOT NULL DEFAULT 0,
    costo_unitario  INTEGER,
    origen          TEXT NOT NULL DEFAULT 'importado',
    ausente_erp     INTEGER NOT NULL DEFAULT 0,
    creado_por      TEXT,
    creado_en       TEXT NOT NULL,
    fusionado_en    INTEGER REFERENCES articulo(id),
    UNIQUE (sesion_id, sku),
    CHECK (origen IN ('importado', 'alta_rapida')),
    -- La afinidad INTEGER de SQLite no es una restricción de tipo: acepta y
    -- guarda un 3.5 como REAL. Sin este CHECK, un solo decimal colado anula
    -- en silencio la exactitud que justifica guardar milésimas y centavos.
    CHECK (typeof(stock_sistema) = 'integer'),
    CHECK (costo_unitario IS NULL OR typeof(costo_unitario) = 'integer')
);

CREATE TABLE IF NOT EXISTS codigo_barras (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id  INTEGER NOT NULL REFERENCES articulo(id),
    codigo       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_codigo_barras_codigo ON codigo_barras(codigo);

CREATE TABLE IF NOT EXISTS operario (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL UNIQUE,
    pin               TEXT,
    token_dispositivo TEXT NOT NULL UNIQUE,
    activo            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS conteo (
    uuid                    TEXT PRIMARY KEY,
    sesion_id               INTEGER NOT NULL REFERENCES sesion(id),
    pasada_id               INTEGER NOT NULL REFERENCES pasada(id),
    articulo_id             INTEGER NOT NULL REFERENCES articulo(id),
    cantidad                INTEGER NOT NULL,
    operario_id             INTEGER NOT NULL REFERENCES operario(id),
    ubicacion_real          TEXT,
    observaciones           TEXT,
    fuera_asignacion        INTEGER NOT NULL DEFAULT 0,
    timestamp_dispositivo   TEXT NOT NULL,
    timestamp_servidor      TEXT NOT NULL,
    anula_uuid              TEXT REFERENCES conteo(uuid),
    CHECK (typeof(cantidad) = 'integer')
);

CREATE INDEX IF NOT EXISTS ix_conteo_articulo ON conteo(articulo_id, pasada_id);
CREATE INDEX IF NOT EXISTS ix_conteo_anula ON conteo(anula_uuid);
CREATE INDEX IF NOT EXISTS ix_conteo_sesion ON conteo(sesion_id, operario_id);

CREATE TABLE IF NOT EXISTS pasada_item (
    pasada_id    INTEGER NOT NULL REFERENCES pasada(id),
    articulo_id  INTEGER NOT NULL REFERENCES articulo(id),
    PRIMARY KEY (pasada_id, articulo_id)
);

CREATE TABLE IF NOT EXISTS asignacion (
    pasada_id         INTEGER NOT NULL REFERENCES pasada(id),
    operario_id       INTEGER NOT NULL REFERENCES operario(id),
    ubicacion         TEXT NOT NULL,
    fecha_asignacion  TEXT NOT NULL,
    PRIMARY KEY (pasada_id, operario_id, ubicacion)
);

CREATE TABLE IF NOT EXISTS mapeo_columnas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE,
    definicion_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS codigo_aprendido (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sku               TEXT NOT NULL,
    codigo            TEXT NOT NULL,
    fecha             TEXT NOT NULL,
    sesion_origen_id  INTEGER REFERENCES sesion(id),
    UNIQUE (sku, codigo)
);

CREATE TABLE IF NOT EXISTS evento_auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id       INTEGER REFERENCES sesion(id),
    fecha           TEXT NOT NULL,
    autor           TEXT NOT NULL,
    accion          TEXT NOT NULL,
    entidad         TEXT,
    entidad_id      TEXT,
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    detalle         TEXT
);

INSERT OR IGNORE INTO unidad (codigo, nombre, admite_decimales) VALUES
    ('UN',   'Unidad',      0),
    ('CJ',   'Caja',        0),
    ('PACK', 'Pack',        0),
    ('KG',   'Kilogramo',   1),
    ('GR',   'Gramo',       1),
    ('LT',   'Litro',       1),
    ('ML',   'Mililitro',   1),
    ('MT',   'Metro',       1);
```

- [ ] **Step 3: Escribir el test que falla**

Crear `servidor/tests/test_db.py`:

```python
from app import db


def test_crear_esquema_crea_todas_las_tablas(con):
    filas = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    tablas = {fila["name"] for fila in filas}

    esperadas = {
        "sesion", "pasada", "unidad", "articulo", "codigo_barras",
        "operario", "conteo", "pasada_item", "asignacion",
        "mapeo_columnas", "codigo_aprendido", "evento_auditoria",
    }
    assert esperadas <= tablas


def test_unidades_precargadas(con):
    filas = con.execute("SELECT codigo, admite_decimales FROM unidad").fetchall()
    unidades = {fila["codigo"]: fila["admite_decimales"] for fila in filas}

    assert unidades["UN"] == 0
    assert unidades["KG"] == 1
    assert len(unidades) == 8


def test_crear_esquema_es_idempotente(con):
    db.crear_esquema(con)
    db.crear_esquema(con)

    total = con.execute("SELECT COUNT(*) AS n FROM unidad").fetchone()["n"]
    assert total == 8


def test_claves_foraneas_activas(con):
    activo = con.execute("PRAGMA foreign_keys").fetchone()[0]
    assert activo == 1


def crear_sesion(con):
    con.execute(
        "INSERT INTO sesion (id, nombre, fecha_creacion) VALUES (1, 'X', '2026-08-10T00:00:00Z')"
    )
    return 1


def crear_articulo(con, sesion_id, sku="A", unidad="UN", stock=0):
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, ?, 'Descripción', ?, ?, '2026-08-10T00:00:00Z')",
        (sesion_id, sku, unidad, stock),
    )


def test_rechaza_sku_repetido_en_la_misma_sesion(con):
    sesion_id = crear_sesion(con)
    crear_articulo(con, sesion_id, sku="A")

    with pytest.raises(sqlite3.IntegrityError):
        crear_articulo(con, sesion_id, sku="A")


def test_rechaza_pasada_de_una_sesion_inexistente(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO pasada (sesion_id, numero, fecha_apertura) "
            "VALUES (999, 1, '2026-08-10T00:00:00Z')"
        )


def test_rechaza_unidad_que_no_existe(con):
    """Un CSV que trae «CAJA» en vez de «CJ» no puede entrar sin que nadie lo note."""
    sesion_id = crear_sesion(con)

    with pytest.raises(sqlite3.IntegrityError):
        crear_articulo(con, sesion_id, unidad="CAJA")


def test_rechaza_stock_decimal(con):
    """Las milésimas solo son exactas si la columna guarda enteros de verdad."""
    sesion_id = crear_sesion(con)

    with pytest.raises(sqlite3.IntegrityError):
        crear_articulo(con, sesion_id, stock=3.5)


def test_solo_admite_una_sesion_abierta(con):
    """Los dispositivos se vinculan a «la» sesión abierta: no puede haber dos."""
    crear_sesion(con)

    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO sesion (nombre, fecha_creacion) "
            "VALUES ('Otra', '2026-08-10T00:00:00Z')"
        )


def test_el_contexto_descarta_lo_escrito_si_algo_falla(con):
    """Dos escrituras van juntas o no va ninguna."""
    with pytest.raises(sqlite3.IntegrityError):
        with con:
            crear_sesion(con)
            con.execute(
                "INSERT INTO pasada (sesion_id, numero, fecha_apertura) "
                "VALUES (999, 1, '2026-08-10T00:00:00Z')"
            )

    quedaron = con.execute("SELECT COUNT(*) AS n FROM sesion").fetchone()["n"]
    assert quedaron == 0


def test_el_contexto_confirma_al_salir_sin_error(con):
    with con:
        crear_sesion(con)

    con.rollback()
    quedaron = con.execute("SELECT COUNT(*) AS n FROM sesion").fetchone()["n"]
    assert quedaron == 1


def test_cada_hilo_recibe_su_propia_conexion(tmp_path):
    """Sin esto, el segundo operario que sincroniza en simultáneo recibe un error."""
    conexion = db.conectar(tmp_path / "hilos.db")
    db.crear_esquema(conexion)

    errores = []

    def consultar():
        try:
            conexion.execute("SELECT COUNT(*) FROM unidad").fetchone()
        except Exception as error:  # noqa: BLE001 — el test reporta cualquiera
            errores.append(error)

    hilos = [threading.Thread(target=consultar) for _ in range(4)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
```

El archivo empieza con estos imports:

```python
import sqlite3
import threading

import pytest

from app import db
```

Crear `servidor/tests/conftest.py`:

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402


@pytest.fixture
def con():
    conexion = db.conectar(":memory:")
    db.crear_esquema(conexion)
    yield conexion
    conexion.close()
```

Crear `servidor/app/__init__.py` y `servidor/tests/__init__.py` vacíos.

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_db.py -v`
Expected: FAIL con `ModuleNotFoundError` o `AttributeError: module 'app.db' has no attribute 'conectar'`

- [ ] **Step 5: Implementar `servidor/app/db.py`**

```python
"""Acceso a la base SQLite: conexión y creación del esquema."""

import sqlite3
import threading
from pathlib import Path

RUTA_ESQUEMA = Path(__file__).parent / "esquema.sql"


class ConexionPorHilo:
    """Conexión SQLite con una instancia propia por hilo.

    FastAPI atiende los endpoints sincrónicos en un pool de hilos, y SQLite
    prohíbe usar una conexión desde un hilo distinto del que la creó.
    Compartir una sola conexión hace fallar el segundo pedido simultáneo:
    exactamente lo que pasa cuando dos operarios sincronizan a la vez.

    Expone la misma interfaz mínima que `sqlite3.Connection` (`execute`,
    `executescript`, `commit`, `close`), así los repositorios la usan sin
    enterarse.
    """

    def __init__(self, ruta):
        self.ruta = str(ruta)
        self._local = threading.local()

    @property
    def _conexion(self):
        conexion = getattr(self._local, "conexion", None)
        if conexion is None:
            conexion = sqlite3.connect(self.ruta)
            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON")
            # Si otro hilo está escribiendo, esperar en vez de fallar con
            # "database is locked".
            conexion.execute("PRAGMA busy_timeout = 5000")
            if self.ruta != ":memory:":
                # WAL permite leer mientras otro hilo escribe: el tablero se
                # refresca solo mientras los celulares sincronizan.
                conexion.execute("PRAGMA journal_mode = WAL")
            self._local.conexion = conexion
        return conexion

    def execute(self, sql, parametros=()):
        return self._conexion.execute(sql, parametros)

    def executescript(self, script):
        return self._conexion.executescript(script)

    def commit(self):
        self._conexion.commit()

    def rollback(self):
        self._conexion.rollback()

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traza):
        """Confirma al salir bien y descarta al salir con error.

        Sin esto, una operación de dos escrituras que falla en la segunda
        deja la primera pendiente, y el commit de cualquier operación
        posterior la persiste: aparece una sesión sin pasada, que no se
        puede usar ni cerrar.
        """
        if tipo is None:
            self.commit()
        else:
            self.rollback()
        return False

    def close(self):
        conexion = getattr(self._local, "conexion", None)
        if conexion is not None:
            conexion.close()
            self._local.conexion = None


def conectar(ruta):
    """Abre la base y devuelve filas accesibles por nombre de columna.

    Con `:memory:` cada hilo tendría su propia base vacía, así que ese modo
    sirve solo para tests de un único hilo.
    """
    return ConexionPorHilo(ruta)


def crear_esquema(con):
    """Crea las tablas si no existen. Se puede ejecutar cuantas veces haga falta."""
    con.executescript(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    con.commit()
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_db.py -v`
Expected: PASS, todos en verde

- [ ] **Step 7: Commit**

```bash
git add servidor/
git commit -m "Crea el esquema de base de datos y el acceso a SQLite

Las cantidades se guardan como enteros en milesimas y los importes en
centavos: SQLite usa punto flotante para REAL y sumar miles de decimales
acumula error en el total del conteo.

El esquema incluye ya las tablas de pasadas sucesivas, asignacion,
bitacora y codigos aprendidos, que se usan en planes posteriores, para
no tener que migrar la base a mitad del desarrollo."
```

---

### Task 2: Conversión de cantidades

**Files:**
- Create: `servidor/app/cantidades.py`
- Create: `servidor/tests/test_cantidades.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `cantidades.a_milesimas(texto: str) -> int` — acepta `"24"`, `"3,5"`, `"3.5"`, `"1.234,56"`; lanza `ValueError` si no es un número
  - `cantidades.a_texto(milesimas: int) -> str` — devuelve `"24"` o `"3,5"`, con coma decimal y sin ceros sobrantes
  - `cantidades.a_centavos(texto: str) -> int`

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_cantidades.py`:

```python
import pytest

from app import cantidades


@pytest.mark.parametrize("texto, esperado", [
    ("24", 24000),
    ("0", 0),
    ("3,5", 3500),
    ("3.5", 3500),
    ("0,001", 1),
    ("1.234,56", 1234560),
    ("1,234.56", 1234560),
    ("  12  ", 12000),
    ("-4", -4000),
])
def test_a_milesimas(texto, esperado):
    assert cantidades.a_milesimas(texto) == esperado


@pytest.mark.parametrize("texto", [
    "", "   ", "abc", "1,2,3", None,
    ".", ",", "-", "-,",           # separador suelto: celda rota, no cero
    "1 2",                         # dos números pegados, no doce mil
    "1.23.456",                    # grupos de miles mal formados
    "inf", "-inf", "nan", "snan",  # Decimal los acepta; acá no son cantidades
    "1e3", "1_000",                # notación que ningún ERP exporta
])
def test_a_milesimas_rechaza_invalidos(texto):
    with pytest.raises(ValueError):
        cantidades.a_milesimas(texto)


@pytest.mark.parametrize("texto, esperado", [
    ("1.234.567", 1234567000),
    ("1,234,567", 1234567000),
])
def test_acepta_miles_agrupados_sin_decimales(texto, esperado):
    """«1.234.567» es la forma normal de escribir un número grande acá."""
    assert cantidades.a_milesimas(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("1,2345", 1235),   # redondea para arriba
    ("1,2344", 1234),   # redondea para abajo
    ("0,0005", 1),      # medio hacia arriba
    ("0,0004", 0),
])
def test_redondea_los_decimales_sobrantes(texto, esperado):
    """Truncar sesgaría todas las cantidades a la baja de forma sistemática."""
    assert cantidades.a_milesimas(texto) == esperado


def test_siempre_devuelve_enteros():
    """La base rechaza cualquier float: la columna tiene CHECK typeof integer."""
    for texto in ["24", "3,5", "1.234,56", "0,0005"]:
        assert isinstance(cantidades.a_milesimas(texto), int)
        assert isinstance(cantidades.a_centavos(texto), int)


@pytest.mark.parametrize("texto", ["", "abc", ".", "12,,5"])
def test_a_centavos_rechaza_invalidos(texto):
    with pytest.raises(ValueError):
        cantidades.a_centavos(texto)


@pytest.mark.parametrize("milesimas, esperado", [
    (24000, "24"),
    (0, "0"),
    (3500, "3,5"),
    (1, "0,001"),
    (1234560, "1234,56"),
    (-4000, "-4"),
])
def test_a_texto(milesimas, esperado):
    assert cantidades.a_texto(milesimas) == esperado


def test_ida_y_vuelta_no_pierde_precision():
    for texto in ["24", "3,5", "0,001", "999999,999"]:
        assert cantidades.a_texto(cantidades.a_milesimas(texto)) == texto


def test_suma_de_decimales_es_exacta():
    total = sum(cantidades.a_milesimas("0,1") for _ in range(10))
    assert total == cantidades.a_milesimas("1")


def test_a_centavos():
    assert cantidades.a_centavos("1.234,56") == 123456
    assert cantidades.a_centavos("10") == 1000
```

**Interfaces (recordatorio):** las tres funciones públicas llevan anotaciones de tipo — `a_milesimas(texto: str) -> int`, `a_centavos(texto: str) -> int`, `a_texto(milesimas: int) -> str` — porque todas las tareas siguientes las consumen.

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_cantidades.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.cantidades'`

- [ ] **Step 3: Implementar `servidor/app/cantidades.py`**

```python
"""Conversión entre texto y enteros escalados.

Las cantidades viajan y se guardan en milésimas, y los importes en
centavos. Sumar float acumula error, y un inventario suma miles de veces.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MILESIMAS = 1000
CENTAVOS = 100

SOLO_DIGITOS = re.compile(r"^-?\d+$")


def _agrupacion_valida(entero, separador_miles):
    """Verifica que los grupos de miles tengan tres dígitos.

    Sin esto «1,2,3» se leería como 123 en vez de rechazarse, y un número
    inventado es peor que un error: pasa por una cantidad real.
    """
    if separador_miles not in entero:
        return bool(SOLO_DIGITOS.match(entero))
    patron = r"^-?\d{1,3}(" + re.escape(separador_miles) + r"\d{3})+$"
    return bool(re.match(patron, entero))


def _partir(limpio, texto):
    """Separa parte entera y decimal resolviendo el formato del origen.

    Los ERP exportan indistintamente 1.234,56 y 1,234.56. Cuando conviven
    los dos caracteres, el último es el decimal y el otro agrupa miles.
    Cuando hay uno solo repetido (1.234.567) solo puede agrupar miles.

    Queda una ambigüedad que ningún criterio resuelve: «1.234» puede ser mil
    doscientos treinta y cuatro o uno coma doscientos treinta y cuatro. Se
    interpreta como decimal, que es lo habitual en cantidades. La vista
    previa de la importación existe para detectar el caso contrario.
    """
    coma = limpio.rfind(",")
    punto = limpio.rfind(".")

    if coma == -1 and punto == -1:
        if not SOLO_DIGITOS.match(limpio):
            raise ValueError(f"Cantidad inválida: {texto!r}")
        return limpio, ""

    if coma >= 0 and punto >= 0:
        separador_decimal = "," if coma > punto else "."
    else:
        unico = "," if coma >= 0 else "."
        if limpio.count(unico) > 1:
            if not _agrupacion_valida(limpio, unico):
                raise ValueError(f"Cantidad inválida: {texto!r}")
            return limpio.replace(unico, ""), ""
        separador_decimal = unico

    separador_miles = "." if separador_decimal == "," else ","
    entero, _, decimal = limpio.rpartition(separador_decimal)

    # Un separador suelto («.» o «,») no es cero: es una celda rota. Devolver
    # cero sería lo peor posible, porque un cero pasa por un conteo real.
    if not decimal.isdigit():
        raise ValueError(f"Cantidad inválida: {texto!r}")

    if entero in ("", "-"):
        entero += "0"
    if not _agrupacion_valida(entero, separador_miles):
        raise ValueError(f"Cantidad inválida: {texto!r}")

    return entero.replace(separador_miles, ""), decimal


def _a_escalado(texto, escala):
    if not isinstance(texto, str):
        raise ValueError(f"Se esperaba texto y llegó {type(texto).__name__}")

    limpio = texto.strip()
    if not limpio:
        raise ValueError("Cantidad vacía")

    entero, decimal = _partir(limpio, texto)

    try:
        valor = Decimal(f"{entero}.{decimal or 0}")
        # Redondeo y no truncamiento: el ERP puede exportar más decimales de
        # los que se guardan, y truncar sesgaría todas las cantidades a la baja.
        return int((valor * escala).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ArithmeticError) as error:
        raise ValueError(f"Cantidad inválida: {texto!r}") from error


def a_milesimas(texto):
    """Convierte texto a milésimas. '3,5' -> 3500."""
    return _a_escalado(texto, MILESIMAS)


def a_centavos(texto):
    """Convierte texto a centavos. '1.234,56' -> 123456."""
    return _a_escalado(texto, CENTAVOS)


def a_texto(milesimas):
    """Convierte milésimas a texto con coma decimal. 3500 -> '3,5'."""
    signo = "-" if milesimas < 0 else ""
    absoluto = abs(milesimas)
    entero, resto = divmod(absoluto, MILESIMAS)

    if resto == 0:
        return f"{signo}{entero}"

    decimales = f"{resto:03d}".rstrip("0")
    return f"{signo}{entero},{decimales}"
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_cantidades.py -v`
Expected: PASS, todos los casos

- [ ] **Step 5: Commit**

```bash
git add servidor/app/cantidades.py servidor/tests/test_cantidades.py
git commit -m "Agrega conversion de cantidades a enteros escalados

Resuelve los dos formatos numericos que exportan los ERP (1.234,56 y
1,234.56) tomando como separador decimal el ultimo que aparece.

Las cantidades quedan en milesimas para que sumar decimales sea exacto:
diez veces 0,1 tiene que dar 1 y con float no lo da."
```

---

### Task 3: Sesiones y pasadas

**Files:**
- Create: `servidor/app/repos/__init__.py`
- Create: `servidor/app/repos/sesiones.py`
- Create: `servidor/app/reloj.py`
- Create: `servidor/tests/test_sesiones.py`

**Interfaces:**
- Consumes: `db.conectar`, `db.crear_esquema` (Task 1)
- Produces:
  - `reloj.ahora() -> str` — timestamp ISO 8601 UTC
  - `sesiones.crear(con, nombre: str) -> int` — crea la sesión y su Conteo 1, devuelve `sesion_id`
  - `sesiones.obtener(con, sesion_id: int) -> dict`
  - `sesiones.listar(con) -> list[dict]`
  - `sesiones.sesion_abierta(con) -> dict | None`
  - `sesiones.pasada_abierta(con, sesion_id: int) -> dict` — incluye `numero` y `etiqueta`
  - `sesiones.etiqueta_pasada(numero: int) -> str` — `1` → `"Conteo 1"`
  - `sesiones.cerrar(con, sesion_id: int) -> None`
  - `sesiones.fijar_tolerancia(con, sesion_id, pct: float, min_abs_milesimas: int) -> None`

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_sesiones.py`:

```python
import pytest

from app.repos import sesiones


def test_crear_devuelve_id_y_abre_conteo_1(con):
    sesion_id = sesiones.crear(con, "Cliente X — 10/08/2026")

    sesion = sesiones.obtener(con, sesion_id)
    assert sesion["nombre"] == "Cliente X — 10/08/2026"
    assert sesion["estado"] == "abierta"

    pasada = sesiones.pasada_abierta(con, sesion_id)
    assert pasada["numero"] == 1
    assert pasada["etiqueta"] == "Conteo 1"


def test_tolerancia_por_defecto(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    sesion = sesiones.obtener(con, sesion_id)

    assert sesion["tolerancia_pct"] == 2.0
    assert sesion["tolerancia_min_abs"] == 1000  # 1 unidad en milésimas


@pytest.mark.parametrize("numero, esperado", [
    (1, "Conteo 1"),
    (2, "Conteo 2"),
    (17, "Conteo 17"),
])
def test_etiqueta_pasada(numero, esperado):
    assert sesiones.etiqueta_pasada(numero) == esperado


def test_no_permite_dos_sesiones_abiertas(con):
    sesiones.crear(con, "Primera")

    with pytest.raises(ValueError, match="Ya hay una sesión abierta"):
        sesiones.crear(con, "Segunda")


def test_se_puede_crear_otra_tras_cerrar(con):
    primera = sesiones.crear(con, "Primera")
    sesiones.cerrar(con, primera)

    segunda = sesiones.crear(con, "Segunda")
    assert segunda != primera
    assert sesiones.sesion_abierta(con)["id"] == segunda


def test_cerrar_cierra_tambien_la_pasada(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    sesiones.cerrar(con, sesion_id)

    fila = con.execute(
        "SELECT estado, fecha_cierre FROM pasada WHERE sesion_id = ?",
        (sesion_id,),
    ).fetchone()
    assert fila["estado"] == "cerrada"
    assert fila["fecha_cierre"] is not None


def test_sesion_abierta_devuelve_none_si_no_hay(con):
    assert sesiones.sesion_abierta(con) is None


def test_listar_devuelve_las_mas_nuevas_primero(con):
    primera = sesiones.crear(con, "Primera")
    sesiones.cerrar(con, primera)
    segunda = sesiones.crear(con, "Segunda")

    listado = sesiones.listar(con)
    assert [s["id"] for s in listado] == [segunda, primera]


def test_fijar_tolerancia(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    sesiones.fijar_tolerancia(con, sesion_id, 5.0, 2000)

    sesion = sesiones.obtener(con, sesion_id)
    assert sesion["tolerancia_pct"] == 5.0
    assert sesion["tolerancia_min_abs"] == 2000


def test_fijar_tolerancia_rechaza_milesimas_con_decimales(con):
    """La base lo rechazaría igual, pero con un mensaje que no dice nada."""
    sesion_id = sesiones.crear(con, "Cliente X")

    with pytest.raises(ValueError, match="milésimas"):
        sesiones.fijar_tolerancia(con, sesion_id, 5.0, 1500.5)


@pytest.mark.parametrize("operacion", [
    lambda con: sesiones.cerrar(con, 999),
    lambda con: sesiones.fijar_tolerancia(con, 999, 2.0, 1000),
])
def test_operar_sobre_una_sesion_inexistente_falla(con, operacion):
    with pytest.raises(ValueError, match="No existe la sesión"):
        operacion(con)


def test_ahora_usa_el_formato_del_proyecto():
    """reloj es la única fuente del formato de fecha de todo el sistema."""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", reloj.ahora())
```

El archivo empieza con estos imports:

```python
import re

import pytest

from app import reloj
from app.repos import sesiones
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_sesiones.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.repos'`

- [ ] **Step 3: Implementar `servidor/app/reloj.py`**

```python
"""Hora del servidor, centralizada para poder fijarla en los tests."""

from datetime import datetime, timezone


def ahora():
    """Timestamp ISO 8601 en UTC: 2026-08-10T14:32:05Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Implementar `servidor/app/repos/sesiones.py`**

Crear también `servidor/app/repos/__init__.py` vacío.

```python
"""Sesiones de inventario y sus pasadas de conteo."""

from app import reloj


def etiqueta_pasada(numero):
    """La etiqueta visible de una pasada. El numero interno y el visible coinciden."""
    return f"Conteo {numero}"


def sesion_abierta(con):
    fila = con.execute(
        "SELECT * FROM sesion WHERE estado = 'abierta' LIMIT 1"
    ).fetchone()
    return dict(fila) if fila else None


def crear(con, nombre):
    """Crea la sesión y abre su Conteo 1.

    Solo puede haber una sesión abierta a la vez: los dispositivos se
    vinculan a la sesión abierta y con dos no habría forma de saber a
    cuál pertenece un conteo.
    """
    if sesion_abierta(con) is not None:
        raise ValueError("Ya hay una sesión abierta. Cerrala antes de crear otra.")

    ahora = reloj.ahora()

    # Las dos escrituras van juntas o no va ninguna: una sesión sin pasada
    # no se puede usar para contar ni se puede cerrar.
    with con:
        cursor = con.execute(
            "INSERT INTO sesion (nombre, fecha_creacion) VALUES (?, ?)",
            (nombre, ahora),
        )
        sesion_id = cursor.lastrowid

        con.execute(
            "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 1, ?)",
            (sesion_id, ahora),
        )

    return sesion_id


def obtener(con, sesion_id):
    fila = con.execute("SELECT * FROM sesion WHERE id = ?", (sesion_id,)).fetchone()
    if fila is None:
        raise ValueError(f"No existe la sesión {sesion_id}")
    return dict(fila)


def listar(con):
    filas = con.execute("SELECT * FROM sesion ORDER BY id DESC").fetchall()
    return [dict(fila) for fila in filas]


def pasada_abierta(con, sesion_id):
    fila = con.execute(
        "SELECT * FROM pasada WHERE sesion_id = ? AND estado = 'abierta' "
        "ORDER BY numero DESC LIMIT 1",
        (sesion_id,),
    ).fetchone()
    if fila is None:
        raise ValueError(f"La sesión {sesion_id} no tiene ninguna pasada abierta")

    pasada = dict(fila)
    pasada["etiqueta"] = etiqueta_pasada(pasada["numero"])
    return pasada


def cerrar(con, sesion_id):
    obtener(con, sesion_id)  # falla con un mensaje claro si no existe
    ahora = reloj.ahora()

    with con:
        con.execute(
            "UPDATE pasada SET estado = 'cerrada', fecha_cierre = ? "
            "WHERE sesion_id = ? AND estado = 'abierta'",
            (ahora, sesion_id),
        )
        con.execute("UPDATE sesion SET estado = 'cerrada' WHERE id = ?", (sesion_id,))


def fijar_tolerancia(con, sesion_id, pct, min_abs_milesimas):
    obtener(con, sesion_id)

    # La base lo rechazaría igual, pero con un mensaje de SQLite que no le
    # dice nada a quien está corriendo el inventario.
    if not isinstance(min_abs_milesimas, int) or isinstance(min_abs_milesimas, bool):
        raise ValueError(
            "La tolerancia mínima se expresa en milésimas, con un número entero."
        )

    with con:
        con.execute(
            "UPDATE sesion SET tolerancia_pct = ?, tolerancia_min_abs = ? WHERE id = ?",
            (pct, min_abs_milesimas, sesion_id),
        )
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_sesiones.py -v`
Expected: PASS, todos en verde

- [ ] **Step 6: Commit**

```bash
git add servidor/app/reloj.py servidor/app/repos/ servidor/tests/test_sesiones.py
git commit -m "Agrega sesiones de inventario y apertura del Conteo 1

Crear una sesion abre automaticamente su primera pasada: no existe una
sesion sin pasada donde contar.

Solo se admite una sesion abierta a la vez. Los dispositivos se vinculan
a la sesion abierta, y con dos no habria forma de saber a cual pertenece
un conteo que llega."
```

---

### Task 4: Lectura de archivos CSV

**Files:**
- Create: `servidor/app/servicios/__init__.py`
- Create: `servidor/app/servicios/lectura_csv.py`
- Create: `servidor/tests/test_lectura_csv.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `lectura_csv.leer(contenido: bytes) -> tuple[list[str], list[list[str]]]` — devuelve encabezados y filas, resolviendo codificación y separador
  - `lectura_csv.detectar_codificacion(contenido: bytes) -> str`
  - `lectura_csv.detectar_separador(texto: str) -> str`

Los ERP exportan con separador `,` o `;`, y en Windows es habitual `cp1252` en vez de UTF-8. Adivinarlo mal rompe la importación entera, así que se resuelve acá y se prueba a fondo.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_lectura_csv.py`:

```python
import pytest

from app.servicios import lectura_csv


def test_lee_utf8_con_comas():
    contenido = "sku,descripcion\n10453,Tornillo\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["10453", "Tornillo"]]


def test_lee_punto_y_coma():
    contenido = "sku;descripcion\n10453;Tornillo\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["10453", "Tornillo"]]


def test_lee_cp1252_con_acentos():
    contenido = "sku;descripcion\n1;Cañería de bronce\n".encode("cp1252")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0][1] == "Cañería de bronce"


def test_lee_utf8_con_bom():
    contenido = "﻿sku,descripcion\n1,Tornillo\n".encode("utf-8")

    encabezados, _ = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]


def test_respeta_comas_dentro_de_comillas():
    contenido = 'sku,descripcion\n1,"Tornillo 3/8, hexagonal"\n'.encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0][1] == "Tornillo 3/8, hexagonal"


def test_ignora_filas_completamente_vacias():
    contenido = "sku,descripcion\n1,Tornillo\n\n2,Tuerca\n\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert len(filas) == 2


def test_completa_filas_con_menos_columnas():
    contenido = "sku,descripcion,grupo\n1,Tornillo\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0] == ["1", "Tornillo", ""]


def test_conserva_las_columnas_de_mas_en_vez_de_descartarlas():
    """Un campo de más delata un archivo mal armado: no se pierde en silencio."""
    contenido = "sku,descripcion\n1,Tornillo,SOBRA\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0] == ["1", "Tornillo", "SOBRA"]


def test_no_se_confunde_con_un_separador_dentro_de_comillas():
    """Contar caracteres fusionaría SKU y descripción en una sola columna."""
    contenido = 'sku,"descripcion; larga"\n1,Tornillo\n'.encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion; larga"]
    assert filas[0] == ["1", "Tornillo"]


def test_saltea_un_titulo_antes_del_encabezado():
    """Varios ERP anteponen el nombre del listado o la fecha de emisión."""
    contenido = (
        "Listado de stock al 10/08/2026\n"
        "sku;descripcion\n"
        "1;Tornillo\n"
        "2;Tuerca\n"
    ).encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert len(filas) == 2


def test_respeta_el_encabezado_aunque_las_filas_tengan_menos_columnas():
    """Elegir el encabezado por «ancho dominante» lo descartaba acá."""
    contenido = (
        "sku,descripcion,grupo\n"
        "1,Tornillo\n"
        "2,Tuerca\n"
        "3,Clavo\n"
    ).encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion", "grupo"]
    assert len(filas) == 3


def test_respeta_el_encabezado_aunque_las_filas_tengan_mas_columnas():
    contenido = (
        "sku,descripcion\n"
        "1,Tornillo,X\n"
        "2,Tuerca,Y\n"
        "3,Clavo,Z\n"
    ).encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert len(filas) == 3


def test_ignora_las_filas_de_relleno_que_deja_excel():
    """Excel suele dejar líneas con solo separadores o espacios al final."""
    contenido = "sku,descripcion\n1,Tornillo\n,\n,\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas == [["1", "Tornillo"]]


def test_ignora_las_lineas_en_blanco_del_final():
    contenido = "sku,descripcion\n1,Tornillo\n   \n   \n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["1", "Tornillo"]]


def test_ignora_la_columna_vacia_que_deja_un_separador_final():
    contenido = "sku,descripcion,\n1,Tornillo,\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas[0][:2] == ["1", "Tornillo"]


def test_rechaza_un_encabezado_sin_nombres():
    contenido = ",,\n1,2,3\n".encode("utf-8")

    with pytest.raises(ValueError, match="nombres de columna"):
        lectura_csv.leer(contenido)


@pytest.mark.parametrize("texto, esperado", [
    ("sku;descripcion\n1;Tornillo", ";"),
    ("sku,descripcion\n1,Tornillo", ","),
    ("sku\tdescripcion\n1\tTornillo", "\t"),
    ("sku|descripcion\n1|Tornillo", "|"),
    ("una sola columna\nsin separadores", ","),
    ("", ","),
])
def test_detectar_separador(texto, esperado):
    assert lectura_csv.detectar_separador(texto) == esperado


@pytest.mark.parametrize("texto, codificacion, esperada", [
    ("Cañería", "utf-8", "utf-8-sig"),
    ("Cañería", "cp1252", "cp1252"),
    ("sin acentos", "ascii", "utf-8-sig"),
])
def test_detectar_codificacion(texto, codificacion, esperada):
    """UTF-8 se prueba primero: casi todo UTF-8 también decodifica como cp1252."""
    assert lectura_csv.detectar_codificacion(texto.encode(codificacion)) == esperada


def test_recorta_espacios_de_los_encabezados():
    contenido = " sku , descripcion \n1,Tornillo\n".encode("utf-8")

    encabezados, _ = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]


def test_rechaza_archivo_vacio():
    with pytest.raises(ValueError, match="vacío"):
        lectura_csv.leer(b"")


def test_rechaza_encabezados_duplicados():
    contenido = "sku,sku\n1,2\n".encode("utf-8")

    with pytest.raises(ValueError, match="duplicada"):
        lectura_csv.leer(contenido)
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_lectura_csv.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.servicios'`

- [ ] **Step 3: Implementar `servidor/app/servicios/lectura_csv.py`**

Crear también `servidor/app/servicios/__init__.py` vacío.

```python
"""Lectura de los CSV que exportan los ERP.

Cada sistema exporta distinto: separador de coma o punto y coma, y en
Windows es habitual cp1252 en vez de UTF-8. Adivinar mal cualquiera de
las dos cosas rompe la importación entera, así que se resuelve acá.
"""

import csv
import io

# utf-8-sig también decodifica UTF-8 sin BOM, así que cubre los dos casos.
# latin-1 va última y nunca falla: mapea cualquier byte.
CODIFICACIONES = ["utf-8-sig", "cp1252", "latin-1"]
SEPARADORES = [",", ";", "\t", "|"]

LINEAS_DE_MUESTRA = 20


def detectar_codificacion(contenido: bytes) -> str:
    """Devuelve la primera codificación con la que el archivo se lee entero.

    El orden importa: casi cualquier texto UTF-8 también decodifica sin
    error como cp1252, pero al revés no. Probar UTF-8 primero evita el
    clásico «CañerÃ­a» en las descripciones.
    """
    for codificacion in CODIFICACIONES:
        try:
            contenido.decode(codificacion)
            return codificacion
        except UnicodeDecodeError:
            continue
    return CODIFICACIONES[-1]


def _anchos(muestra: list[str], separador: str) -> list[int]:
    filas = list(csv.reader(muestra, delimiter=separador))
    return [len(fila) for fila in filas if fila]


def detectar_separador(texto: str) -> str:
    """Elige el separador que parte el archivo de forma consistente.

    Contar caracteres no alcanza por dos motivos. Una coma dentro de un
    campo entre comillas cuenta igual que una separadora, así que un
    encabezado como `sku,"descripcion; larga"` empata y puede resolverse
    a punto y coma, fusionando columnas sin que nadie lo note. Y mirar
    solo la primera línea falla cuando el ERP antepone un título, que no
    tiene ningún separador.

    Se prueba cada candidato con el lector de CSV real sobre las primeras
    líneas y gana el que produce más filas del mismo ancho.
    """
    muestra = [linea for linea in texto.splitlines() if linea.strip()]
    muestra = muestra[:LINEAS_DE_MUESTRA]
    if not muestra:
        return ","

    mejor = ","
    mejor_puntaje = (0, 0)

    for separador in SEPARADORES:
        anchos = _anchos(muestra, separador)
        if not anchos:
            continue

        # El ancho más frecuente; ante un empate, el mayor. Sin el desempate
        # el resultado depende del orden del conjunto y no es reproducible.
        ancho_dominante = max(anchos, key=lambda ancho: (anchos.count(ancho), ancho))
        if ancho_dominante < 2:
            continue  # una sola columna: este separador no separa nada

        puntaje = (anchos.count(ancho_dominante), ancho_dominante)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = separador

    return mejor


def leer(contenido: bytes) -> tuple[list[str], list[list[str]]]:
    """Devuelve (encabezados, filas) a partir del contenido binario del archivo."""
    if not contenido.strip():
        raise ValueError("El archivo está vacío")

    texto = contenido.decode(detectar_codificacion(contenido))
    separador = detectar_separador(texto)

    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    todas = [fila for fila in lector if any(celda.strip() for celda in fila)]

    if not todas:
        raise ValueError("El archivo está vacío")

    # Muchos ERP anteponen un título o una fecha antes del encabezado real.
    # Se reconoce porque queda como una línea suelta sin separadores entre
    # filas que sí los tienen. Solo se saltean esas: cualquier otra
    # diferencia de ancho es un encabezado legítimo con filas irregulares,
    # y elegir por «ancho dominante» descartaría el encabezado verdadero
    # apenas la mayoría de las filas omita la última columna.
    primera = 0
    if any(len(fila) > 1 for fila in todas):
        while primera < len(todas) - 1 and len(todas[primera]) <= 1:
            primera += 1

    encabezados = [celda.strip() for celda in todas[primera]]

    # Un encabezado que termina en separador deja una columna sin nombre.
    while encabezados and not encabezados[-1]:
        encabezados.pop()

    if not encabezados:
        raise ValueError("La primera fila del archivo no tiene nombres de columna")

    vistos = set()
    for encabezado in encabezados:
        clave = encabezado.lower()
        if clave in vistos:
            raise ValueError(f"La columna «{encabezado}» está duplicada en el archivo")
        vistos.add(clave)

    cantidad = len(encabezados)
    filas = []
    for fila in todas[primera + 1:]:
        # Las filas cortas se completan; las largas se conservan enteras. Un
        # campo de más suele delatar un archivo mal armado, y descartarlo acá
        # perdería el dato en silencio. La importación lo reporta.
        completa = [celda.strip() for celda in fila]
        completa += [""] * (cantidad - len(completa))
        filas.append(completa)

    return encabezados, filas
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_lectura_csv.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add servidor/app/servicios/ servidor/tests/test_lectura_csv.py
git commit -m "Agrega lectura tolerante de los CSV del ERP

Detecta codificacion y separador en vez de asumirlos: cada ERP exporta
distinto y en Windows cp1252 sigue siendo comun. Adivinar mal cualquiera
de los dos rompe la importacion entera, y el error aparece recien al ver
descripciones ilegibles en el tablero.

Rechaza encabezados duplicados, que dejarian el mapeo de columnas
ambiguo sin que nadie lo note."
```

---

### Task 5: Importación del maestro con mapeo de columnas

**Files:**
- Create: `servidor/app/servicios/importacion.py`
- Create: `servidor/tests/test_importacion.py`

**Interfaces:**
- Consumes: `lectura_csv.leer` (Task 4), `cantidades.a_milesimas` y `a_centavos` (Task 2), `sesiones.crear` (Task 3)
- Produces:
  - `importacion.CAMPOS` — lista de campos mapeables: `["id_orden", "tipo", "material", "sku", "descripcion", "grupo", "ubicacion", "unidad", "stock_sistema", "costo_unitario", "codigo_barras"]`
  - `importacion.CAMPOS_OBLIGATORIOS` — `["sku", "descripcion"]`
  - `importacion.previsualizar(contenido: bytes, cantidad: int = 5) -> dict` — `{"encabezados": [...], "filas": [...]}`
  - `importacion.importar(con, sesion_id: int, contenido: bytes, mapeo: dict[str, str], unidad_por_defecto: str = "UN") -> dict` — devuelve `{"importados": int, "codigos": int}`

`mapeo` va del campo del sistema al encabezado del archivo: `{"sku": "Código", "descripcion": "Detalle"}`.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_importacion.py`:

```python
import pytest

from app.repos import sesiones
from app.servicios import importacion


@pytest.fixture
def sesion_id(con):
    return sesiones.crear(con, "Cliente X")


def test_previsualizar_devuelve_encabezados_y_muestra():
    contenido = "sku,detalle\n1,Tornillo\n2,Tuerca\n3,Arandela\n".encode("utf-8")

    vista = importacion.previsualizar(contenido, cantidad=2)

    assert vista["encabezados"] == ["sku", "detalle"]
    assert len(vista["filas"]) == 2


def test_importa_articulos_con_mapeo(con, sesion_id):
    # Punto y coma como separador: es lo habitual cuando las cantidades
    # llevan coma decimal, como el 12,5 de la segunda fila.
    contenido = (
        "Codigo;Detalle;Rubro;Deposito;UM;Existencia\n"
        "10453;Tornillo hex 3/8;Buloneria;A-03-2;UN;48\n"
        "10454;Cañeria bronce;Sanitarios;B-01;MT;12,5\n"
    ).encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "Codigo",
        "descripcion": "Detalle",
        "grupo": "Rubro",
        "ubicacion": "Deposito",
        "unidad": "UM",
        "stock_sistema": "Existencia",
    })

    assert resultado["importados"] == 2

    filas = con.execute(
        "SELECT * FROM articulo WHERE sesion_id = ? ORDER BY id_orden", (sesion_id,)
    ).fetchall()
    assert filas[0]["sku"] == "10453"
    assert filas[0]["descripcion"] == "Tornillo hex 3/8"
    assert filas[0]["grupo"] == "Buloneria"
    assert filas[0]["ubicacion"] == "A-03-2"
    assert filas[0]["unidad"] == "UN"
    assert filas[0]["stock_sistema"] == 48000
    assert filas[1]["stock_sistema"] == 12500


def test_genera_id_orden_si_no_viene(con, sesion_id):
    contenido = "sku,detalle\nA,Uno\nB,Dos\nC,Tres\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    ordenes = [
        fila["id_orden"]
        for fila in con.execute(
            "SELECT id_orden FROM articulo WHERE sesion_id = ? ORDER BY id", (sesion_id,)
        )
    ]
    assert ordenes == [1, 2, 3]


def test_respeta_id_orden_del_archivo(con, sesion_id):
    contenido = "nro,sku,detalle\n100,A,Uno\n200,B,Dos\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "id_orden": "nro", "sku": "sku", "descripcion": "detalle",
    })

    ordenes = [
        fila["id_orden"]
        for fila in con.execute(
            "SELECT id_orden FROM articulo WHERE sesion_id = ? ORDER BY id", (sesion_id,)
        )
    ]
    assert ordenes == [100, 200]


def test_crea_codigo_de_barras_cuando_se_mapea(con, sesion_id):
    contenido = "sku,detalle,ean\n10453,Tornillo,7791234567890\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "codigo_barras": "ean",
    })

    assert resultado["codigos"] == 1
    fila = con.execute("SELECT codigo FROM codigo_barras").fetchone()
    assert fila["codigo"] == "7791234567890"


def test_usa_el_sku_como_codigo_si_no_se_mapea(con, sesion_id):
    contenido = "sku,detalle\n10453,Tornillo\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    fila = con.execute("SELECT codigo FROM codigo_barras").fetchone()
    assert fila["codigo"] == "10453"


def test_unidad_por_defecto_cuando_no_se_mapea(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    importacion.importar(
        con, sesion_id, contenido,
        {"sku": "sku", "descripcion": "detalle"},
        unidad_por_defecto="KG",
    )

    fila = con.execute("SELECT unidad FROM articulo").fetchone()
    assert fila["unidad"] == "KG"


def test_importa_costo_en_centavos(con, sesion_id):
    contenido = "sku,detalle,costo\n1,Tornillo,\"1.234,56\"\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "costo_unitario": "costo",
    })

    fila = con.execute("SELECT costo_unitario FROM articulo").fetchone()
    assert fila["costo_unitario"] == 123456


def test_rechaza_mapeo_sin_campos_obligatorios(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="descripcion"):
        importacion.importar(con, sesion_id, contenido, {"sku": "sku"})


def test_rechaza_mapeo_a_columna_inexistente(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="no existe en el archivo"):
        importacion.importar(con, sesion_id, contenido, {
            "sku": "sku", "descripcion": "detalle", "grupo": "Rubro",
        })


def test_saltea_filas_sin_sku(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n,Sin codigo\n2,Tuerca\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert len(resultado["descartadas"]) == 1


def test_reporta_las_filas_con_columnas_de_mas(con, sesion_id):
    """Una columna de más suele delatar una comilla sin cerrar."""
    contenido = "sku,detalle\n1,Tornillo\n2,Tuerca,SOBRA\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert any("más columnas" in a["motivo"] for a in resultado["advertencias"])


def test_stock_invalido_queda_en_cero_y_se_reporta(con, sesion_id):
    contenido = "sku,detalle,stock\n1,Tornillo,mucho\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "stock_sistema": "stock",
    })

    fila = con.execute("SELECT stock_sistema FROM articulo").fetchone()
    assert fila["stock_sistema"] == 0
    assert len(resultado["advertencias"]) == 1
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_importacion.py -v`
Expected: FAIL con `AttributeError: module 'app.servicios.importacion' has no attribute 'previsualizar'`

- [ ] **Step 3: Implementar `servidor/app/servicios/importacion.py`**

```python
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

    importados = 0
    codigos = 0
    descartadas = []
    advertencias = []

    for numero_fila, fila in enumerate(filas, start=2):
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
            descartadas.append(
                {"fila": numero_fila, "motivo": "Sin SKU"}
            )
            continue

        descripcion = valor("descripcion") or sku

        if "id_orden" in indice:
            try:
                id_orden = int(valor("id_orden"))
            except ValueError:
                id_orden = importados + 1
                advertencias.append({
                    "fila": numero_fila,
                    "motivo": f"Número de orden inválido, se usó {id_orden}",
                })
        else:
            id_orden = importados + 1

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
            codigos += 1

        importados += 1

    con.commit()
    return {
        "importados": importados,
        "codigos": codigos,
        "descartadas": descartadas,
        "advertencias": advertencias,
    }
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_importacion.py -v`
Expected: PASS, 12 tests

- [ ] **Step 5: Commit**

```bash
git add servidor/app/servicios/importacion.py servidor/tests/test_importacion.py
git commit -m "Agrega importacion del maestro con mapeo de columnas

El mapeo va del campo del sistema al encabezado del archivo, resuelto en
pantalla: cada cliente exporta con nombres y orden distintos, y tocar el
codigo en cada instalacion no escala.

Las filas con problemas no frenan la importacion. Una fila sin SKU se
descarta y un stock ilegible entra como cero, ambos reportados en el
resultado, porque un maestro de miles de lineas siempre trae basura y
abortar todo por una celda obliga a editar el CSV a mano."
```

---

### Task 6: Operarios y vinculación de dispositivos

**Files:**
- Create: `servidor/app/repos/operarios.py`
- Create: `servidor/tests/test_operarios.py`

**Interfaces:**
- Consumes: `db` (Task 1)
- Produces:
  - `operarios.crear(con, nombre: str, pin: str | None = None) -> dict` — devuelve el operario con su `token_dispositivo`
  - `operarios.listar(con) -> list[dict]`
  - `operarios.por_token(con, token: str) -> dict | None`
  - `operarios.desactivar(con, operario_id: int) -> None`

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_operarios.py`:

```python
import pytest

from app.repos import operarios


def test_crear_devuelve_token(con):
    juan = operarios.crear(con, "Juan Pérez")

    assert juan["nombre"] == "Juan Pérez"
    assert len(juan["token_dispositivo"]) >= 32
    assert juan["activo"] == 1


def test_tokens_distintos_por_operario(con):
    juan = operarios.crear(con, "Juan")
    ana = operarios.crear(con, "Ana")

    assert juan["token_dispositivo"] != ana["token_dispositivo"]


def test_por_token_encuentra_al_operario(con):
    juan = operarios.crear(con, "Juan")

    encontrado = operarios.por_token(con, juan["token_dispositivo"])

    assert encontrado["id"] == juan["id"]


def test_por_token_devuelve_none_si_no_existe(con):
    assert operarios.por_token(con, "token-inventado") is None


def test_por_token_ignora_desactivados(con):
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    assert operarios.por_token(con, juan["token_dispositivo"]) is None


def test_no_permite_nombres_repetidos(con):
    operarios.crear(con, "Juan")

    with pytest.raises(ValueError, match="Ya existe"):
        operarios.crear(con, "Juan")


def test_listar_ordena_por_nombre(con):
    operarios.crear(con, "Zulema")
    operarios.crear(con, "Ana")

    nombres = [o["nombre"] for o in operarios.listar(con)]

    assert nombres == ["Ana", "Zulema"]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_operarios.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.repos.operarios'`

- [ ] **Step 3: Implementar `servidor/app/repos/operarios.py`**

```python
"""Operarios y los tokens con los que se vinculan sus dispositivos.

Los operarios son globales, no de una sesión: se dan de alta una vez y se
reutilizan en todos los inventarios.
"""

import secrets
import sqlite3


def crear(con, nombre, pin=None):
    token = secrets.token_urlsafe(32)
    try:
        cursor = con.execute(
            "INSERT INTO operario (nombre, pin, token_dispositivo) VALUES (?, ?, ?)",
            (nombre, pin, token),
        )
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Ya existe un operario llamado «{nombre}»") from error

    con.commit()
    return _obtener(con, cursor.lastrowid)


def _obtener(con, operario_id):
    fila = con.execute("SELECT * FROM operario WHERE id = ?", (operario_id,)).fetchone()
    return dict(fila) if fila else None


def listar(con):
    filas = con.execute(
        "SELECT * FROM operario WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [dict(fila) for fila in filas]


def por_token(con, token):
    fila = con.execute(
        "SELECT * FROM operario WHERE token_dispositivo = ? AND activo = 1",
        (token,),
    ).fetchone()
    return dict(fila) if fila else None


def desactivar(con, operario_id):
    con.execute("UPDATE operario SET activo = 0 WHERE id = ?", (operario_id,))
    con.commit()
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_operarios.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/operarios.py servidor/tests/test_operarios.py
git commit -m "Agrega operarios con token de vinculacion

Cada operario recibe un token propio que despues viaja en el QR personal,
asi el celular queda identificado sin que nadie tipee su nombre: evita
homonimos y variantes con espacios que partirian el conteo de una misma
persona en dos.

Los operarios son globales y no de una sesion, para no volver a cargarlos
en cada inventario."
```

---

### Task 7: Registro de conteos con idempotencia

**Files:**
- Create: `servidor/app/repos/conteos.py`
- Create: `servidor/tests/test_conteos.py`

**Interfaces:**
- Consumes: `sesiones` (Task 3), `operarios` (Task 6), `importacion` (Task 5)
- Produces:
  - `conteos.registrar(con, sesion_id, operario_id, evento: dict) -> str` — devuelve `"registrado"` o `"duplicado"`
  - `conteos.registrar_lote(con, sesion_id, operario_id, eventos: list[dict]) -> dict`
  - `conteos.buscar_por_codigo(con, sesion_id, codigo: str) -> dict | None`
  - `conteos.de_operario(con, sesion_id, operario_id, limite: int = 50) -> list[dict]`

Un `evento` es: `{"uuid": str, "codigo": str, "cantidad": int (milésimas), "timestamp_dispositivo": str, "ubicacion_real": str | None, "observaciones": str | None, "anula_uuid": str | None}`.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_conteos.py`:

```python
import pytest

from app.repos import conteos, operarios, sesiones
from app.servicios import importacion


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,ean\n"
        "10453,Tornillo hex,7791111111111\n"
        "10454,Tuerca,7792222222222\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "codigo_barras": "ean",
    })
    juan = operarios.crear(con, "Juan")
    ana = operarios.crear(con, "Ana")
    return {"sesion_id": sesion_id, "juan": juan, "ana": ana}


def evento(uuid, codigo="7791111111111", cantidad=24000, **extra):
    base = {
        "uuid": uuid,
        "codigo": codigo,
        "cantidad": cantidad,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
    }
    base.update(extra)
    return base


def test_registrar_guarda_el_conteo(con, escenario):
    resultado = conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1")
    )

    assert resultado == "registrado"
    fila = con.execute("SELECT * FROM conteo WHERE uuid = 'u-1'").fetchone()
    assert fila["cantidad"] == 24000
    assert fila["timestamp_servidor"] is not None


def test_reenviar_el_mismo_uuid_no_duplica(con, escenario):
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1"))
    resultado = conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1")
    )

    assert resultado == "duplicado"
    total = con.execute("SELECT COUNT(*) AS n FROM conteo").fetchone()["n"]
    assert total == 1


def test_lote_reporta_registrados_y_duplicados(con, escenario):
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1"))

    resultado = conteos.registrar_lote(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        [evento("u-1"), evento("u-2"), evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert resultado["duplicados"] == 1
    assert resultado["rechazados"] == []


def test_codigo_desconocido_se_rechaza_sin_frenar_el_lote(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        [evento("u-1"), evento("u-2", codigo="0000000000000"), evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert len(resultado["rechazados"]) == 1
    assert resultado["rechazados"][0]["uuid"] == "u-2"


def test_anulacion_referencia_al_conteo_original(con, escenario):
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1"))
    conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        evento("u-2", cantidad=0, anula_uuid="u-1"),
    )

    fila = con.execute("SELECT anula_uuid FROM conteo WHERE uuid = 'u-2'").fetchone()
    assert fila["anula_uuid"] == "u-1"


def test_anular_un_uuid_inexistente_se_rechaza(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        [evento("u-9", anula_uuid="no-existe")],
    )

    assert resultado["registrados"] == 0
    assert len(resultado["rechazados"]) == 1


def test_guarda_ubicacion_real_y_observaciones(con, escenario):
    conteos.registrar(
        con, escenario["sesion_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="C-01", observaciones="Estaba mal ubicado"),
    )

    fila = con.execute("SELECT * FROM conteo WHERE uuid = 'u-1'").fetchone()
    assert fila["ubicacion_real"] == "C-01"
    assert fila["observaciones"] == "Estaba mal ubicado"


def test_buscar_por_codigo_devuelve_el_articulo(con, escenario):
    articulo = conteos.buscar_por_codigo(con, escenario["sesion_id"], "7792222222222")

    assert articulo["sku"] == "10454"
    assert articulo["descripcion"] == "Tuerca"


def test_buscar_por_codigo_no_expone_stock_ni_costo(con, escenario):
    articulo = conteos.buscar_por_codigo(con, escenario["sesion_id"], "7791111111111")

    assert "stock_sistema" not in articulo
    assert "costo_unitario" not in articulo


def test_de_operario_solo_devuelve_lo_propio(con, escenario):
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], evento("u-1"))
    conteos.registrar(con, escenario["sesion_id"], escenario["ana"]["id"], evento("u-2"))

    propios = conteos.de_operario(
        con, escenario["sesion_id"], escenario["juan"]["id"]
    )

    assert [c["uuid"] for c in propios] == ["u-1"]


def test_de_operario_devuelve_lo_mas_reciente_primero(con, escenario):
    for numero in range(1, 4):
        conteos.registrar(
            con, escenario["sesion_id"], escenario["juan"]["id"],
            evento(f"u-{numero}"),
        )

    propios = conteos.de_operario(con, escenario["sesion_id"], escenario["juan"]["id"])

    assert [c["uuid"] for c in propios] == ["u-3", "u-2", "u-1"]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_conteos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.repos.conteos'`

- [ ] **Step 3: Implementar `servidor/app/repos/conteos.py`**

```python
"""Registro de conteos.

Nada se edita ni se borra: cada escaneo es una fila y una corrección es
otra fila que anula la anterior. Eso vuelve la sincronización idempotente
—reenviar es inofensivo— y deja el conteo auditable de punta a punta.
"""

from app import reloj
from app.repos import sesiones

CAMPOS_PUBLICOS = (
    "a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion, "
    "a.grupo, a.ubicacion, a.unidad"
)


def buscar_por_codigo(con, sesion_id, codigo):
    """Busca el artículo por código de barras.

    Devuelve solo campos que pueden viajar a un dispositivo: sin
    stock_sistema ni costo_unitario, por el conteo a ciegas.
    """
    fila = con.execute(
        f"""
        SELECT {CAMPOS_PUBLICOS}
        FROM codigo_barras cb
        JOIN articulo a ON a.id = cb.articulo_id
        WHERE cb.codigo = ? AND a.sesion_id = ? AND a.fusionado_en IS NULL
        LIMIT 1
        """,
        (codigo, sesion_id),
    ).fetchone()
    return dict(fila) if fila else None


def _ya_registrado(con, uuid):
    return con.execute(
        "SELECT 1 FROM conteo WHERE uuid = ?", (uuid,)
    ).fetchone() is not None


def registrar(con, sesion_id, operario_id, evento):
    """Registra un conteo. Devuelve 'registrado' o 'duplicado'.

    Reenviar un uuid ya recibido no es un error: es lo que hace el celular
    cuando no le llegó la confirmación.
    """
    if _ya_registrado(con, evento["uuid"]):
        return "duplicado"

    anula = evento.get("anula_uuid")
    if anula and not _ya_registrado(con, anula):
        raise ValueError(f"El conteo que se intenta anular no existe: {anula}")

    articulo = buscar_por_codigo(con, sesion_id, evento["codigo"])
    if articulo is None:
        raise ValueError(f"Código desconocido: {evento['codigo']}")

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
            evento["cantidad"], operario_id,
            evento.get("ubicacion_real"), evento.get("observaciones"),
            evento["timestamp_dispositivo"], reloj.ahora(), anula,
        ),
    )
    con.commit()
    return "registrado"


def registrar_lote(con, sesion_id, operario_id, eventos):
    """Registra varios conteos. Un evento con problema no frena a los demás."""
    registrados = 0
    duplicados = 0
    rechazados = []

    for evento in eventos:
        try:
            resultado = registrar(con, sesion_id, operario_id, evento)
        except ValueError as error:
            rechazados.append({"uuid": evento.get("uuid"), "motivo": str(error)})
            continue

        if resultado == "registrado":
            registrados += 1
        else:
            duplicados += 1

    return {
        "registrados": registrados,
        "duplicados": duplicados,
        "rechazados": rechazados,
    }


def de_operario(con, sesion_id, operario_id, limite=50):
    """Los conteos propios del operario, del más reciente al más viejo."""
    filas = con.execute(
        """
        SELECT c.uuid, c.cantidad, c.ubicacion_real, c.observaciones,
               c.timestamp_dispositivo, c.anula_uuid,
               a.sku, a.descripcion, a.unidad, a.ubicacion
        FROM conteo c
        JOIN articulo a ON a.id = c.articulo_id
        WHERE c.sesion_id = ? AND c.operario_id = ?
        ORDER BY c.rowid DESC
        LIMIT ?
        """,
        (sesion_id, operario_id, limite),
    ).fetchall()
    return [dict(fila) for fila in filas]
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_conteos.py -v`
Expected: PASS, todos en verde

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/conteos.py servidor/tests/test_conteos.py
git commit -m "Agrega registro de conteos idempotente por uuid

Reenviar un uuid ya recibido devuelve 'duplicado' en vez de fallar: es lo
que hace el celular cuando pierde la confirmacion, y sin esto un corte de
WiFi en el momento justo duplicaria conteos.

En un lote, un evento con problema se rechaza y se informa, pero no frena
a los demas: el operario no puede quedar sin sincronizar media jornada
por un solo codigo desconocido.

La busqueda por codigo devuelve solo campos que pueden viajar a un
dispositivo, sin stock ni costo, por el conteo a ciegas."
```

---

### Task 8: Cálculo del tablero

**Files:**
- Create: `servidor/app/servicios/tablero.py`
- Create: `servidor/tests/test_tablero.py`

**Interfaces:**
- Consumes: `sesiones` (Task 3), `conteos` (Task 7)
- Produces:
  - `tablero.SIN_CONTAR`, `tablero.CONSOLIDADO`, `tablero.A_RECONTAR` — constantes de estado
  - `tablero.estado_de(dif: int, stock: int, pct: float, min_abs: int, hubo_conteo: bool) -> str`
  - `tablero.parece_error_de_carga(contado: int, stock: int) -> str | None` — devuelve el patrón detectado (`"dígito de más"`, `"dígitos permutados"`, `"dígito repetido"`) o `None`
  - `tablero.filas(con, sesion_id, filtros: dict | None = None) -> list[dict]`
  - `tablero.resumen(con, sesion_id) -> dict`

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_tablero.py`:

```python
import pytest

from app.repos import conteos, operarios, sesiones
from app.servicios import importacion, tablero


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,grupo,ubic,stock\n"
        "A,Tornillo,Buloneria,P-1,100\n"
        "B,Tuerca,Buloneria,P-1,50\n"
        "C,Arandela,Bazar,P-2,10\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "grupo": "grupo",
        "ubicacion": "ubic", "stock_sistema": "stock",
    })
    juan = operarios.crear(con, "Juan")
    return {"sesion_id": sesion_id, "juan": juan}


def contar(con, escenario, codigo, cantidad, uuid):
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": uuid,
        "codigo": codigo,
        "cantidad": cantidad,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
    })


@pytest.mark.parametrize("dif, stock, esperado", [
    (0,      100000, tablero.CONSOLIDADO),   # exacto
    (2000,   100000, tablero.CONSOLIDADO),   # 2% de 100 = 2 unidades
    (-2000,  100000, tablero.CONSOLIDADO),   # tolera para ambos lados
    (2001,   100000, tablero.A_RECONTAR),    # apenas afuera
    (1000,   3000,   tablero.CONSOLIDADO),   # 2% de 3 es 0,06: manda el mínimo de 1
    (1001,   3000,   tablero.A_RECONTAR),
    (1000,   0,      tablero.CONSOLIDADO),   # stock cero, entra por el mínimo
    (2000,   -100000, tablero.CONSOLIDADO),  # stock negativo del ERP: cuenta el absoluto
])
def test_estado_de(dif, stock, esperado):
    assert tablero.estado_de(dif, stock, 2.0, 1000, hubo_conteo=True) == esperado


def test_sin_conteo_es_sin_contar():
    assert tablero.estado_de(0, 100000, 2.0, 1000, hubo_conteo=False) == tablero.SIN_CONTAR


@pytest.mark.parametrize("contado, stock, esperado", [
    (240000, 24000, "dígito de más"),      # 240 en vez de 24
    (2000,   24000, "dígito de más"),      # 2 en vez de 24
    (2400000, 24000, "dígito de más"),     # 2400 en vez de 24
    (42000,  24000, "dígitos permutados"), # 42 en vez de 24
    (55000,  5000,  "dígito repetido"),    # 55 en vez de 5
    (23000,  24000, None),                 # diferencia común, no tiene forma de tipeo
    (0,      24000, None),                 # faltante total: es un hallazgo, no un error
    (24000,  24000, None),                 # sin diferencia
    (0,      0,     None),                 # ambos en cero: nada que comparar
])
def test_parece_error_de_carga(contado, stock, esperado):
    assert tablero.parece_error_de_carga(contado, stock) == esperado


def test_marca_error_de_carga_solo_a_los_que_hay_que_recontar(con, escenario):
    contar(con, escenario, "C", 100000, "u-1")  # el sistema dice 10, se cargaron 100

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "C")

    assert fila["estado"] == tablero.A_RECONTAR
    assert fila["posible_error_carga"] == "dígito de más"


def test_los_consolidados_no_se_marcan(con, escenario):
    contar(con, escenario, "A", 100000, "u-1")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["posible_error_carga"] is None


def test_filas_traen_todos_los_articulos(con, escenario):
    filas = tablero.filas(con, escenario["sesion_id"])

    assert len(filas) == 3
    assert [f["sku"] for f in filas] == ["A", "B", "C"]


def test_articulo_sin_contar(con, escenario):
    fila = tablero.filas(con, escenario["sesion_id"])[0]

    assert fila["ultimo_conteo"] is None
    assert fila["dif"] is None
    assert fila["estado"] == tablero.SIN_CONTAR
    assert fila["fecha"] is None


def test_conteos_del_mismo_sku_se_suman(con, escenario):
    contar(con, escenario, "A", 60000, "u-1")
    contar(con, escenario, "A", 40000, "u-2")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 100000
    assert fila["dif"] == 0
    assert fila["estado"] == tablero.CONSOLIDADO


def test_conteo_anulado_no_suma(con, escenario):
    contar(con, escenario, "A", 60000, "u-1")
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "A", "cantidad": 0,
        "timestamp_dispositivo": "2026-08-10T10:05:00Z", "anula_uuid": "u-1",
    })
    contar(con, escenario, "A", 100000, "u-3")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 100000


def test_diferencia_fuera_de_tolerancia(con, escenario):
    contar(con, escenario, "C", 5000, "u-1")  # sistema dice 10

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "C")

    assert fila["dif"] == -5000
    assert fila["estado"] == tablero.A_RECONTAR


def test_filtro_por_grupo(con, escenario):
    filas = tablero.filas(con, escenario["sesion_id"], {"grupo": "Bazar"})

    assert [f["sku"] for f in filas] == ["C"]


def test_filtro_por_estado(con, escenario):
    contar(con, escenario, "A", 100000, "u-1")

    filas = tablero.filas(con, escenario["sesion_id"], {"estado": tablero.SIN_CONTAR})

    assert [f["sku"] for f in filas] == ["B", "C"]


def test_filtro_por_texto_busca_en_sku_y_descripcion(con, escenario):
    filas = tablero.filas(con, escenario["sesion_id"], {"texto": "arand"})

    assert [f["sku"] for f in filas] == ["C"]


def test_resumen_cuenta_avance(con, escenario):
    contar(con, escenario, "A", 100000, "u-1")
    contar(con, escenario, "C", 5000, "u-2")

    resumen = tablero.resumen(con, escenario["sesion_id"])

    assert resumen["articulos"] == 3
    assert resumen["contados"] == 2
    assert resumen["sin_contar"] == 1
    assert resumen["consolidados"] == 1
    assert resumen["a_recontar"] == 1
    assert resumen["avance_pct"] == pytest.approx(66.7, abs=0.1)


def test_resumen_de_sesion_vacia_no_divide_por_cero(con):
    sesion_id = sesiones.crear(con, "Sin maestro")

    resumen = tablero.resumen(con, sesion_id)

    assert resumen["articulos"] == 0
    assert resumen["avance_pct"] == 0
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_tablero.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.servicios.tablero'`

- [ ] **Step 3: Implementar `servidor/app/servicios/tablero.py`**

```python
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

    # 240 por 24, o 2 por 24: el número quedó multiplicado o dividido por
    # una potencia de diez porque se tecleó un dígito de más o de menos.
    if dc.rstrip("0").lstrip("0") == ds.rstrip("0").lstrip("0") and len(dc) != len(ds):
        return "dígito de más"

    # 5 tecleado dos veces queda 55.
    if len(set(dc)) == 1 and dc[0] == ds.lstrip("0")[:1] and len(dc) != len(ds):
        return "dígito repetido"

    # 42 por 24: los mismos dígitos en otro orden.
    if len(dc) == len(ds) and sorted(dc) == sorted(ds):
        return "dígitos permutados"

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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_tablero.py -v`
Expected: PASS, 14 tests

- [ ] **Step 5: Commit**

```bash
git add servidor/app/servicios/tablero.py servidor/tests/test_tablero.py
git commit -m "Agrega el calculo del tablero con tolerancia y estados

La tolerancia toma el mayor entre el porcentaje y el minimo absoluto. El
porcentaje solo dejaria fuera de tolerancia a un articulo con stock 3 por
una sola unidad de diferencia, y el minimo solo seria demasiado
permisivo con los articulos de mucho stock.

Usa el valor absoluto del stock del sistema porque algunos ERP arrastran
stock negativo por errores de carga, y con el signo el limite daba
negativo y el articulo nunca consolidaba.

El estado es un calculo, no un dato guardado: cambiar la tolerancia
recalcula el tablero al instante, que es lo que permite negociar el
criterio con el cliente viendo el impacto."
```

---

### Task 9: Exportación a CSV

**Files:**
- Create: `servidor/app/servicios/exportacion.py`
- Create: `servidor/tests/test_exportacion.py`

**Interfaces:**
- Consumes: `tablero` (Task 8), `cantidades` (Task 2)
- Produces:
  - `exportacion.resumen_por_sku(con, sesion_id, filtros=None) -> str` — CSV completo como texto
  - `exportacion.detalle(con, sesion_id) -> str`

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_exportacion.py`:

```python
import csv
import io

import pytest

from app.repos import conteos, operarios, sesiones
from app.servicios import exportacion, importacion


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,grupo,ubic,um,stock,costo\n"
        "A,Tornillo,Buloneria,P-1,UN,100,25\n"
        "B,Cable,Electricidad,P-2,MT,50,\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "grupo": "grupo",
        "ubicacion": "ubic", "unidad": "um", "stock_sistema": "stock",
        "costo_unitario": "costo",
    })
    juan = operarios.crear(con, "Juan")
    conteos.registrar(con, sesion_id, juan["id"], {
        "uuid": "u-1", "codigo": "A", "cantidad": 98000,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
        "ubicacion_real": "P-9", "observaciones": "Estaba en otro estante",
    })
    return {"sesion_id": sesion_id, "juan": juan}


def leer_csv(texto):
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def test_resumen_tiene_las_columnas_del_spec(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))

    assert list(filas[0].keys()) == [
        "id_orden", "tipo", "material", "sku", "descripcion", "grupo",
        "ubicacion", "ubicacion_real", "unidad", "stock_sistema",
        "ultimo_conteo", "dif", "costo_unitario", "dif_valorizada",
        "estado", "fecha", "observaciones",
    ]


def test_cantidades_salen_con_coma_decimal(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_a = next(f for f in filas if f["sku"] == "A")

    assert fila_a["stock_sistema"] == "100"
    assert fila_a["ultimo_conteo"] == "98"
    assert fila_a["dif"] == "-2"


def test_articulo_sin_contar_deja_columnas_vacias(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_b = next(f for f in filas if f["sku"] == "B")

    assert fila_b["ultimo_conteo"] == ""
    assert fila_b["dif"] == ""
    assert fila_b["estado"] == "SIN CONTAR"


def test_valorizacion_vacia_si_no_hay_costo(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_b = next(f for f in filas if f["sku"] == "B")

    assert fila_b["costo_unitario"] == ""
    assert fila_b["dif_valorizada"] == ""


def test_valorizacion_calculada(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_a = next(f for f in filas if f["sku"] == "A")

    assert fila_a["costo_unitario"] == "25,00"
    assert fila_a["dif_valorizada"] == "-50,00"


def test_resumen_respeta_filtros(con, escenario):
    texto = exportacion.resumen_por_sku(
        con, escenario["sesion_id"], {"grupo": "Bazar"}
    )
    filas = leer_csv(texto)

    assert filas == []


def test_detalle_tiene_una_fila_por_escaneo(con, escenario):
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert len(filas) == 1
    assert filas[0]["sku"] == "A"
    assert filas[0]["operario"] == "Juan"
    assert filas[0]["cantidad"] == "98"
    assert filas[0]["pasada"] == "Conteo 1"
    assert filas[0]["ubicacion_real"] == "P-9"
    assert filas[0]["observaciones"] == "Estaba en otro estante"
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_exportacion.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.servicios.exportacion'`

- [ ] **Step 3: Implementar `servidor/app/servicios/exportacion.py`**

```python
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
    "fecha", "pasada", "operario", "sku", "descripcion", "unidad",
    "cantidad", "ubicacion", "ubicacion_real", "observaciones", "anulado",
]


def _milesimas(valor):
    return "" if valor is None else cantidades.a_texto(valor)


def _centavos(valor):
    if valor is None:
        return ""
    signo = "-" if valor < 0 else ""
    entero, resto = divmod(abs(valor), 100)
    return f"{signo}{entero},{resto:02d}"


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


def detalle(con, sesion_id):
    anulados = {
        fila["anula_uuid"]
        for fila in con.execute(
            "SELECT anula_uuid FROM conteo WHERE anula_uuid IS NOT NULL"
        )
    }

    crudas = con.execute(
        """
        SELECT c.uuid, c.cantidad, c.ubicacion_real, c.observaciones,
               c.timestamp_servidor, c.anula_uuid,
               a.sku, a.descripcion, a.unidad, a.ubicacion,
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

    filas = []
    for fila in crudas:
        es_anulacion = fila["anula_uuid"] is not None
        filas.append({
            "fecha": fila["timestamp_servidor"],
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
        })
    return _escribir(COLUMNAS_DETALLE, filas)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_exportacion.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Correr toda la suite**

Run: `cd servidor && python -m pytest tests/ -v`
Expected: PASS, todos

- [ ] **Step 6: Commit**

```bash
git add servidor/app/servicios/exportacion.py servidor/tests/test_exportacion.py
git commit -m "Agrega exportacion del resumen por SKU y del detalle

Usa punto y coma como separador y coma decimal, que es lo que espera
Excel en configuracion regional argentina. Con coma como separador, Excel
parte cada cantidad decimal en dos columnas y el archivo llega ilegible.

Los articulos sin contar dejan las columnas de conteo vacias en vez de
cero: un cero declara que se conto y dio cero, que es un dato distinto."
```

---

### Task 10: API HTTP

**Files:**
- Create: `servidor/app/main.py`
- Create: `servidor/app/api/__init__.py`
- Create: `servidor/app/api/panel.py`
- Create: `servidor/app/api/dispositivos.py`
- Create: `servidor/tests/test_api.py`

**Interfaces:**
- Consumes: todos los repos y servicios anteriores
- Produces:
  - `main.crear_app(ruta_db: str) -> FastAPI`
  - Endpoints de panel: `GET/POST /api/sesiones`, `POST /api/sesiones/{id}/cerrar`, `PUT /api/sesiones/{id}/tolerancia`, `POST /api/maestro/previsualizar`, `POST /api/sesiones/{id}/maestro`, `GET /api/sesiones/{id}/tablero`, `GET /api/sesiones/{id}/resumen`, `GET/POST /api/operarios`, `GET /api/sesiones/{id}/exportar/{tipo}`
  - Endpoints de dispositivo: `POST /api/dispositivo/vincular`, `GET /api/dispositivo/maestro`, `POST /api/dispositivo/conteos`, `GET /api/dispositivo/mis-conteos`

Los endpoints de dispositivo se autentican con el encabezado `X-Token` del operario.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app


@pytest.fixture
def cliente(tmp_path):
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def sesion(cliente):
    respuesta = cliente.post("/api/sesiones", json={"nombre": "Cliente X"})
    return respuesta.json()


CSV_MAESTRO = (
    "sku,detalle,stock\n"
    "A,Tornillo,100\n"
    "B,Tuerca,50\n"
).encode("utf-8")


def importar(cliente, sesion_id):
    return cliente.post(
        f"/api/sesiones/{sesion_id}/maestro",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
        data={"mapeo": '{"sku": "sku", "descripcion": "detalle", "stock_sistema": "stock"}'},
    )


def test_crear_sesion(cliente):
    respuesta = cliente.post("/api/sesiones", json={"nombre": "Cliente X"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["nombre"] == "Cliente X"
    assert cuerpo["pasada"]["etiqueta"] == "Conteo 1"


def test_no_permite_dos_sesiones_abiertas(cliente, sesion):
    respuesta = cliente.post("/api/sesiones", json={"nombre": "Otra"})

    assert respuesta.status_code == 409
    assert "sesión abierta" in respuesta.json()["detail"]


def test_previsualizar_maestro(cliente):
    respuesta = cliente.post(
        "/api/maestro/previsualizar",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["encabezados"] == ["sku", "detalle", "stock"]


def test_importar_maestro(cliente, sesion):
    respuesta = importar(cliente, sesion["id"])

    assert respuesta.status_code == 200
    assert respuesta.json()["importados"] == 2


def test_mapeo_invalido_devuelve_400(cliente, sesion):
    respuesta = cliente.post(
        f"/api/sesiones/{sesion['id']}/maestro",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
        data={"mapeo": '{"sku": "sku"}'},
    )

    assert respuesta.status_code == 400


def test_tablero_devuelve_filas_y_resumen(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/tablero")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["filas"]) == 2
    assert cuerpo["resumen"]["articulos"] == 2


def test_tablero_acepta_filtros(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(
        f"/api/sesiones/{sesion['id']}/tablero", params={"texto": "torni"}
    )

    assert len(respuesta.json()["filas"]) == 1


def test_vincular_dispositivo(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/vincular", headers={"X-Token": operario["token_dispositivo"]}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["operario"]["nombre"] == "Juan"
    assert cuerpo["sesion"]["id"] == sesion["id"]


def test_vincular_con_token_invalido_devuelve_401(cliente, sesion):
    respuesta = cliente.post(
        "/api/dispositivo/vincular", headers={"X-Token": "inventado"}
    )

    assert respuesta.status_code == 401


def test_maestro_para_dispositivo_no_expone_stock(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(
        "/api/dispositivo/maestro", headers={"X-Token": operario["token_dispositivo"]}
    )

    assert respuesta.status_code == 200
    articulos = respuesta.json()["articulos"]
    assert len(articulos) == 2
    for articulo in articulos:
        assert "stock_sistema" not in articulo
        assert "costo_unitario" not in articulo


def test_enviar_conteos(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/conteos",
        headers={"X-Token": operario["token_dispositivo"]},
        json={"conteos": [
            {"uuid": "u-1", "codigo": "A", "cantidad": 98000,
             "timestamp_dispositivo": "2026-08-10T10:00:00Z"},
        ]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["registrados"] == 1


def test_reenviar_conteos_no_duplica(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cuerpo = {"conteos": [
        {"uuid": "u-1", "codigo": "A", "cantidad": 98000,
         "timestamp_dispositivo": "2026-08-10T10:00:00Z"},
    ]}
    encabezados = {"X-Token": operario["token_dispositivo"]}

    cliente.post("/api/dispositivo/conteos", headers=encabezados, json=cuerpo)
    respuesta = cliente.post("/api/dispositivo/conteos", headers=encabezados, json=cuerpo)

    assert respuesta.json()["duplicados"] == 1

    tablero = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()
    fila_a = next(f for f in tablero["filas"] if f["sku"] == "A")
    assert fila_a["ultimo_conteo"] == 98000


def test_exportar_resumen(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/exportar/resumen")

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]

    lineas = respuesta.text.lstrip("﻿").splitlines()
    assert lineas[0].startswith("id_orden;tipo;material;sku")
    assert len(lineas) == 3  # encabezado + dos artículos


def test_exportar_tipo_inexistente_devuelve_404(cliente, sesion):
    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/exportar/inventado")

    assert respuesta.status_code == 404
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_api.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Implementar `servidor/app/api/panel.py`**

Crear también `servidor/app/api/__init__.py` vacío.

```python
"""Endpoints que consume el panel web."""

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.repos import operarios, sesiones
from app.servicios import exportacion, importacion, tablero

router = APIRouter(prefix="/api")


def _con(request):
    return request.app.state.con


@router.get("/sesiones")
def listar_sesiones(request: Request):
    return sesiones.listar(_con(request))


@router.post("/sesiones")
async def crear_sesion(request: Request):
    cuerpo = await request.json()
    con = _con(request)
    try:
        sesion_id = sesiones.crear(con, cuerpo["nombre"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    sesion = sesiones.obtener(con, sesion_id)
    sesion["pasada"] = sesiones.pasada_abierta(con, sesion_id)
    return sesion


@router.post("/sesiones/{sesion_id}/cerrar")
def cerrar_sesion(sesion_id: int, request: Request):
    sesiones.cerrar(_con(request), sesion_id)
    return {"estado": "cerrada"}


@router.put("/sesiones/{sesion_id}/tolerancia")
async def fijar_tolerancia(sesion_id: int, request: Request):
    cuerpo = await request.json()
    sesiones.fijar_tolerancia(
        _con(request), sesion_id, cuerpo["pct"], cuerpo["min_abs"]
    )
    return sesiones.obtener(_con(request), sesion_id)


@router.post("/maestro/previsualizar")
async def previsualizar_maestro(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    try:
        return importacion.previsualizar(contenido)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sesiones/{sesion_id}/maestro")
async def importar_maestro(
    sesion_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    mapeo: str = Form(...),
    unidad_por_defecto: str = Form("UN"),
):
    contenido = await archivo.read()
    try:
        return importacion.importar(
            _con(request), sesion_id, contenido, json.loads(mapeo), unidad_por_defecto
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sesiones/{sesion_id}/tablero")
def ver_tablero(
    sesion_id: int,
    request: Request,
    tipo: str = "", material: str = "", grupo: str = "",
    ubicacion: str = "", estado: str = "", texto: str = "",
    solo_errores_carga: bool = False,
):
    con = _con(request)
    filtros = {
        "tipo": tipo, "material": material, "grupo": grupo,
        "ubicacion": ubicacion, "estado": estado, "texto": texto,
        "solo_errores_carga": solo_errores_carga,
    }
    return {
        "filas": tablero.filas(con, sesion_id, filtros),
        "resumen": tablero.resumen(con, sesion_id),
    }


@router.get("/operarios")
def listar_operarios(request: Request):
    return operarios.listar(_con(request))


@router.post("/operarios")
async def crear_operario(request: Request):
    cuerpo = await request.json()
    try:
        return operarios.crear(_con(request), cuerpo["nombre"], cuerpo.get("pin"))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/sesiones/{sesion_id}/exportar/{tipo}")
def exportar(sesion_id: int, tipo: str, request: Request):
    con = _con(request)
    if tipo == "resumen":
        texto = exportacion.resumen_por_sku(con, sesion_id)
    elif tipo == "detalle":
        texto = exportacion.detalle(con, sesion_id)
    else:
        raise HTTPException(status_code=404, detail=f"No existe la exportación «{tipo}»")

    # El BOM hace que Excel reconozca UTF-8 y muestre bien los acentos.
    return Response(
        content="﻿" + texto,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{tipo}-{sesion_id}.csv"'
        },
    )
```

- [ ] **Step 4: Implementar `servidor/app/api/dispositivos.py`**

```python
"""Endpoints que consumen la app y la PWA.

Ninguna respuesta de este módulo puede incluir stock_sistema ni
costo_unitario: el conteo es a ciegas y el dato no debe existir en el
dispositivo, ni siquiera oculto en la pantalla.
"""

from fastapi import APIRouter, Header, HTTPException, Request

from app.repos import conteos, operarios, sesiones

router = APIRouter(prefix="/api/dispositivo")


def _contexto(request, token):
    con = request.app.state.con
    operario = operarios.por_token(con, token or "")
    if operario is None:
        raise HTTPException(status_code=401, detail="Token de operario inválido")

    sesion = sesiones.sesion_abierta(con)
    if sesion is None:
        raise HTTPException(status_code=409, detail="No hay ninguna sesión abierta")

    return con, operario, sesion


@router.post("/vincular")
def vincular(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    return {
        "operario": {"id": operario["id"], "nombre": operario["nombre"]},
        "sesion": {"id": sesion["id"], "nombre": sesion["nombre"]},
        "pasada": sesiones.pasada_abierta(con, sesion["id"]),
    }


@router.get("/maestro")
def descargar_maestro(request: Request, x_token: str = Header(default="")):
    con, _, sesion = _contexto(request, x_token)

    articulos = con.execute(
        """
        SELECT a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion,
               a.grupo, a.ubicacion, a.unidad
        FROM articulo a
        WHERE a.sesion_id = ? AND a.fusionado_en IS NULL
        ORDER BY a.id_orden
        """,
        (sesion["id"],),
    ).fetchall()

    codigos = con.execute(
        """
        SELECT cb.codigo, cb.articulo_id
        FROM codigo_barras cb
        JOIN articulo a ON a.id = cb.articulo_id
        WHERE a.sesion_id = ?
        """,
        (sesion["id"],),
    ).fetchall()

    unidades = con.execute("SELECT * FROM unidad").fetchall()

    return {
        "sesion_id": sesion["id"],
        "articulos": [dict(fila) for fila in articulos],
        "codigos": [dict(fila) for fila in codigos],
        "unidades": [dict(fila) for fila in unidades],
    }


@router.post("/conteos")
async def recibir_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    cuerpo = await request.json()

    return conteos.registrar_lote(
        con, sesion["id"], operario["id"], cuerpo.get("conteos", [])
    )


@router.get("/mis-conteos")
def mis_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    return conteos.de_operario(con, sesion["id"], operario["id"])
```

- [ ] **Step 5: Implementar `servidor/app/main.py`**

```python
"""Punto de entrada del servidor."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.api import dispositivos, panel

RUTA_PANEL = Path(__file__).parent.parent / "panel"
RUTA_DB_POR_DEFECTO = Path(__file__).parent.parent / "inventario.db"


def crear_app(ruta_db=None):
    ruta = str(ruta_db or RUTA_DB_POR_DEFECTO)

    @asynccontextmanager
    async def ciclo_de_vida(app):
        app.state.con = db.conectar(ruta)
        db.crear_esquema(app.state.con)
        yield
        app.state.con.close()

    app = FastAPI(title="Control de Stock", lifespan=ciclo_de_vida)
    app.include_router(panel.router)
    app.include_router(dispositivos.router)

    if RUTA_PANEL.exists():
        app.mount("/", StaticFiles(directory=RUTA_PANEL, html=True), name="panel")

    return app


app = crear_app()
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_api.py -v`
Expected: PASS, 14 tests

- [ ] **Step 7: Correr toda la suite**

Run: `cd servidor && python -m pytest tests/ -v`
Expected: PASS, todos

- [ ] **Step 8: Commit**

```bash
git add servidor/app/main.py servidor/app/api/ servidor/tests/test_api.py
git commit -m "Expone la API del panel y de los dispositivos

Los endpoints de dispositivo se separan en su propio modulo con una regla
unica: ninguna respuesta puede incluir stock_sistema ni costo_unitario.
Tenerlos aparte hace que la regla sea revisable de un vistazo, en vez de
quedar dispersa entre endpoints del panel que si los necesitan.

La autenticacion del dispositivo es el token del operario, el mismo que
viaja en su QR personal.

El CSV exportado lleva BOM para que Excel reconozca UTF-8 y no muestre
los acentos rotos."
```

---

### Task 11: Panel web

**Files:**
- Create: `servidor/panel/index.html`
- Create: `servidor/panel/estilos.css`
- Create: `servidor/panel/app.js`
- Create: `servidor/tests/test_panel_estatico.py`

**Interfaces:**
- Consumes: la API de Task 10
- Produces: el panel funcionando en `http://<ip>:8000/`

Sin frameworks ni dependencias externas: durante el conteo puede no haber internet.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_panel_estatico.py`:

```python
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import crear_app

RUTA_PANEL = Path(__file__).resolve().parent.parent / "panel"


@pytest.fixture
def cliente(tmp_path):
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


def test_el_panel_se_sirve_en_la_raiz(cliente):
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "Control de Stock" in respuesta.text


def test_no_hay_referencias_a_recursos_externos():
    """Durante el conteo puede no haber internet: todo se sirve local."""
    patron = re.compile(r'(src|href)\s*=\s*["\']https?://', re.IGNORECASE)

    for archivo in RUTA_PANEL.rglob("*"):
        if archivo.suffix in {".html", ".css", ".js"}:
            contenido = archivo.read_text(encoding="utf-8")
            assert not patron.search(contenido), f"{archivo.name} carga algo externo"


def test_los_estados_usan_texto_ademas_de_color():
    """El estado no puede comunicarse solo con color (spec, sección 8)."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    for estado in ["SIN CONTAR", "CONSOLIDADO", "A RECONTAR"]:
        assert estado in contenido
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_panel_estatico.py -v`
Expected: FAIL — la carpeta `panel/` no existe

- [ ] **Step 3: Crear `servidor/panel/index.html`**

```html
<!doctype html>
<html lang="es-AR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Control de Stock</title>
  <link rel="stylesheet" href="estilos.css">
</head>
<body>
  <header class="barra">
    <h1>Control de Stock</h1>
    <div id="sesion-actual" class="sesion-actual"></div>
  </header>

  <nav class="pestanas">
    <button data-vista="tablero" class="activa">Tablero</button>
    <button data-vista="maestro">Importar maestro</button>
    <button data-vista="operarios">Operarios</button>
    <button data-vista="sesiones">Sesiones</button>
  </nav>

  <main>
    <section id="vista-tablero" class="vista">
      <div id="metricas" class="metricas"></div>

      <div class="filtros">
        <input id="filtro-texto" type="search" placeholder="Buscar por SKU o descripción">
        <select id="filtro-estado">
          <option value="">Todos los estados</option>
          <option value="SIN CONTAR">Sin contar</option>
          <option value="CONSOLIDADO">Consolidado</option>
          <option value="A RECONTAR">A recontar</option>
        </select>
        <select id="filtro-grupo"><option value="">Todos los grupos</option></select>
        <select id="filtro-ubicacion"><option value="">Todas las ubicaciones</option></select>
        <label class="casilla">
          <input id="filtro-errores-carga" type="checkbox">
          Solo posibles errores de carga
        </label>
        <button id="limpiar-filtros" class="secundario">Limpiar filtros</button>
        <a id="exportar-resumen" class="boton secundario">Exportar resumen</a>
        <a id="exportar-detalle" class="boton secundario">Exportar detalle</a>
      </div>

      <div class="tabla-envoltorio" id="envoltorio-tabla">
        <table id="tabla">
          <thead>
            <tr>
              <th>#</th><th>Tipo</th><th>Material</th><th>SKU</th>
              <th>Descripción</th><th>Grupo</th><th>Ubicación</th>
              <th>Ub. real</th><th>Un.</th>
              <th class="num">Sistema</th><th class="num">Último conteo</th>
              <th class="num">Dif.</th><th>Estado</th><th>Fecha</th><th>Observaciones</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <section id="vista-maestro" class="vista oculta">
      <h2>Importar maestro</h2>
      <p class="ayuda">
        Elegí el CSV que exporta el sistema de gestión. Después indicá qué
        columna del archivo corresponde a cada campo.
      </p>
      <input id="archivo" type="file" accept=".csv,.txt">
      <div id="mapeo" class="mapeo oculta">
        <table id="tabla-mapeo"><tbody></tbody></table>
        <label>
          Unidad por defecto
          <select id="unidad-defecto">
            <option>UN</option><option>KG</option><option>LT</option>
            <option>MT</option><option>CJ</option><option>PACK</option>
          </select>
        </label>
        <h3>Vista previa</h3>
        <div class="tabla-envoltorio">
          <table id="tabla-vista-previa"></table>
        </div>
        <button id="confirmar-importacion">Importar</button>
      </div>
      <div id="resultado-importacion"></div>
    </section>

    <section id="vista-operarios" class="vista oculta">
      <h2>Operarios</h2>
      <form id="form-operario">
        <input id="nombre-operario" placeholder="Nombre y apellido" required>
        <button>Agregar</button>
      </form>
      <ul id="lista-operarios" class="lista"></ul>
    </section>

    <section id="vista-sesiones" class="vista oculta">
      <h2>Sesiones</h2>
      <form id="form-sesion">
        <input id="nombre-sesion" placeholder="Cliente y fecha" required>
        <button>Crear sesión</button>
      </form>
      <ul id="lista-sesiones" class="lista"></ul>
    </section>
  </main>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Crear `servidor/panel/estilos.css`**

```css
:root {
  --fondo: #f5f6f8;
  --panel: #ffffff;
  --borde: #d7dbe0;
  --texto: #1c2126;
  --tenue: #5c6873;
  --acento: #1f5fa9;
  --verde: #1b7a3d;
  --verde-fondo: #e6f4ea;
  --rojo: #b3261e;
  --rojo-fondo: #fce8e6;
  --gris-fondo: #eceff1;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--fondo);
  color: var(--texto);
  font-size: 15px;
}

.barra {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1.25rem;
  background: var(--panel);
  border-bottom: 1px solid var(--borde);
}

.barra h1 { font-size: 1.1rem; margin: 0; }
.sesion-actual { color: var(--tenue); }

.pestanas {
  display: flex;
  gap: 0.25rem;
  padding: 0 1.25rem;
  background: var(--panel);
  border-bottom: 1px solid var(--borde);
}

.pestanas button {
  border: 0;
  background: none;
  padding: 0.7rem 1rem;
  cursor: pointer;
  font-size: 0.95rem;
  color: var(--tenue);
  border-bottom: 3px solid transparent;
}

.pestanas button.activa { color: var(--acento); border-bottom-color: var(--acento); }

main { padding: 1.25rem; }
.vista.oculta, .oculta { display: none; }

.metricas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.metrica {
  background: var(--panel);
  border: 1px solid var(--borde);
  border-radius: 6px;
  padding: 0.75rem 1rem;
}

.metrica .valor { font-size: 1.6rem; font-weight: 600; }
.metrica .rotulo { color: var(--tenue); font-size: 0.85rem; }

.filtros {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  align-items: center;
}

input, select, button, .boton {
  font: inherit;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--borde);
  border-radius: 5px;
  background: var(--panel);
  color: var(--texto);
}

button, .boton {
  cursor: pointer;
  background: var(--acento);
  color: #fff;
  border-color: var(--acento);
  text-decoration: none;
}

button.secundario, .boton.secundario {
  background: var(--panel);
  color: var(--texto);
  border-color: var(--borde);
}

.tabla-envoltorio {
  overflow: auto;
  max-height: calc(100vh - 320px);
  background: var(--panel);
  border: 1px solid var(--borde);
  border-radius: 6px;
}

table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }

th, td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--borde);
  text-align: left;
  white-space: nowrap;
}

thead th {
  position: sticky;
  top: 0;
  background: var(--panel);
  z-index: 1;
  box-shadow: inset 0 -1px 0 var(--borde);
}

.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }

.estado {
  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.marca {
  display: inline-block;
  margin-left: 0.35rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  border: 1px solid var(--borde);
  font-size: 0.78rem;
  color: var(--tenue);
}

.casilla {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 1px solid var(--borde);
  border-radius: 5px;
  padding: 0.4rem 0.7rem;
  background: var(--panel);
}

.casilla input { padding: 0; }

.estado-consolidado { background: var(--verde-fondo); color: var(--verde); }
.estado-a-recontar { background: var(--rojo-fondo); color: var(--rojo); }
.estado-sin-contar { background: var(--gris-fondo); color: var(--tenue); }

.lista { list-style: none; padding: 0; }

.lista li {
  background: var(--panel);
  border: 1px solid var(--borde);
  border-radius: 6px;
  padding: 0.6rem 0.9rem;
  margin-bottom: 0.4rem;
}

.ayuda { color: var(--tenue); max-width: 60ch; }
.mapeo { margin-top: 1rem; }
.error { color: var(--rojo); }
```

- [ ] **Step 5: Crear `servidor/panel/app.js`**

```javascript
"use strict";

// Estado del panel. `filtros` vive acá para que el refresco automático no
// los pierda ni mueva el scroll: un tablero que salta mientras se lee es
// inservible.
const estado = {
  sesion: null,
  filtros: {
    texto: "", estado: "", grupo: "", ubicacion: "", solo_errores_carga: false,
  },
};

const ESTADOS = {
  "SIN CONTAR": "estado-sin-contar",
  "CONSOLIDADO": "estado-consolidado",
  "A RECONTAR": "estado-a-recontar",
};

const $ = (selector) => document.querySelector(selector);

async function pedir(url, opciones = {}) {
  const respuesta = await fetch(url, opciones);
  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}));
    throw new Error(cuerpo.detail || "No se pudo completar la operación");
  }
  return respuesta.json();
}

function milesimasATexto(valor) {
  if (valor === null || valor === undefined) return "";
  const signo = valor < 0 ? "-" : "";
  const absoluto = Math.abs(valor);
  const entero = Math.floor(absoluto / 1000);
  const resto = absoluto % 1000;
  if (resto === 0) return `${signo}${entero}`;
  return `${signo}${entero},${String(resto).padStart(3, "0").replace(/0+$/, "")}`;
}

// --- Tablero ---------------------------------------------------------------

function dibujarMetricas(resumen) {
  const tarjetas = [
    ["Avance", `${resumen.avance_pct}%`],
    ["Contados", `${resumen.contados} / ${resumen.articulos}`],
    ["Consolidados", resumen.consolidados],
    ["A recontar", resumen.a_recontar],
    ["Posible error de carga", resumen.posibles_errores_carga],
    ["Altas rápidas", resumen.altas_rapidas],
  ];
  $("#metricas").innerHTML = tarjetas
    .map(([rotulo, valor]) =>
      `<div class="metrica"><div class="valor">${valor}</div>` +
      `<div class="rotulo">${rotulo}</div></div>`)
    .join("");
}

function dibujarFilas(filas) {
  const cuerpo = $("#tabla tbody");
  cuerpo.innerHTML = filas.map((fila) => `
    <tr>
      <td class="num">${fila.id_orden}</td>
      <td>${fila.tipo || ""}</td>
      <td>${fila.material || ""}</td>
      <td>${fila.sku}</td>
      <td>${fila.descripcion}</td>
      <td>${fila.grupo || ""}</td>
      <td>${fila.ubicacion || ""}</td>
      <td>${fila.ubicacion_real || ""}</td>
      <td>${fila.unidad}</td>
      <td class="num">${milesimasATexto(fila.stock_sistema)}</td>
      <td class="num">${milesimasATexto(fila.ultimo_conteo)}</td>
      <td class="num">${milesimasATexto(fila.dif)}</td>
      <td>
        <span class="estado ${ESTADOS[fila.estado]}">${fila.estado}</span>
        ${fila.posible_error_carga
          ? `<span class="marca" title="Revisar antes de recontar: ${fila.posible_error_carga}">⌨ ${fila.posible_error_carga}</span>`
          : ""}
      </td>
      <td>${(fila.fecha || "").replace("T", " ").replace("Z", "")}</td>
      <td>${fila.observaciones || ""}</td>
    </tr>`).join("");
}

function completarOpciones(select, valores, rotuloTodos) {
  const elegido = select.value;
  select.innerHTML = `<option value="">${rotuloTodos}</option>` +
    valores.map((valor) => `<option>${valor}</option>`).join("");
  select.value = elegido;
}

async function refrescarTablero() {
  if (!estado.sesion) return;

  const envoltorio = $("#envoltorio-tabla");
  const scroll = envoltorio.scrollTop;

  const parametros = new URLSearchParams(estado.filtros);
  const datos = await pedir(
    `/api/sesiones/${estado.sesion.id}/tablero?${parametros}`);

  dibujarMetricas(datos.resumen);
  dibujarFilas(datos.filas);

  completarOpciones($("#filtro-grupo"),
    [...new Set(datos.filas.map((f) => f.grupo).filter(Boolean))].sort(),
    "Todos los grupos");
  completarOpciones($("#filtro-ubicacion"),
    [...new Set(datos.filas.map((f) => f.ubicacion).filter(Boolean))].sort(),
    "Todas las ubicaciones");

  envoltorio.scrollTop = scroll;
}

// --- Sesiones --------------------------------------------------------------

async function cargarSesiones() {
  const sesiones = await pedir("/api/sesiones");
  estado.sesion = sesiones.find((s) => s.estado === "abierta") || null;

  $("#sesion-actual").textContent = estado.sesion
    ? `Sesión: ${estado.sesion.nombre}`
    : "Sin sesión abierta";

  $("#lista-sesiones").innerHTML = sesiones.map((sesion) => `
    <li>
      <strong>${sesion.nombre}</strong> — ${sesion.estado}
      ${sesion.estado === "abierta"
        ? `<button class="secundario" data-cerrar="${sesion.id}">Cerrar</button>`
        : ""}
    </li>`).join("") || "<li>Todavía no hay sesiones.</li>";

  if (estado.sesion) {
    $("#exportar-resumen").href =
      `/api/sesiones/${estado.sesion.id}/exportar/resumen`;
    $("#exportar-detalle").href =
      `/api/sesiones/${estado.sesion.id}/exportar/detalle`;
    await refrescarTablero();
  }
}

// --- Importación del maestro -----------------------------------------------

const CAMPOS = [
  ["id_orden", "Número de orden"], ["tipo", "Tipo"], ["material", "Material"],
  ["sku", "SKU (obligatorio)"], ["descripcion", "Descripción (obligatorio)"],
  ["grupo", "Grupo"], ["ubicacion", "Ubicación"], ["unidad", "Unidad"],
  ["stock_sistema", "Stock del sistema"], ["costo_unitario", "Costo unitario"],
  ["codigo_barras", "Código de barras"],
];

let archivoElegido = null;

async function previsualizarArchivo(archivo) {
  archivoElegido = archivo;
  const cuerpo = new FormData();
  cuerpo.append("archivo", archivo);

  const vista = await pedir("/api/maestro/previsualizar",
    { method: "POST", body: cuerpo });

  $("#tabla-mapeo").querySelector("tbody").innerHTML = CAMPOS.map(
    ([campo, rotulo]) => `
      <tr>
        <td><label for="mapeo-${campo}">${rotulo}</label></td>
        <td>
          <select id="mapeo-${campo}" data-campo="${campo}">
            <option value="">— sin asignar —</option>
            ${vista.encabezados.map((encabezado) => {
              const coincide = encabezado.toLowerCase() === campo ? " selected" : "";
              return `<option${coincide}>${encabezado}</option>`;
            }).join("")}
          </select>
        </td>
      </tr>`).join("");

  $("#tabla-vista-previa").innerHTML =
    `<thead><tr>${vista.encabezados.map((e) => `<th>${e}</th>`).join("")}</tr></thead>` +
    `<tbody>${vista.filas.map((fila) =>
      `<tr>${fila.map((celda) => `<td>${celda}</td>`).join("")}</tr>`).join("")}</tbody>`;

  $("#mapeo").classList.remove("oculta");
}

async function confirmarImportacion() {
  if (!estado.sesion) {
    $("#resultado-importacion").innerHTML =
      '<p class="error">Primero creá una sesión.</p>';
    return;
  }

  const mapeo = {};
  document.querySelectorAll("[data-campo]").forEach((select) => {
    if (select.value) mapeo[select.dataset.campo] = select.value;
  });

  const cuerpo = new FormData();
  cuerpo.append("archivo", archivoElegido);
  cuerpo.append("mapeo", JSON.stringify(mapeo));
  cuerpo.append("unidad_por_defecto", $("#unidad-defecto").value);

  try {
    const resultado = await pedir(
      `/api/sesiones/${estado.sesion.id}/maestro`,
      { method: "POST", body: cuerpo });

    $("#resultado-importacion").innerHTML =
      `<p>Se importaron <strong>${resultado.importados}</strong> artículos ` +
      `y ${resultado.codigos} códigos de barras.</p>` +
      (resultado.descartadas.length
        ? `<p>Se descartaron ${resultado.descartadas.length} filas sin SKU.</p>` : "") +
      (resultado.advertencias.length
        ? `<p>${resultado.advertencias.length} filas con datos corregidos.</p>` : "");

    await refrescarTablero();
  } catch (error) {
    $("#resultado-importacion").innerHTML = `<p class="error">${error.message}</p>`;
  }
}

// --- Operarios -------------------------------------------------------------

async function cargarOperarios() {
  const lista = await pedir("/api/operarios");
  $("#lista-operarios").innerHTML = lista.map((operario) => `
    <li><strong>${operario.nombre}</strong></li>`).join("")
    || "<li>Todavía no hay operarios.</li>";
}

// --- Arranque --------------------------------------------------------------

function conectarEventos() {
  document.querySelectorAll(".pestanas button").forEach((boton) => {
    boton.addEventListener("click", () => {
      document.querySelectorAll(".pestanas button")
        .forEach((otro) => otro.classList.remove("activa"));
      boton.classList.add("activa");
      document.querySelectorAll(".vista")
        .forEach((vista) => vista.classList.add("oculta"));
      $(`#vista-${boton.dataset.vista}`).classList.remove("oculta");
    });
  });

  $("#filtro-texto").addEventListener("input", (evento) => {
    estado.filtros.texto = evento.target.value;
    refrescarTablero();
  });

  ["estado", "grupo", "ubicacion"].forEach((campo) => {
    $(`#filtro-${campo}`).addEventListener("change", (evento) => {
      estado.filtros[campo] = evento.target.value;
      refrescarTablero();
    });
  });

  $("#filtro-errores-carga").addEventListener("change", (evento) => {
    estado.filtros.solo_errores_carga = evento.target.checked;
    refrescarTablero();
  });

  $("#limpiar-filtros").addEventListener("click", () => {
    estado.filtros = {
      texto: "", estado: "", grupo: "", ubicacion: "", solo_errores_carga: false,
    };
    $("#filtro-texto").value = "";
    $("#filtro-errores-carga").checked = false;
    ["estado", "grupo", "ubicacion"].forEach((campo) => {
      $(`#filtro-${campo}`).value = "";
    });
    refrescarTablero();
  });

  $("#archivo").addEventListener("change", (evento) => {
    if (evento.target.files.length) previsualizarArchivo(evento.target.files[0]);
  });

  $("#confirmar-importacion").addEventListener("click", confirmarImportacion);

  $("#form-operario").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    await pedir("/api/operarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nombre: $("#nombre-operario").value }),
    });
    $("#nombre-operario").value = "";
    await cargarOperarios();
  });

  $("#form-sesion").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await pedir("/api/sesiones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: $("#nombre-sesion").value }),
      });
      $("#nombre-sesion").value = "";
      await cargarSesiones();
    } catch (error) {
      alert(error.message);
    }
  });

  $("#lista-sesiones").addEventListener("click", async (evento) => {
    const id = evento.target.dataset.cerrar;
    if (!id) return;
    if (!confirm("¿Cerrar la sesión? No se van a poder cargar más conteos.")) return;
    await pedir(`/api/sesiones/${id}/cerrar`, { method: "POST" });
    await cargarSesiones();
  });
}

async function iniciar() {
  conectarEventos();
  await cargarSesiones();
  await cargarOperarios();
  setInterval(refrescarTablero, 4000);
}

iniciar();
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_panel_estatico.py -v`
Expected: PASS, 3 tests

- [ ] **Step 7: Probar el panel a mano**

Run: `cd servidor && python -m uvicorn app.main:app --port 8000`

Abrir `http://localhost:8000`, crear una sesión, importar un CSV de prueba y verificar que el tablero muestra los artículos. Cortar con `Ctrl+C`.

- [ ] **Step 8: Commit**

```bash
git add servidor/panel/ servidor/tests/test_panel_estatico.py
git commit -m "Agrega el panel web con tablero, importacion y operarios

Sin frameworks ni recursos externos, con un test que lo verifica: durante
el conteo puede no haber internet y una fuente o libreria remota dejaria
el panel a medio dibujar.

El refresco automatico conserva scroll y filtros. Sin eso el tablero
salta mientras se lo lee, que es la forma mas rapida de volverlo inutil.

El estado se muestra con texto ademas de color, para que una diferencia
no pase desapercibida por daltonismo o por un monitor mal calibrado."
```

---

### Task 12: Arranque en Windows

**Files:**
- Create: `servidor/iniciar.py`
- Create: `Iniciar servidor.bat`
- Create: `servidor/tests/test_red.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `main.crear_app` (Task 10)
- Produces:
  - `iniciar.ip_local() -> str` — la IP de la máquina en la red local
  - `iniciar.main() -> None` — levanta uvicorn y muestra la dirección

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_red.py`:

```python
import ipaddress

import iniciar


def test_ip_local_es_una_ip_valida():
    ip = iniciar.ip_local()

    direccion = ipaddress.ip_address(ip)
    assert direccion.version == 4


def test_ip_local_no_es_loopback():
    """Si devolviera 127.0.0.1, los celulares no podrían llegar al servidor."""
    ip = iniciar.ip_local()

    assert not ipaddress.ip_address(ip).is_loopback
```

No hace falta tocar `conftest.py`: la línea `sys.path.insert` de la Task 1 ya agrega `servidor/` al path, y `iniciar.py` vive ahí, así que se importa directamente.

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd servidor && python -m pytest tests/test_red.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'iniciar'`

- [ ] **Step 3: Implementar `servidor/iniciar.py`**

```python
"""Arranque del servidor con la dirección visible para los celulares."""

import socket

import uvicorn

PUERTO = 8000


def ip_local():
    """La IP de esta máquina en la red local.

    Abrir un socket UDP hacia una dirección externa no envía nada, pero
    obliga al sistema a elegir la interfaz de salida. Es la forma
    confiable de saber con qué IP nos ven los celulares cuando hay varias
    placas de red (WiFi, Ethernet, VPN).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()


def main():
    ip = ip_local()
    print("=" * 56)
    print("  CONTROL DE STOCK")
    print("=" * 56)
    print(f"  Panel:      http://localhost:{PUERTO}")
    print(f"  Celulares:  http://{ip}:{PUERTO}")
    print()
    print("  Dejá esta ventana abierta mientras dure el conteo.")
    print("  Para terminar, cerrala o apretá Ctrl+C.")
    print("=" * 56)

    uvicorn.run("app.main:app", host="0.0.0.0", port=PUERTO, log_level="warning")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd servidor && python -m pytest tests/test_red.py -v`
Expected: PASS, 2 tests

- [ ] **Step 5: Crear `Iniciar servidor.bat` en la raíz del proyecto**

```bat
@echo off
chcp 65001 > nul
cd /d "%~dp0servidor"

if not exist ".venv\" (
    echo Preparando el entorno por primera vez...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

python iniciar.py
pause
```

- [ ] **Step 6: Crear `README.md` en la raíz**

```markdown
# Control de Stock

Toma de inventario con escaneo de códigos de barras. El servidor corre en
una PC y los celulares se conectan por la red WiFi del lugar.

## Cómo se usa

1. Doble clic en **Iniciar servidor.bat**. La primera vez tarda un poco
   más porque prepara el entorno.
2. Windows va a pedir permiso de firewall: hay que **aceptarlo para redes
   privadas**. Sin eso los celulares no llegan al servidor.
3. Se abre una ventana negra con dos direcciones. La de `localhost` es
   para esta PC; la otra es la que usan los celulares.
4. Abrir el panel en el navegador, crear una sesión e importar el maestro.

Dejá la ventana negra abierta mientras dure el conteo.

## La base de datos

Todo vive en `servidor/inventario.db`. Copiar ese archivo respalda el
inventario completo. No está en git a propósito: git no es el backup de
los datos.

## Para desarrollar

```bash
cd servidor
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest tests/ -v
```
```

- [ ] **Step 7: Verificar el arranque real**

Ejecutar `Iniciar servidor.bat` con doble clic. Verificar que:
- Muestra las dos direcciones.
- El panel abre en `http://localhost:8000`.
- Desde un celular en la misma WiFi, la dirección con IP también abre el panel.

- [ ] **Step 8: Correr la suite completa**

Run: `cd servidor && python -m pytest tests/ -v`
Expected: PASS, todos

- [ ] **Step 9: Commit**

```bash
git add servidor/iniciar.py "Iniciar servidor.bat" servidor/tests/test_red.py README.md
git commit -m "Agrega el arranque por doble clic en Windows

El .bat prepara el entorno la primera vez y despues solo levanta el
servidor, para que no haya que instalar nada a mano en la PC del cliente.

Detecta la IP local abriendo un socket UDP: no envia nada, pero obliga al
sistema a elegir la interfaz de salida, que es la forma confiable de
saber con que IP ven los celulares al servidor cuando hay varias placas
de red. Sin eso habria que dictar la IP a mano en cada lugar.

El README avisa del permiso de firewall, que es el motivo numero uno por
el que los celulares no encuentran el servidor."
```

---

## Verificación final del plan

Al terminar las 12 tareas, verificar de punta a punta:

```bash
cd servidor && python -m pytest tests/ -v
```

Todos los tests deben pasar. Después, prueba manual del circuito completo:

1. Doble clic en `Iniciar servidor.bat`.
2. Crear una sesión.
3. Importar un CSV de maestro mapeando las columnas.
4. Dar de alta dos operarios.
5. Simular conteos desde otra terminal:

```bash
curl -X POST http://localhost:8000/api/dispositivo/conteos ^
  -H "X-Token: <token del operario>" ^
  -H "Content-Type: application/json" ^
  -d "{\"conteos\":[{\"uuid\":\"u-1\",\"codigo\":\"<un sku>\",\"cantidad\":24000,\"timestamp_dispositivo\":\"2026-08-10T10:00:00Z\"}]}"
```

6. Verificar en el tablero que la fila cambió de estado y que las métricas se actualizaron solas.
7. Exportar resumen y detalle, y abrirlos en Excel para confirmar que los acentos y los decimales se ven bien.

Con esto el núcleo queda funcionando. El plan siguiente construye la app Android que reemplaza el paso 5.
