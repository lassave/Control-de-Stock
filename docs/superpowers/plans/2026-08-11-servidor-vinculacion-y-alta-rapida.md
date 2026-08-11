# Servidor: vinculación por QR, alta rápida y entrega del APK — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Goal:** Agregar al servidor las tres piezas que la app Android necesita y que hoy no existen: el QR con el que se vincula un celular, el alta de un artículo desconocido desde el dispositivo, y la descarga del APK desde el panel.

**Architecture:** Se mantiene la separación en tres capas del servidor: repositorios que hablan con la base, servicios con la lógica de negocio probable sin HTTP, y routers que solo traducen. El QR se genera con `segno`, que es Python puro. El alta rápida es un repositorio nuevo (`repos/articulos.py`) más un endpoint de dispositivo.

**Tech Stack:** Python 3.11+, FastAPI, sqlite3, pytest, segno.

Este plan corresponde a la sección 7 del spec `docs/superpowers/specs/2026-08-11-app-android-base-design.md`.

## Global Constraints

- **Cantidades en milésimas e importes en centavos, siempre `INTEGER`.** Las columnas tienen `CHECK (typeof(...) = 'integer')`.
- **`stock_sistema` y `costo_unitario` nunca salen por `/api/dispositivo/*`.** El conteo es a ciegas.
- **Sin dependencias externas en el navegador.** Todo se sirve desde el servidor local.
- **Fechas ISO 8601 UTC** como texto, y la única fuente es `app/reloj.py`.
- **Nada se edita ni se borra**: las correcciones son eventos nuevos.
- **Textos de interfaz y mensajes de error en castellano rioplatense.**
- **El intérprete es el del venv, por ruta:** `servidor\.venv\Scripts\python.exe`. El `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta nada.
- Los mensajes de commit van en castellano, en presente, describiendo el efecto.

Todos los comandos se ejecutan desde la raíz del repositorio.

---

### Task 1: QR de vinculación

**Files:**
- Create: `servidor/app/red.py`
- Create: `servidor/app/servicios/vinculacion.py`
- Create: `servidor/tests/test_vinculacion.py`
- Modify: `servidor/iniciar.py` (usa `red.ip_local` en vez de definirla)
- Modify: `servidor/tests/test_red.py` (importa de `app.red`)
- Modify: `servidor/app/repos/operarios.py` (`_obtener` pasa a ser público)
- Modify: `servidor/app/api/panel.py` (endpoint del QR)
- Modify: `servidor/tests/test_api.py`
- Modify: `servidor/panel/app.js` y `servidor/panel/estilos.css`
- Modify: `servidor/requirements.txt`

**Interfaces:**
- Consumes: `operarios.listar`, `operarios.crear` (ya existen)
- Produces:
  - `red.ip_local() -> str` — la IP de esta máquina en la red local
  - `vinculacion.contenido(url: str, token: str) -> str` — el JSON que va adentro del QR
  - `vinculacion.svg(texto: str) -> str` — un SVG como texto
  - `vinculacion.armar_url(ip: str, puerto: int) -> str`
  - `operarios.obtener(con, operario_id) -> dict | None`
  - `GET /api/operarios/{id}/qr` — SVG del QR de vinculación

**Por qué la IP no sale del pedido HTTP:** el panel se abre en `127.0.0.1`, así que `request.url.hostname` daría loopback y el QR mandaría al celular a sí mismo. La dirección tiene que ser la de la red local. El puerto sí se toma del pedido, para que siga funcionando si alguien cambia el puerto.

- [ ] **Step 1: Agregar `segno` a `servidor/requirements.txt`**

El archivo queda así:

```
fastapi==0.115.6
uvicorn==0.34.0
python-multipart==0.0.20
segno==1.6.6
pytest==8.3.4
httpx==0.28.1
```

Instalarlo:

Run: `.\servidor\.venv\Scripts\python.exe -m pip install -r servidor\requirements.txt`

- [ ] **Step 2: Escribir el test que falla**

Crear `servidor/tests/test_vinculacion.py`:

```python
import ipaddress
import json

import pytest

from app import red
from app.servicios import vinculacion


def test_ip_local_es_ipv4_y_no_loopback():
    """Si devolviera 127.0.0.1, el QR mandaría al celular a sí mismo."""
    direccion = ipaddress.ip_address(red.ip_local())

    assert direccion.version == 4
    assert not direccion.is_loopback


def test_armar_url():
    assert vinculacion.armar_url("172.16.11.12", 8000) == "http://172.16.11.12:8000"


def test_el_contenido_lleva_direccion_y_token():
    texto = vinculacion.contenido("http://172.16.11.12:8000", "abc123")

    datos = json.loads(texto)
    assert datos == {"u": "http://172.16.11.12:8000", "t": "abc123"}


def test_el_contenido_es_compacto():
    """Cada carácter agranda el QR, y uno más denso se lee peor con poca luz."""
    texto = vinculacion.contenido("http://172.16.11.12:8000", "abc123")

    assert ", " not in texto
    assert '": ' not in texto


def test_el_svg_es_texto_y_no_bytes():
    """segno escribe bytes; devolver bytes rompería la respuesta HTTP."""
    salida = vinculacion.svg("hola")

    assert isinstance(salida, str)
    assert "<svg" in salida


def test_el_svg_no_referencia_nada_externo():
    """Durante el conteo puede no haber internet."""
    salida = vinculacion.svg("hola")

    assert "http://www.w3.org/2000/svg" in salida  # el namespace no es una descarga
    assert "<image" not in salida
    assert "xlink:href" not in salida


def test_un_token_largo_sigue_entrando_en_el_qr():
    """Los tokens reales son de 43 caracteres, no los de tres letras del test."""
    token = "dsvDgRqPY-gh9gMh90kuyjGinb1GAxqddsoDG4y4AXk"

    salida = vinculacion.svg(
        vinculacion.contenido("http://172.16.11.12:8000", token)
    )

    assert "<svg" in salida


@pytest.mark.parametrize("valor", ["", None])
def test_rechaza_un_token_vacio(valor):
    """Un QR sin token se lee bien y vincula a nadie: falla silencioso."""
    with pytest.raises(ValueError, match="token"):
        vinculacion.contenido("http://172.16.11.12:8000", valor)
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_vinculacion.py -v --rootdir .\servidor`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.red'`

- [ ] **Step 4: Crear `servidor/app/red.py`**

El cuerpo de la función se mueve tal cual desde `iniciar.py`, sin cambios:

```python
"""Dirección de esta máquina en la red local.

Vive en `app` y no en `iniciar` porque la usan los dos: el arranque, para
mostrar la dirección en pantalla, y la API, para armar el QR de vinculación.
Duplicarla haría que un día muestren direcciones distintas.
"""

import socket


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
```

- [ ] **Step 5: Crear `servidor/app/servicios/vinculacion.py`**

```python
"""El QR con el que un celular se vincula al servidor.

Lleva adentro la dirección del servidor y el token del operario, así el
operario no tipea nada: ni la IP, que cambia en cada lugar, ni el token,
que son 43 caracteres al azar.
"""

import io
import json

import segno

# Corrección de errores media: tolera un QR manchado o mal impreso sin
# agrandarlo tanto como para que cueste enfocarlo de cerca.
CORRECCION = "m"


def armar_url(ip, puerto):
    return f"http://{ip}:{puerto}"


def contenido(url, token):
    """El texto que va adentro del QR.

    Compacto a propósito: cada carácter agrega módulos al QR, y uno más
    denso se lee peor justo donde se usa, con poca luz y a pulso.
    """
    if not token:
        raise ValueError("El QR necesita el token del operario")
    return json.dumps({"u": url, "t": token}, separators=(",", ":"))


def svg(texto):
    """Devuelve el QR como SVG.

    `segno` escribe bytes aunque el formato sea texto, así que hay que
    decodificar: devolver bytes haría que la respuesta HTTP saliera como
    una descarga en vez de dibujarse.
    """
    qr = segno.make(texto, error=CORRECCION)
    salida = io.BytesIO()
    qr.save(salida, kind="svg", scale=4, border=2,
            dark="#1c2126", light="#ffffff")
    return salida.getvalue().decode("utf-8")
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_vinculacion.py -v --rootdir .\servidor`
Expected: PASS, 9 tests (7 funciones, y la última corre dos veces por sus parámetros)

- [ ] **Step 7: Hacer que `iniciar.py` use `red.ip_local`**

En `servidor/iniciar.py`, borrar la función `ip_local` y su `import socket`, y reemplazarla por la importación. El archivo queda así de la primera línea hasta `mostrar_encabezado`:

```python
"""Arranque del servidor con la dirección visible para los celulares."""

import uvicorn

from app.red import ip_local

PUERTO = 8000

# 127.0.0.1 y no «localhost»: en Windows, localhost resuelve primero a ::1 y
# el servidor escucha en IPv4. La dirección numérica abre siempre, y esta
# línea es lo único que tiene quien levanta el servidor para llegar al panel.
LOCAL = "127.0.0.1"
```

El resto del archivo (`mostrar_encabezado` y `main`) no cambia: sigue llamando a `ip_local()`.

- [ ] **Step 8: Actualizar `servidor/tests/test_red.py`**

Cambiar el import y las dos referencias a `iniciar.ip_local`. El archivo empieza así:

```python
import ipaddress
from pathlib import Path

import iniciar
from app import red

RAIZ = Path(__file__).resolve().parent.parent.parent
ARRANQUE = RAIZ / "Iniciar servidor.bat"
```

Reemplazar los tres tests que llamaban a `iniciar.ip_local()` por estos:

```python
def test_ip_local_es_una_ip_valida():
    ip = red.ip_local()

    direccion = ipaddress.ip_address(ip)
    assert direccion.version == 4


def test_ip_local_no_es_loopback():
    """Si devolviera 127.0.0.1, los celulares no podrían llegar al servidor."""
    ip = red.ip_local()

    assert not ipaddress.ip_address(ip).is_loopback


def test_el_arranque_y_la_api_muestran_la_misma_direccion(capsys):
    """Dos implementaciones de la IP terminarían mostrando direcciones distintas."""
    iniciar.mostrar_encabezado()

    salida = capsys.readouterr().out
    assert f"http://{red.ip_local()}:{iniciar.PUERTO}" in salida
    assert f"http://{iniciar.LOCAL}:{iniciar.PUERTO}" in salida
```

Los tests `test_la_direccion_local_no_depende_de_resolver_un_nombre`,
`test_el_bat_de_arranque_usa_saltos_de_linea_de_windows` y
`test_el_bat_de_arranque_no_lleva_bom` quedan tal como están.

- [ ] **Step 9: Correr los tests de red y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_red.py -v --rootdir .\servidor`
Expected: PASS, 6 tests

- [ ] **Step 10: Hacer público `operarios.obtener`**

En `servidor/app/repos/operarios.py`, renombrar `_obtener` a `obtener` y actualizar la llamada de `crear` (línea 61). Queda:

```python
def obtener(con, operario_id):
    fila = con.execute(
        f"SELECT {CAMPOS} FROM operario WHERE id = ?", (operario_id,)
    ).fetchone()
    return dict(fila) if fila else None
```

Y dentro de `crear`, la última línea pasa a ser `return obtener(con, operario_id)`.

- [ ] **Step 11: Escribir el test del endpoint**

Agregar al final de `servidor/tests/test_api.py`:

```python
def test_el_qr_del_operario_se_sirve_como_svg(cliente):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(f"/api/operarios/{operario['id']}/qr")

    assert respuesta.status_code == 200
    assert "image/svg+xml" in respuesta.headers["content-type"]
    assert "<svg" in respuesta.text


def test_el_qr_no_apunta_a_loopback(cliente):
    """El celular tiene que llegar por la red, no a sí mismo."""
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(f"/api/operarios/{operario['id']}/qr")

    assert "127.0.0.1" not in respuesta.text


def test_el_qr_de_un_operario_inexistente_devuelve_404(cliente):
    assert cliente.get("/api/operarios/999/qr").status_code == 404
```

- [ ] **Step 12: Correr el test y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -k qr -v --rootdir .\servidor`
Expected: FAIL los dos primeros, porque la ruta todavía no existe y devuelve 404. El tercero pasa desde el principio: una ruta inexistente también da 404. Recién dice algo cuando la ruta existe.

- [ ] **Step 13: Agregar el endpoint en `servidor/app/api/panel.py`**

Agregar `red` y `vinculacion` a los imports:

```python
from app import red
from app.repos import operarios, sesiones
from app.servicios import exportacion, importacion, tablero, vinculacion
```

Y el endpoint, después de `crear_operario`:

```python
@router.get("/operarios/{operario_id}/qr")
def qr_de_operario(operario_id: int, request: Request):
    """El QR con el que se vincula un celular: dirección del servidor y token.

    La dirección sale de la IP de la red local y no del pedido: el panel se
    abre en 127.0.0.1, y ese QR mandaría al celular a sí mismo.
    """
    operario = operarios.obtener(_con(request), operario_id)
    if operario is None:
        raise HTTPException(
            status_code=404, detail=f"No existe el operario {operario_id}"
        )

    url = vinculacion.armar_url(red.ip_local(), request.url.port or 8000)
    texto = vinculacion.contenido(url, operario["token_dispositivo"])

    return Response(content=vinculacion.svg(texto), media_type="image/svg+xml")
```

- [ ] **Step 14: Correr el test y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -k qr -v --rootdir .\servidor`
Expected: PASS, 3 tests

- [ ] **Step 15: Mostrar el QR en el panel**

En `servidor/panel/app.js`, reemplazar `dibujarOperario` por esta versión, que agrega la imagen del QR:

```javascript
function dibujarOperario(operario) {
  // El token es lo único con lo que se vincula un celular. Va en un campo
  // de solo lectura para poder seleccionarlo y copiarlo: son 43 caracteres
  // al azar y copiarlos a ojo es garantía de error. El QR lo evita del
  // todo, y además le pasa al celular la dirección del servidor.
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
        </div>
        <p class="ayuda">Escaneá este código desde la app para vincular el celular.</p>
      </div>
      <img class="qr" src="/api/operarios/${esc(operario.id)}/qr"
           alt="Código QR de vinculación de ${esc(operario.nombre)}">
    </li>`;
}
```

En `servidor/panel/estilos.css`, agregar antes de `.ayuda`:

```css
.operario {
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
}

.qr {
  width: 148px;
  height: 148px;
  border: 1px solid var(--borde);
  border-radius: 6px;
  background: #fff;
}
```

- [ ] **Step 16: Escribir el test del panel**

Agregar a `servidor/tests/test_panel_estatico.py`:

```python
def test_el_panel_muestra_el_qr_de_vinculacion():
    """Sin el QR hay que transcribir a mano 43 caracteres y la IP del lugar."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "/qr" in contenido
```

- [ ] **Step 17: Correr toda la suite**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS, todos

- [ ] **Step 18: Verificar el QR en el navegador**

Levantar el servidor con `.\"Iniciar servidor.bat"`, abrir `http://127.0.0.1:8000`, ir a Operarios, dar de alta uno y confirmar que aparece el QR dibujado junto al token. Cortar con Ctrl+C.

- [ ] **Step 19: Commit**

```bash
git add servidor/app/red.py servidor/app/servicios/vinculacion.py servidor/tests/test_vinculacion.py servidor/iniciar.py servidor/tests/test_red.py servidor/app/repos/operarios.py servidor/app/api/panel.py servidor/tests/test_api.py servidor/panel/ servidor/tests/test_panel_estatico.py servidor/requirements.txt
git commit -m "Agrega el QR con el que se vincula un celular

Lleva adentro la direccion del servidor y el token del operario, asi no
hay que tipear ninguno de los dos: la IP cambia en cada lugar y el token
son 43 caracteres al azar.

La direccion sale de la IP de la red local y no del pedido HTTP. El panel
se abre en 127.0.0.1, y un QR armado con eso mandaria al celular a si
mismo.

El calculo de la IP se muda a app/red.py porque ahora lo usan el arranque
y la API. Con dos implementaciones, un dia mostrarian direcciones
distintas."
```

---

### Task 2: Alta rápida desde el dispositivo

**Files:**
- Create: `servidor/app/repos/articulos.py`
- Create: `servidor/tests/test_articulos.py`
- Modify: `servidor/app/api/dispositivos.py`
- Modify: `servidor/tests/test_api.py`

**Interfaces:**
- Consumes: `sesiones.crear`, `conteos.buscar_por_codigo`, `reloj.ahora`
- Produces:
  - `articulos.crear_alta_rapida(con, sesion_id, operario_id, datos: dict) -> dict` — devuelve el artículo con los campos públicos
  - `POST /api/dispositivo/articulos` — alta rápida autenticada con `X-Token`

**Reglas que fija el spec:**
- El SKU del artículo nuevo es el código escaneado. Sin código, se genera `AR-<n>` correlativo dentro de la sesión.
- Si el código coincide con el SKU de un artículo que ya existe en la sesión, no se crea nada: se le asocia el código y se devuelve el existente.
- La respuesta no incluye `stock_sistema` ni `costo_unitario`.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_articulos.py`:

```python
import pytest

from app.repos import articulos, conteos, operarios, sesiones


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    juan = operarios.crear(con, "Juan")
    return {"sesion_id": sesion_id, "juan": juan}


def crear(con, escenario, **datos):
    completo = {
        "codigo": "999",
        "descripcion": "Caño de bronce",
        "unidad": "UN",
        "ubicacion": "P-9",
    }
    completo.update(datos)
    return articulos.crear_alta_rapida(
        con, escenario["sesion_id"], escenario["juan"]["id"], completo
    )


def test_crea_el_articulo_con_origen_alta_rapida(con, escenario):
    articulo = crear(con, escenario)

    fila = con.execute(
        "SELECT origen, creado_por, descripcion, ubicacion FROM articulo WHERE id = ?",
        (articulo["id"],),
    ).fetchone()
    assert fila["origen"] == "alta_rapida"
    assert fila["creado_por"] == "Juan"
    assert fila["descripcion"] == "Caño de bronce"
    assert fila["ubicacion"] == "P-9"


def test_el_sku_es_el_codigo_escaneado(con, escenario):
    articulo = crear(con, escenario, codigo="7790001001234")

    assert articulo["sku"] == "7790001001234"


def test_el_codigo_queda_asociado_y_el_escaneo_siguiente_lo_encuentra(con, escenario):
    """Sin esto, el mismo producto se daría de alta una vez por escaneo."""
    crear(con, escenario, codigo="7790001001234")

    encontrado = conteos.buscar_por_codigo(
        con, escenario["sesion_id"], "7790001001234"
    )
    assert encontrado["descripcion"] == "Caño de bronce"


def test_sin_codigo_genera_un_sku_correlativo(con, escenario):
    """Un producto sin etiqueta legible igual tiene que poder contarse."""
    primero = crear(con, escenario, codigo="")
    segundo = crear(con, escenario, codigo="")

    assert primero["sku"] == "AR-1"
    assert segundo["sku"] == "AR-2"


def test_un_codigo_que_ya_es_sku_devuelve_el_articulo_existente(con, escenario):
    """El maestro pudo traer un código de barras propio distinto del SKU.

    Crear un duplicado violaría la unicidad de SKU por sesión y partiría el
    conteo de un mismo producto en dos filas del tablero.
    """
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, 'A-100', 'Tornillo', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["sesion_id"],),
    )
    con.commit()

    articulo = crear(con, escenario, codigo="A-100", descripcion="Otra cosa")

    assert articulo["sku"] == "A-100"
    assert articulo["descripcion"] == "Tornillo"  # no se pisa el maestro
    cuantos = con.execute(
        "SELECT COUNT(*) AS n FROM articulo WHERE sesion_id = ?",
        (escenario["sesion_id"],),
    ).fetchone()["n"]
    assert cuantos == 1
    assert conteos.buscar_por_codigo(con, escenario["sesion_id"], "A-100") is not None


def test_el_id_orden_queda_por_encima_del_mayor_existente(con, escenario):
    """Comparte criterio con la importación: el orden define el recorrido."""
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 57, 'A-100', 'Tornillo', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["sesion_id"],),
    )
    con.commit()

    articulo = crear(con, escenario)

    assert articulo["id_orden"] == 58


def test_no_devuelve_stock_ni_costo(con, escenario):
    """Conteo a ciegas: el dato no puede llegar al dispositivo."""
    articulo = crear(con, escenario)

    assert "stock_sistema" not in articulo
    assert "costo_unitario" not in articulo


def test_rechaza_una_descripcion_vacia(con, escenario):
    with pytest.raises(ValueError, match="descripción"):
        crear(con, escenario, descripcion="   ")


def test_rechaza_una_unidad_que_no_existe(con, escenario):
    """La clave foránea lo rechazaría con un mensaje que no dice nada."""
    with pytest.raises(ValueError, match="unidad"):
        crear(con, escenario, unidad="CAJA")


def test_la_ubicacion_es_opcional(con, escenario):
    articulo = crear(con, escenario, ubicacion="")

    assert articulo["ubicacion"] is None


def test_dos_altas_del_mismo_codigo_no_duplican(con, escenario):
    """Dos operarios pueden escanear la misma etiqueta desconocida a la vez."""
    primero = crear(con, escenario, codigo="7790001001234")
    segundo = crear(con, escenario, codigo="7790001001234")

    assert primero["id"] == segundo["id"]
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_articulos.py -v --rootdir .\servidor`
Expected: FAIL con `ImportError: cannot import name 'articulos'`

- [ ] **Step 3: Implementar `servidor/app/repos/articulos.py`**

```python
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
    """AR-1, AR-2, … para los productos que no tienen etiqueta legible."""
    cuantos = con.execute(
        "SELECT COUNT(*) AS n FROM articulo WHERE sesion_id = ? AND sku LIKE 'AR-%'",
        (sesion_id,),
    ).fetchone()["n"]
    return f"AR-{cuantos + 1}"


def crear_alta_rapida(con, sesion_id, operario_id, datos):
    """Crea el artículo y le asocia el código escaneado.

    Si el código ya identifica a un artículo de la sesión —porque otro
    operario lo dio de alta hace un segundo, o porque coincide con el SKU de
    uno del maestro— devuelve ese, sin crear nada. Dos filas para el mismo
    producto partirían su conteo en dos.
    """
    codigo = (datos.get("codigo") or "").strip()
    descripcion = (datos.get("descripcion") or "").strip()
    unidad = (datos.get("unidad") or "UN").strip().upper()
    ubicacion = (datos.get("ubicacion") or "").strip() or None

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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_articulos.py -v --rootdir .\servidor`
Expected: PASS, 11 tests

- [ ] **Step 5: Escribir el test del endpoint**

Agregar al final de `servidor/tests/test_api.py`:

```python
def alta_rapida(cliente, token, **datos):
    cuerpo = {
        "codigo": "999", "descripcion": "Caño de bronce",
        "unidad": "UN", "ubicacion": "P-9",
    }
    cuerpo.update(datos)
    return cliente.post(
        "/api/dispositivo/articulos", headers={"X-Token": token}, json=cuerpo
    )


def test_alta_rapida_crea_el_articulo(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"])

    assert respuesta.status_code == 200
    assert respuesta.json()["descripcion"] == "Caño de bronce"


def test_lo_dado_de_alta_se_puede_contar_enseguida(cliente, sesion):
    """Es el punto del alta rápida: destrabar el conteo, no anotar para después."""
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    encabezados = {"X-Token": operario["token_dispositivo"]}
    alta_rapida(cliente, operario["token_dispositivo"], codigo="7790001001234")

    respuesta = cliente.post("/api/dispositivo/conteos", headers=encabezados, json={
        "conteos": [{"uuid": "u-9", "codigo": "7790001001234", "cantidad": 3000,
                     "timestamp_dispositivo": "2026-08-11T10:00:00Z"}],
    })

    assert respuesta.json()["registrados"] == 1


def test_el_alta_rapida_no_expone_stock_ni_costo(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    cuerpo = alta_rapida(cliente, operario["token_dispositivo"]).json()

    assert "stock_sistema" not in cuerpo
    assert "costo_unitario" not in cuerpo


def test_el_alta_rapida_sin_token_devuelve_401(cliente, sesion):
    assert alta_rapida(cliente, "inventado").status_code == 401


def test_el_alta_rapida_con_datos_invalidos_devuelve_400(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"], descripcion="")

    assert respuesta.status_code == 400
    assert "descripción" in respuesta.json()["detail"]


def test_el_alta_rapida_aparece_en_el_tablero(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    alta_rapida(cliente, operario["token_dispositivo"])

    filas = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"]

    nuevo = next(f for f in filas if f["descripcion"] == "Caño de bronce")
    assert nuevo["origen"] == "alta_rapida"
```

- [ ] **Step 6: Correr el test y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -k alta_rapida -v --rootdir .\servidor`
Expected: FAIL con 404 (la ruta no existe)

- [ ] **Step 7: Agregar el endpoint en `servidor/app/api/dispositivos.py`**

Agregar `HTTPException` ya está importado y sumar `articulos` a los repos:

```python
from app.repos import articulos, conteos, operarios, sesiones
```

Y el endpoint, después de `descargar_maestro`:

```python
@router.post("/articulos")
async def dar_de_alta(request: Request, x_token: str = Header(default="")):
    """Alta rápida de un código que no está en el maestro.

    Necesita red, a diferencia del conteo: el identificador lo asigna el
    servidor. La app avisa cuando no hay señal en vez de guardar un alta a
    ciegas que después podría chocar con otra igual.
    """
    con, operario, sesion = _contexto(request, x_token)
    cuerpo = await request.json()

    try:
        return articulos.crear_alta_rapida(
            con, sesion["id"], operario["id"], cuerpo
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
```

- [ ] **Step 8: Correr el test y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -k alta_rapida -v --rootdir .\servidor`
Expected: PASS, 6 tests

- [ ] **Step 9: Correr toda la suite**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS, todos

- [ ] **Step 10: Commit**

```bash
git add servidor/app/repos/articulos.py servidor/tests/test_articulos.py servidor/app/api/dispositivos.py servidor/tests/test_api.py
git commit -m "Permite dar de alta desde el celular un codigo desconocido

Sin esto, el operario que encuentra mercaderia con una etiqueta que el
maestro no tiene se queda sin poder registrarla, que es justamente uno de
los hallazgos que justifican el inventario.

Un codigo que ya identifica a un articulo de la sesion no crea nada:
devuelve el existente. Dos operarios pueden escanear la misma etiqueta
desconocida a la vez, y dos filas para el mismo producto partirian su
conteo en dos."
```

---

### Task 3: Entrega del APK desde el panel

**Files:**
- Modify: `servidor/app/api/panel.py`
- Modify: `servidor/tests/test_api.py`
- Modify: `servidor/panel/index.html`, `servidor/panel/app.js`, `servidor/panel/estilos.css`
- Modify: `servidor/tests/test_panel_estatico.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `red.ip_local`, `vinculacion.armar_url`, `vinculacion.svg` (Task 1)
- Produces:
  - `GET /app.apk` — el APK, o 404 si no está
  - `GET /api/instalacion` — `{"disponible": bool, "url": str}`
  - `GET /api/instalacion/qr` — SVG que apunta a `/app.apk`

**Por qué:** en el depósito no hay cable ni tienda de aplicaciones. El celular escanea un QR del panel, baja el APK y lo instala. Si el APK no está presente, el panel no muestra nada en vez de ofrecer una descarga rota.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `servidor/tests/test_api.py`:

```python
APK_FALSO = b"PK\x03\x04 esto hace de APK en los tests"


def test_sin_apk_la_descarga_devuelve_404(cliente):
    assert cliente.get("/app.apk").status_code == 404


def test_sin_apk_la_instalacion_se_informa_como_no_disponible(cliente):
    """El panel no puede ofrecer una descarga que va a fallar."""
    respuesta = cliente.get("/api/instalacion")

    assert respuesta.status_code == 200
    assert respuesta.json()["disponible"] is False


def test_con_apk_presente_se_descarga(cliente, tmp_path, monkeypatch):
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)

    respuesta = cliente.get("/app.apk")

    assert respuesta.status_code == 200
    assert respuesta.content == APK_FALSO
    assert "android.package-archive" in respuesta.headers["content-type"]


def test_con_apk_presente_la_instalacion_informa_la_direccion_de_red(
    cliente, tmp_path, monkeypatch
):
    """El QR lo escanea un celular: 127.0.0.1 lo mandaría a sí mismo."""
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["disponible"] is True
    assert cuerpo["url"].endswith("/app.apk")
    assert "127.0.0.1" not in cuerpo["url"]


def test_el_qr_de_instalacion_es_svg(cliente, tmp_path, monkeypatch):
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)

    respuesta = cliente.get("/api/instalacion/qr")

    assert respuesta.status_code == 200
    assert "image/svg+xml" in respuesta.headers["content-type"]


def test_el_qr_de_instalacion_sin_apk_devuelve_404(cliente):
    assert cliente.get("/api/instalacion/qr").status_code == 404
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -k "apk or instalacion" -v --rootdir .\servidor`
Expected: FAIL — las rutas no existen (los dos tests de 404 pasan por casualidad; los otros cuatro fallan)

- [ ] **Step 3: Agregar las rutas en `servidor/app/api/panel.py`**

Agregar el import de `Path` y `FileResponse` arriba:

```python
from pathlib import Path

from fastapi.responses import FileResponse, Response
```

Y después de las constantes del módulo:

```python
# El APK se deja junto al servidor cuando hay una versión compilada. No está
# en git: es un binario que se regenera, y el repositorio no es su lugar.
RUTA_APK = Path(__file__).parent.parent.parent / "app.apk"

MEDIA_APK = "application/vnd.android.package-archive"
```

Las tres rutas, al final del archivo:

```python
def _url_de_instalacion(request):
    base = vinculacion.armar_url(red.ip_local(), request.url.port or 8000)
    return f"{base}/app.apk"


@router.get("/instalacion")
def estado_de_instalacion(request: Request):
    """Si hay APK para instalar y desde qué dirección se baja."""
    if not RUTA_APK.exists():
        return {"disponible": False, "url": ""}
    return {"disponible": True, "url": _url_de_instalacion(request)}


@router.get("/instalacion/qr")
def qr_de_instalacion(request: Request):
    if not RUTA_APK.exists():
        raise HTTPException(status_code=404, detail="Todavía no hay una app para instalar")

    return Response(
        content=vinculacion.svg(_url_de_instalacion(request)),
        media_type="image/svg+xml",
    )
```

La descarga en sí **no lleva el prefijo `/api`**, porque la dirección la tipea o escanea una persona. Va en `main.py`, no en este router: ver el paso siguiente.

- [ ] **Step 4: Agregar la descarga en `servidor/app/main.py`**

La ruta se registra antes del montaje de archivos estáticos, que es lo que atrapa todo lo demás. Agregar el import y la ruta dentro de `crear_app`, justo después de `app.include_router(dispositivos.router)`:

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api import dispositivos, panel
```

```python
    @app.get("/app.apk")
    def descargar_apk():
        """La app para instalar en el celular.

        Sin prefijo /api porque esta dirección la escanea una persona desde
        un QR: cuanto más corta, más chico y más legible el código.
        """
        if not panel.RUTA_APK.exists():
            raise HTTPException(
                status_code=404, detail="Todavía no hay una app para instalar"
            )
        return FileResponse(
            panel.RUTA_APK,
            media_type=panel.MEDIA_APK,
            filename="control-de-stock.apk",
        )
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -k "apk or instalacion" -v --rootdir .\servidor`
Expected: PASS, 6 tests

- [ ] **Step 6: Ignorar el APK en git**

Agregar a `.gitignore`, en la sección de Android (ya existe `*.apk`, así que verificar que esté; si está, no tocar nada). Confirmar con:

Run: `git check-ignore -v servidor/app.apk`
Expected: la línea `*.apk` del `.gitignore`

- [ ] **Step 7: Mostrar la instalación en el panel**

En `servidor/panel/index.html`, dentro de `<section id="vista-operarios">`, antes del `<h2>Operarios</h2>`:

```html
      <div id="instalacion" class="instalacion oculta">
        <div>
          <h2>Instalar la app en un celular</h2>
          <p class="ayuda">
            Escaneá este código con la cámara del celular para descargar la
            app. La primera vez, Android pide permiso para instalar desde
            esta fuente.
          </p>
          <p class="ayuda"><a id="enlace-apk" href="/app.apk">Descargar el APK</a></p>
        </div>
        <img class="qr" src="/api/instalacion/qr" alt="Código QR para descargar la app">
      </div>
```

En `servidor/panel/app.js`, agregar la función y llamarla desde `cargarOperarios`:

```javascript
async function cargarInstalacion() {
  const estado = await pedir("/api/instalacion");
  $("#instalacion").classList.toggle("oculta", !estado.disponible);
}
```

En `cargarOperarios`, agregar como última línea del cuerpo:

```javascript
  await cargarInstalacion();
```

En `servidor/panel/estilos.css`, junto a `.operario`:

```css
.instalacion {
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  background: var(--panel);
  border: 1px solid var(--borde);
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 1.25rem;
}
```

- [ ] **Step 8: Escribir el test del panel**

Agregar a `servidor/tests/test_panel_estatico.py`:

```python
def test_el_panel_esconde_la_instalacion_si_no_hay_apk():
    """Ofrecer una descarga que devuelve 404 es peor que no ofrecer nada."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "/api/instalacion" in contenido
    assert "estado.disponible" in contenido
```

- [ ] **Step 9: Correr toda la suite**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS, todos

- [ ] **Step 10: Verificar a mano el circuito de instalación**

Copiar cualquier archivo a `servidor/app.apk` para simular una versión compilada, levantar el servidor y abrir `http://127.0.0.1:8000` → Operarios. Tiene que aparecer el bloque de instalación con su QR. Borrar `servidor/app.apk` y recargar: el bloque desaparece.

- [ ] **Step 11: Commit**

```bash
git add servidor/app/api/panel.py servidor/app/main.py servidor/tests/test_api.py servidor/panel/ servidor/tests/test_panel_estatico.py
git commit -m "Entrega el APK desde el panel con un QR

En el deposito no hay cable ni tienda de aplicaciones: el celular escanea
el codigo del panel, baja la app y la instala.

Si el APK no esta presente el panel no muestra nada, en vez de ofrecer una
descarga que devuelve 404.

La direccion de descarga no lleva el prefijo /api porque la escanea una
persona: cuanto mas corta, mas chico y mas legible queda el QR."
```

---

## Verificación final del plan

```bash
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Todos los tests en verde. Después, prueba manual del circuito completo:

1. Levantar con `.\"Iniciar servidor.bat"`.
2. Crear una sesión e importar un maestro.
3. Dar de alta un operario y confirmar que aparece su QR.
4. Escanear ese QR con la cámara del celular (cualquier lector sirve para esta verificación): tiene que mostrar un JSON con la dirección del servidor y el token.
5. Con `curl` o PowerShell, dar de alta un artículo por `POST /api/dispositivo/articulos` y verificar que aparece en el tablero marcado como alta rápida, y que se le puede cargar un conteo enseguida.

Con esto el servidor queda listo para que la app se vincule, descargue el maestro, cuente y dé de alta lo que no está. El plan siguiente construye la app.
