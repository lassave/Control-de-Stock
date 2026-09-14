# Identificarse sin QR, contar tocando el SKU y AGREGADO — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sumar a la app del celular tres capacidades — identificarse sin escanear el QR (para un celular ya vinculado), contar tocando el SKU (tarjeta de Mi Lista o buscando por texto), y una etiqueta «AGREGADO» que distinga en el celular y en el panel los artículos que nacieron de una alta rápida.

**Architecture:** Server (FastAPI/SQLite) primero — dos endpoints nuevos bajo `/api/dispositivo` y un campo (`origen`) sumado a uno que ya existe, siguiendo el mismo patrón de `_contexto`/repos que ya usa `dispositivos.py`. Después el contrato compartido (`celular/contrato/*.json`) que fija la forma entre los dos lados. Después el celular de adentro hacia afuera: `nucleo` (DTOs, lógica pura) → `app/datos` (Room) → `app` (Contador, Vinculador, ListaDeTrabajo) → `app/ui` (pantallas) → `MainActivity` (cableado). El panel es un cambio aislado de una línea en `app.js`.

**Tech Stack:** Python 3 + FastAPI + SQLite crudo (servidor); Kotlin + Jetpack Compose + Room + OkHttp + kotlinx.serialization, dos módulos Gradle (`nucleo` puro, `app` con Android) (celular); HTML/CSS/JS sin dependencias (panel).

**Spec:** `docs/superpowers/specs/2026-09-14-identificarse-contar-tocando-y-agregado-design.md`

## Global Constraints

- El intérprete de Python de este repo es `.\servidor\.venv\Scripts\python.exe` por ruta completa — nunca `python` del PATH (es el acceso directo de la Microsoft Store).
- Gradle es `C:\Gradle\gradle-8.7\bin\gradle.bat`, siempre con `--no-daemon` en estos comandos.
- `stock_sistema` y `costo_unitario` nunca salen por ningún endpoint de `/api/dispositivo/*`.
- Nada externo en el navegador del panel (sin CDN, sin fuentes remotas).
- Todo dato del servidor se escapa antes de ir al HTML del panel (usar `esc()`, ya presente en `app.js`).
- Fechas ISO 8601 UTC como texto, siempre vía `app/reloj.py` — esta rama no agrega ninguna fecha nueva.
- Nada se edita ni se borra — esta rama tampoco agrega ningún update/delete de datos de negocio.
- Todo texto para el operario o para los mensajes de error va en castellano rioplatense, sin jerga técnica.
- TDD sin excepciones: test que falla, implementación, test que pasa, commit. Cada tarea termina con un commit.
- Mensajes de commit en castellano, en presente, describiendo el efecto.

---

## File Structure

**Servidor:**
- Modificar `servidor/app/repos/operarios.py` — dos funciones nuevas: `listar_para_identificar`, `para_identificar`.
- Modificar `servidor/app/api/dispositivos.py` — dos endpoints nuevos (`GET /operarios`, `POST /identificar`) y una columna más en el `SELECT` de `/maestro`.
- Modificar `servidor/tests/test_operarios.py`, `servidor/tests/test_api.py`, `servidor/tests/test_contrato.py`.
- Modificar `celular/contrato/capturar.py` y los archivos `celular/contrato/maestro.json`, `celular/contrato/operarios.json` (nuevo), `celular/contrato/identificacion.json` (nuevo).
- Modificar `servidor/panel/app.js` — una línea en `dibujarFila`.

**Celular — `nucleo` (Kotlin puro):**
- Modificar `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ContratoApi.kt` — DTOs nuevos y `origen` en `ArticuloRemoto`.
- Modificar `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ListaAsignada.kt` — `origen` en `ArticuloParaLista`, `articuloId`/`agregado` en `RenglonAsignado`.
- Modificar `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ContratoApiTest.kt`, `ListaAsignadaTest.kt`.

**Celular — `app` (Android):**
- Modificar `celular/app/src/main/kotlin/com/controldestock/red/ClienteServidor.kt` — `operarios()`, `identificar()`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/datos/Entidades.kt` — `origen` en `ArticuloEntidad`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt` — versión 6, `MIGRACION_5_6`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/Contador.kt` — `buscarPorId`, `buscarTexto`, `origen` en `darDeAlta`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/Vinculador.kt` — `identificar()`, mapeo de `origen`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/ListaDeTrabajo.kt` — pasa `origen`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt` — parámetro `buscando`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/ui/Tema.kt` — color `Violeta`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/ui/PantallaMiLista.kt` — tarjeta tocable, etiqueta AGREGADO, encabezado con operario.
- Modificar `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt` — botón «Buscar».
- Crear `celular/app/src/main/kotlin/com/controldestock/ui/DialogoIdentificarse.kt`.
- Crear `celular/app/src/main/kotlin/com/controldestock/ui/DialogoBuscarProducto.kt`.
- Modificar `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt` — cableado final.
- Tests correspondientes en `celular/app/src/test/kotlin/...` y `celular/app/src/testDebug/kotlin/...`.

---

## Task 1: Repositorio de operarios — identificarse sin token

**Files:**
- Modify: `servidor/app/repos/operarios.py`
- Test: `servidor/tests/test_operarios.py`

**Interfaces:**
- Produces: `listar_para_identificar(con) -> list[dict]` — cada dict `{"id": int, "nombre": str, "tiene_pin": bool}`, solo operarios activos, ordenados por nombre.
- Produces: `para_identificar(con, nombre) -> dict | None` — dict con `id, nombre, pin, token_dispositivo` (el único lugar que sí trae el PIN), o `None` si no existe o está inactivo.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `servidor/tests/test_operarios.py`:

```python
def test_listar_para_identificar_dice_si_tiene_pin(con):
    operarios.crear(con, "Juan")
    operarios.crear(con, "Ana", pin="1234")

    listado = {o["nombre"]: o["tiene_pin"] for o in operarios.listar_para_identificar(con)}

    assert listado == {"Juan": False, "Ana": True}


def test_listar_para_identificar_no_expone_ni_el_pin_ni_el_token(con):
    operarios.crear(con, "Ana", pin="1234")

    campos = set(operarios.listar_para_identificar(con)[0])

    assert campos == {"id", "nombre", "tiene_pin"}


def test_listar_para_identificar_ordena_por_nombre(con):
    operarios.crear(con, "Zulema")
    operarios.crear(con, "Ana")

    nombres = [o["nombre"] for o in operarios.listar_para_identificar(con)]

    assert nombres == ["Ana", "Zulema"]


def test_listar_para_identificar_ignora_desactivados(con):
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    assert operarios.listar_para_identificar(con) == []


def test_para_identificar_encuentra_por_nombre_y_trae_el_pin(con):
    juan = operarios.crear(con, "Juan", pin="1234")

    encontrado = operarios.para_identificar(con, "Juan")

    assert encontrado["id"] == juan["id"]
    assert encontrado["pin"] == "1234"
    assert encontrado["token_dispositivo"] == juan["token_dispositivo"]


def test_para_identificar_devuelve_none_si_no_existe(con):
    assert operarios.para_identificar(con, "Nadie") is None


def test_para_identificar_ignora_desactivados(con):
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    assert operarios.para_identificar(con, "Juan") is None
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_operarios.py -q --rootdir .\servidor`
Expected: FAIL con `AttributeError: module 'app.repos.operarios' has no attribute 'listar_para_identificar'`.

- [ ] **Step 3: Implementar**

Agregar al final de `servidor/app/repos/operarios.py`:

```python
def listar_para_identificar(con):
    """Nombres activos para elegir al identificarse sin QR.

    Nunca el PIN ni el token: esta lista arma un botón por nombre en el
    celular, no vincula a nadie por sí sola.
    """
    filas = con.execute(
        "SELECT id, nombre, pin FROM operario WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    return [
        {"id": fila["id"], "nombre": fila["nombre"], "tiene_pin": bool(fila["pin"])}
        for fila in filas
    ]


def para_identificar(con, nombre):
    """El operario por nombre, con su PIN y su token.

    A diferencia de `listar_para_identificar` y `por_token`, esta sí trae el
    PIN: es la única consulta que lo necesita, para compararlo contra el que
    mandó el celular. No sale de acá hacia ninguna respuesta HTTP.
    """
    fila = con.execute(
        "SELECT id, nombre, pin, token_dispositivo FROM operario "
        "WHERE nombre = ? AND activo = 1",
        (nombre,),
    ).fetchone()
    return dict(fila) if fila else None
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_operarios.py -q --rootdir .\servidor`
Expected: PASS, todos los tests del archivo.

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/operarios.py servidor/tests/test_operarios.py
git commit -m "Agrega al repositorio de operarios la consulta para identificarse sin QR"
```

---

## Task 2: Endpoints — listar operarios e identificarse

**Files:**
- Modify: `servidor/app/api/dispositivos.py`
- Test: `servidor/tests/test_api.py`

**Interfaces:**
- Consumes: `operarios.listar_para_identificar(con)`, `operarios.para_identificar(con, nombre)` (Task 1); `proyectos.pasada_activa_de_operario(con, proyecto_id, operario_id)` (ya existente).
- Produces: `GET /api/dispositivo/operarios` → `{"operarios": [...]}`. `POST /api/dispositivo/identificar` → `{"operario": {...}, "proyecto": {...}, "pasada": {...}, "token": str}`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `servidor/tests/test_api.py`:

```python
def test_listar_operarios_para_identificar(cliente, proyecto):
    cliente.post("/api/operarios", json={"nombre": "Juan"})
    cliente.post("/api/operarios", json={"nombre": "Ana", "pin": "1234"})
    token = cliente.post("/api/operarios", json={"nombre": "Pedro"}).json()["token_dispositivo"]

    respuesta = cliente.get("/api/dispositivo/operarios", headers={"X-Token": token})

    assert respuesta.status_code == 200
    listado = {o["nombre"]: o["tiene_pin"] for o in respuesta.json()["operarios"]}
    assert listado == {"Juan": False, "Ana": True, "Pedro": False}


def test_listar_operarios_con_token_invalido_devuelve_401(cliente, proyecto):
    respuesta = cliente.get("/api/dispositivo/operarios", headers={"X-Token": "inventado"})

    assert respuesta.status_code == 401


def test_identificarse_sin_pin(cliente, proyecto):
    juan = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    ana = cliente.post("/api/operarios", json={"nombre": "Ana"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": juan["token_dispositivo"]},
        json={"nombre": "Ana"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["operario"]["nombre"] == "Ana"
    assert cuerpo["proyecto"]["id"] == proyecto["id"]
    assert cuerpo["token"] == ana["token_dispositivo"]


def test_identificarse_con_pin_correcto(cliente, proyecto):
    juan = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post("/api/operarios", json={"nombre": "Ana", "pin": "1234"})

    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": juan["token_dispositivo"]},
        json={"nombre": "Ana", "pin": "1234"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["operario"]["nombre"] == "Ana"


def test_identificarse_con_pin_incorrecto_devuelve_400(cliente, proyecto):
    juan = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post("/api/operarios", json={"nombre": "Ana", "pin": "1234"})

    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": juan["token_dispositivo"]},
        json={"nombre": "Ana", "pin": "0000"},
    )

    assert respuesta.status_code == 400
    assert "PIN no coincide" in respuesta.json()["detail"]


def test_identificarse_sin_el_pin_que_hace_falta_devuelve_400(cliente, proyecto):
    juan = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post("/api/operarios", json={"nombre": "Ana", "pin": "1234"})

    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": juan["token_dispositivo"]},
        json={"nombre": "Ana"},
    )

    assert respuesta.status_code == 400
    assert "necesita un PIN" in respuesta.json()["detail"]


def test_identificarse_con_nombre_inexistente_devuelve_400(cliente, proyecto):
    juan = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": juan["token_dispositivo"]},
        json={"nombre": "Nadie"},
    )

    assert respuesta.status_code == 400
    assert "no existe" in respuesta.json()["detail"]


def test_identificarse_con_token_invalido_devuelve_401(cliente, proyecto):
    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": "inventado"},
        json={"nombre": "Juan"},
    )

    assert respuesta.status_code == 401


def test_identificarse_sin_proyecto_abierto_devuelve_409(cliente, proyecto):
    juan = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post(f"/api/proyectos/{proyecto['id']}/cerrar")

    respuesta = cliente.post(
        "/api/dispositivo/identificar",
        headers={"X-Token": juan["token_dispositivo"]},
        json={"nombre": "Juan"},
    )

    assert respuesta.status_code == 409
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -q -k "identificarse or listar_operarios" --rootdir .\servidor`
Expected: FAIL con `404 Not Found` en los nuevos tests (las rutas todavía no existen).

- [ ] **Step 3: Implementar**

En `servidor/app/api/dispositivos.py`, agregar después de `vincular` (después de la función, antes de `descargar_maestro`):

```python
@router.get("/operarios")
def listar_operarios(request: Request, x_token: str = Header(default="")):
    con, _, _ = _contexto(request, x_token)
    return {"operarios": operarios.listar_para_identificar(con)}


@router.post("/identificar")
async def identificar(request: Request, x_token: str = Header(default="")):
    """Identificarse en un celular ya vinculado, sin volver a escanear el QR.

    El `X-Token` de acá adentro no es el de la persona que se está por
    identificar: es el de quien ya tenía el celular, y solo prueba que es un
    dispositivo que ya pasó por el QR alguna vez.
    """
    con, _, proyecto = _contexto(request, x_token)
    cuerpo = await _cuerpo_json(request)

    nombre = (cuerpo.get("nombre") or "").strip()
    elegido = operarios.para_identificar(con, nombre)
    if elegido is None:
        raise HTTPException(status_code=400, detail="Ese operario no existe")

    pin_guardado = elegido["pin"]
    if pin_guardado:
        pin_recibido = cuerpo.get("pin")
        if not pin_recibido:
            raise HTTPException(status_code=400, detail="Ese operario necesita un PIN")
        if pin_recibido != pin_guardado:
            raise HTTPException(status_code=400, detail="El PIN no coincide")

    try:
        pasada = proyectos.pasada_activa_de_operario(con, proyecto["id"], elegido["id"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {
        "operario": {"id": elegido["id"], "nombre": elegido["nombre"]},
        "proyecto": {"id": proyecto["id"], "nombre": proyecto["nombre"]},
        "pasada": pasada,
        "token": elegido["token_dispositivo"],
    }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -q --rootdir .\servidor`
Expected: PASS, todo el archivo (incluidos los tests viejos: sin querer no se rompió nada).

- [ ] **Step 5: Commit**

```bash
git add servidor/app/api/dispositivos.py servidor/tests/test_api.py
git commit -m "Agrega los endpoints para identificarse sin QR en un celular ya vinculado"
```

---

## Task 3: Exponer `origen` en el maestro del dispositivo

**Files:**
- Modify: `servidor/app/api/dispositivos.py`
- Test: `servidor/tests/test_api.py`

**Interfaces:**
- Produces: cada artículo de `GET /api/dispositivo/maestro` trae ahora `"origen": "importado" | "alta_rapida"`.

- [ ] **Step 1: Escribir el test que falla**

Agregar a `servidor/tests/test_api.py`:

```python
def test_maestro_expone_el_origen_de_cada_articulo(cliente, proyecto):
    importar(cliente, proyecto["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(
        "/api/dispositivo/maestro", headers={"X-Token": operario["token_dispositivo"]}
    )

    articulos = respuesta.json()["articulos"]
    assert len(articulos) == 2
    assert all(a["origen"] == "importado" for a in articulos)
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -q -k origen_de_cada_articulo --rootdir .\servidor`
Expected: FAIL con `KeyError: 'origen'`.

- [ ] **Step 3: Implementar**

En `servidor/app/api/dispositivos.py`, dentro de `descargar_maestro`, cambiar el `SELECT`:

```python
    filas_articulos = con.execute(
        """
        SELECT a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion,
               a.grupo, a.ubicacion, a.unidad, a.origen
        FROM articulo a
        WHERE a.proyecto_id = ? AND a.fusionado_en IS NULL
        ORDER BY a.id_orden
        """,
        (proyecto["id"],),
    ).fetchall()
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -q -k origen_de_cada_articulo --rootdir .\servidor`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add servidor/app/api/dispositivos.py servidor/tests/test_api.py
git commit -m "Suma el origen de cada articulo a lo que baja el maestro del dispositivo"
```

---

## Task 4: Actualizar el contrato compartido

**Files:**
- Modify: `servidor/tests/test_contrato.py`
- Modify: `celular/contrato/capturar.py`
- Modify: `celular/contrato/maestro.json`
- Create: `celular/contrato/operarios.json`
- Create: `celular/contrato/identificacion.json`

**Interfaces:**
- Consumes: los endpoints de las Tasks 1-3.
- Produces: los tres archivos de contrato quedan al día para que `celular/nucleo/.../ContratoApiTest.kt` (Task 6) tenga contra qué parsear.

- [ ] **Step 1: Escribir los tests que fallan**

En `servidor/tests/test_contrato.py`, cambiar `ARCHIVOS`:

```python
ARCHIVOS = [
    "vinculacion", "maestro", "conteos-respuesta", "alta-rapida",
    "mis-ubicaciones", "operarios", "identificacion",
]
```

En la función `vivo`, después de la línea `respuestas["vinculacion"] = ...` y antes de `respuestas["maestro"] = ...`, agregar:

```python
        respuestas["operarios"] = c.get(
            "/api/dispositivo/operarios", headers=cab
        ).json()
        respuestas["identificacion"] = c.post(
            "/api/dispositivo/identificar", headers=cab, json={"nombre": "Contrato"},
        ).json()
```

Al final del archivo, agregar:

```python
def test_operarios_trae_id_nombre_y_tiene_pin():
    datos = leer("operarios")

    assert set(datos) == {"operarios"}
    assert set(datos["operarios"][0]) == {"id", "nombre", "tiene_pin"}


def test_identificacion_trae_lo_mismo_que_la_vinculacion_mas_el_token():
    datos = leer("identificacion")

    assert set(datos) == {"operario", "proyecto", "pasada", "token"}
    assert set(datos["operario"]) == {"id", "nombre"}
    assert set(datos["proyecto"]) == {"id", "nombre"}
```

Y actualizar la aserción existente para que incluya `origen`:

```python
def test_el_maestro_trae_articulos_codigos_y_unidades():
    datos = leer("maestro")

    assert set(datos) == {"proyecto_id", "articulos", "codigos", "unidades"}
    assert set(datos["articulos"][0]) == {
        "id", "id_orden", "tipo", "material", "sku", "descripcion",
        "grupo", "ubicacion", "unidad", "origen",
    }
    assert set(datos["codigos"][0]) == {"codigo", "articulo_id"}
    assert set(datos["unidades"][0]) == {"codigo", "nombre", "admite_decimales"}
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_contrato.py -q --rootdir .\servidor`
Expected: FAIL — `test_los_archivos_del_contrato_existen` (faltan `operarios.json`/`identificacion.json`), `test_operarios_trae_id_nombre_y_tiene_pin` y `test_identificacion_...` (`FileNotFoundError`), `test_el_maestro_trae_articulos_codigos_y_unidades` (falta `origen` en el archivo viejo), y `test_el_servidor_sigue_cumpliendo_el_contrato[maestro]` (el servidor ahora manda `origen` y el archivo viejo no lo tiene).

- [ ] **Step 3: Escribir los archivos de contrato**

Editar `celular/contrato/maestro.json`: agregar `"origen": "importado"` a cada uno de los dos artículos (después de `"unidad": "UN"`, con coma):

```json
{
  "proyecto_id": 1,
  "articulos": [
    {
      "id": 1,
      "id_orden": 1,
      "tipo": null,
      "material": null,
      "sku": "7790001001234",
      "descripcion": "Fideos guisero 500g",
      "grupo": null,
      "ubicacion": "P-1",
      "unidad": "UN",
      "origen": "importado"
    },
    {
      "id": 2,
      "id_orden": 2,
      "tipo": null,
      "material": null,
      "sku": "7790002005678",
      "descripcion": "Aceite girasol 900ml",
      "grupo": null,
      "ubicacion": "P-2",
      "unidad": "UN",
      "origen": "importado"
    }
  ],
  "codigos": [
    { "codigo": "7790001001234", "articulo_id": 1 },
    { "codigo": "7790002005678", "articulo_id": 2 }
  ],
  "unidades": [
    { "codigo": "UN", "nombre": "Unidad", "admite_decimales": 0 },
    { "codigo": "CJ", "nombre": "Caja", "admite_decimales": 0 },
    { "codigo": "PACK", "nombre": "Pack", "admite_decimales": 0 },
    { "codigo": "KG", "nombre": "Kilogramo", "admite_decimales": 1 },
    { "codigo": "GR", "nombre": "Gramo", "admite_decimales": 1 },
    { "codigo": "LT", "nombre": "Litro", "admite_decimales": 1 },
    { "codigo": "ML", "nombre": "Mililitro", "admite_decimales": 1 },
    { "codigo": "MT", "nombre": "Metro", "admite_decimales": 1 }
  ]
}
```

Crear `celular/contrato/operarios.json`:

```json
{
  "operarios": [
    {
      "id": 1,
      "nombre": "Contrato",
      "tiene_pin": false
    }
  ]
}
```

Crear `celular/contrato/identificacion.json` (la misma `pasada` que ya usa `vinculacion.json`, más `token`):

```json
{
  "operario": {
    "id": 1,
    "nombre": "Contrato"
  },
  "proyecto": {
    "id": 1,
    "nombre": "Contrato"
  },
  "pasada": {
    "id": 1,
    "proyecto_id": 1,
    "numero": 1,
    "estado": "abierta",
    "fecha_apertura": "2026-08-12T01:39:51Z",
    "fecha_cierre": null,
    "abierta_por": null,
    "cerrada_por": null,
    "etiqueta": "Conteo 1"
  },
  "token": "token-de-contrato-para-identificarse"
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_contrato.py -q --rootdir .\servidor`
Expected: PASS, todo el archivo.

- [ ] **Step 5: Mantener `capturar.py` al día**

En `celular/contrato/capturar.py`, dentro de `main()`, después de la línea `guardar("vinculacion", ...)` y antes de `guardar("maestro", ...)`, agregar:

```python
        guardar("operarios", c.get("/api/dispositivo/operarios", headers=cab).json())
        guardar("identificacion", c.post(
            "/api/dispositivo/identificar", headers=cab, json={"nombre": "Contrato"},
        ).json())
```

Este script no se ejecuta en este task (necesita un servidor real corriendo contra una base vacía); queda al día para la próxima vez que alguien recapture el contrato a mano.

- [ ] **Step 6: Commit**

```bash
git add servidor/tests/test_contrato.py celular/contrato/capturar.py celular/contrato/maestro.json celular/contrato/operarios.json celular/contrato/identificacion.json
git commit -m "Suma operarios e identificacion al contrato, y origen al maestro"
```

---

## Task 5: Panel — etiqueta AGREGADO en el tablero

**Files:**
- Modify: `servidor/panel/app.js`

**Interfaces:**
- Consumes: `fila.origen` (ya lo devuelve `servidor/app/servicios/tablero.py`, sin cambios en este task).

- [ ] **Step 1: Verificar el punto de partida**

Los tests del panel ya existentes (nada externo en el navegador, todo dato escapado) no cubren esta etiqueta puntual porque todavía no existe. Este cambio se verifica en el navegador (Step 3), no con un test automático nuevo: `dibujarFila` es una función de armado de HTML sin lógica de negocio propia, del mismo tamaño que las otras marcas (`marca`, `asignadoA`, `fueraDeSector`) que tampoco tienen test unitario aparte.

- [ ] **Step 2: Implementar**

En `servidor/panel/app.js`, dentro de `dibujarFila`, agregar antes del `return`:

```javascript
  const agregado = fila.origen === "alta_rapida"
    ? `<span class="marca">AGREGADO</span>`
    : "";
```

Y cambiar la celda del SKU para incluirla:

```javascript
      <td class="sku">${esc(fila.sku)} ${agregado}</td>
```

- [ ] **Step 3: Verificar en el navegador**

Levantar el servidor (`.\"Iniciar servidor.bat"`), crear un proyecto, importar un maestro, vincular un celular de prueba (o usar `celular/contrato/capturar.py` contra ese servidor) y dar de alta un artículo por `/api/dispositivo/articulos`. Abrir el panel, pestaña Tablero, y confirmar que esa fila muestra «AGREGADO» al lado del SKU y las demás no.

- [ ] **Step 4: Commit**

```bash
git add servidor/panel/app.js
git commit -m "Marca en el tablero los articulos que nacieron de una alta rapida"
```

---

## Task 6: Celular nucleo — DTOs de identificarse y `origen` en el maestro

**Files:**
- Modify: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ContratoApi.kt`
- Test: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ContratoApiTest.kt`

**Interfaces:**
- Produces: `data class OperarioParaIdentificar(id: Int, nombre: String, tienePin: Boolean)`, `data class RespuestaOperarios(operarios: List<OperarioParaIdentificar>)`, `data class RespuestaIdentificacion(operario: OperarioRemoto, proyecto: ProyectoRemoto, pasada: PasadaRemota, token: String)`. `ArticuloRemoto` gana `origen: String = "importado"`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ContratoApiTest.kt`:

```kotlin
    @Test
    fun `el maestro trae el origen de cada articulo`() {
        val respuesta = json.decodeFromString<RespuestaMaestro>(leer("maestro"))

        assertTrue(respuesta.articulos.all { it.origen == "importado" })
    }

    @Test
    fun `sin origen en la respuesta se asume importado`() {
        // Tolerancia hacia un servidor viejo que todavía no manda el campo:
        // un JSON armado a mano y no el archivo de contrato, para no
        // depender de su formato exacto.
        val sinOrigen = """
            {"proyecto_id":1,"articulos":[{"id":1,"id_orden":1,"sku":"A-1",
            "descripcion":"Fideos","unidad":"UN"}],"codigos":[],"unidades":[]}
        """.trimIndent()

        val respuesta = json.decodeFromString<RespuestaMaestro>(sinOrigen)

        assertEquals("importado", respuesta.articulos[0].origen)
    }

    @Test
    fun `parsea la lista de operarios para identificarse`() {
        val respuesta = json.decodeFromString<RespuestaOperarios>(leer("operarios"))

        assertEquals(1, respuesta.operarios.size)
        assertEquals("Contrato", respuesta.operarios[0].nombre)
        assertFalse(respuesta.operarios[0].tienePin)
    }

    @Test
    fun `parsea la identificacion y trae el token`() {
        val respuesta = json.decodeFromString<RespuestaIdentificacion>(leer("identificacion"))

        assertEquals("Contrato", respuesta.operario.nombre)
        assertTrue(respuesta.token.isNotBlank())
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL — no compila (`OperarioParaIdentificar`, `RespuestaOperarios`, `RespuestaIdentificacion` y `ArticuloRemoto.origen` no existen todavía).

- [ ] **Step 3: Implementar**

En `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ContratoApi.kt`, cambiar `ArticuloRemoto`:

```kotlin
@Serializable
data class ArticuloRemoto(
    val id: Int,
    @SerialName("id_orden") val idOrden: Int,
    val tipo: String? = null,
    val material: String? = null,
    val sku: String,
    val descripcion: String,
    val grupo: String? = null,
    val ubicacion: String? = null,
    val unidad: String,
    // Por defecto «importado»: un servidor viejo que todavía no manda este
    // campo no puede dejar a la app sin poder parsear el maestro.
    val origen: String = "importado",
)
```

Y agregar, después de `RespuestaVinculacion`:

```kotlin
@Serializable
data class OperarioParaIdentificar(
    val id: Int,
    val nombre: String,
    @SerialName("tiene_pin") val tienePin: Boolean,
)

@Serializable
data class RespuestaOperarios(val operarios: List<OperarioParaIdentificar>)

@Serializable
data class RespuestaIdentificacion(
    val operario: OperarioRemoto,
    val proyecto: ProyectoRemoto,
    val pasada: PasadaRemota,
    val token: String,
)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ContratoApi.kt celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ContratoApiTest.kt
git commit -m "Suma los tipos de identificarse y el origen del articulo al contrato del celular"
```

---

## Task 7: Celular red — `ClienteServidor.operarios()` / `.identificar()`

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/red/ClienteServidor.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/red/ClienteServidorTest.kt`

**Interfaces:**
- Consumes: `RespuestaOperarios`, `RespuestaIdentificacion` (Task 6).
- Produces: `suspend fun ClienteServidor.operarios(): RespuestaOperarios`, `suspend fun ClienteServidor.identificar(nombre: String, pin: String? = null): RespuestaIdentificacion`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/app/src/test/kotlin/com/controldestock/red/ClienteServidorTest.kt`:

```kotlin
    @Test
    fun `pide la lista de operarios para identificarse`() = runTest {
        responder(contrato("operarios"))

        val respuesta = cliente.operarios()

        assertEquals("/api/dispositivo/operarios", servidor.takeRequest().path)
        assertEquals("Contrato", respuesta.operarios[0].nombre)
    }

    @Test
    fun `identificarse manda el nombre y el pin`() = runTest {
        responder(contrato("identificacion"))

        val respuesta = cliente.identificar("Contrato", "1234")

        val pedido = servidor.takeRequest()
        assertEquals("/api/dispositivo/identificar", pedido.path)
        assertEquals("token-de-prueba", pedido.getHeader("X-Token"))
        assertTrue(pedido.body.readUtf8().contains("\"pin\":\"1234\""))
        assertTrue(respuesta.token.isNotBlank())
    }

    @Test
    fun `identificarse sin pin no lo manda`() = runTest {
        responder(contrato("identificacion"))

        cliente.identificar("Contrato")

        assertTrue(servidor.takeRequest().body.readUtf8().contains("\"pin\":null"))
    }

    @Test
    fun `un operario que no existe se explica en castellano`() = runTest {
        responder("""{"detail":"Ese operario no existe"}""", HttpURLConnection.HTTP_BAD_REQUEST)

        val error = try {
            cliente.identificar("Nadie"); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.message!!.contains("no existe"))
        assertTrue(error.contenidoRechazado)
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ClienteServidorTest*"`
Expected: FAIL — no compila (`operarios()`/`identificar()` no existen en `ClienteServidor`).

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/red/ClienteServidor.kt`, agregar el import (`OperarioParaIdentificar` no hace falta: no se nombra directo en este archivo, solo viaja adentro de `RespuestaOperarios`):

```kotlin
import com.controldestock.nucleo.RespuestaIdentificacion
import com.controldestock.nucleo.RespuestaOperarios
```

Agregar la clase `PedidoDeIdentificacion` junto a `PedidoDeAlta`:

```kotlin
@Serializable
private data class PedidoDeIdentificacion(val nombre: String, val pin: String?)
```

Y los dos métodos, después de `vincular()`:

```kotlin
    suspend fun operarios(): RespuestaOperarios =
        interpretar(traer("/api/dispositivo/operarios"))

    suspend fun identificar(nombre: String, pin: String? = null): RespuestaIdentificacion {
        val pedido = json.encodeToString(PedidoDeIdentificacion(nombre, pin))
        return interpretar(traer("/api/dispositivo/identificar", cuerpo = pedido))
    }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ClienteServidorTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/red/ClienteServidor.kt celular/app/src/test/kotlin/com/controldestock/red/ClienteServidorTest.kt
git commit -m "El cliente HTTP del celular sabe listar operarios e identificarse"
```

---

## Task 8: Celular datos — `origen` en `ArticuloEntidad` y migración 5→6

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/datos/Entidades.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/datos/MigracionV6Test.kt`

**Interfaces:**
- Produces: `ArticuloEntidad.origen: String = "importado"`. `BaseLocal.MIGRACION_5_6`, `BaseLocal` en `version = 6`.

- [ ] **Step 1: Escribir el test que falla**

Crear `celular/app/src/test/kotlin/com/controldestock/datos/MigracionV6Test.kt`:

```kotlin
package com.controldestock.datos

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

// Copiado de app/schemas/com.controldestock.datos.BaseLocal/5.json.
private val ESQUEMA_V5 = listOf(
    "CREATE TABLE IF NOT EXISTS `vinculacion` (`id` INTEGER NOT NULL, " +
        "`url` TEXT NOT NULL, `token` TEXT NOT NULL, `operarioId` INTEGER NOT NULL, " +
        "`operarioNombre` TEXT NOT NULL, `proyectoId` INTEGER NOT NULL, " +
        "`pasadaId` INTEGER NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`pasadaEtiqueta` TEXT NOT NULL, `esParcial` INTEGER NOT NULL, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `articulo` (`id` INTEGER NOT NULL, " +
        "`idOrden` INTEGER NOT NULL, `tipo` TEXT, `material` TEXT, `sku` TEXT NOT NULL, " +
        "`descripcion` TEXT NOT NULL, `grupo` TEXT, `ubicacion` TEXT, " +
        "`unidad` TEXT NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`proyectoId` INTEGER NOT NULL, `busqueda` TEXT NOT NULL, `estadoAlta` TEXT, " +
        "`motivoRechazo` TEXT, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `codigo` (`codigo` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, PRIMARY KEY(`codigo`, `articuloId`))",
    "CREATE INDEX IF NOT EXISTS `index_codigo_codigo` ON `codigo` (`codigo`)",
    "CREATE TABLE IF NOT EXISTS `unidad` (`codigo` TEXT NOT NULL, " +
        "`nombre` TEXT NOT NULL, `admiteDecimales` INTEGER NOT NULL, PRIMARY KEY(`codigo`))",
    "CREATE TABLE IF NOT EXISTS `conteo` (`uuid` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, `proyectoId` INTEGER NOT NULL, " +
        "`codigo` TEXT NOT NULL, `cantidad` INTEGER NOT NULL, `ubicacionReal` TEXT, " +
        "`observaciones` TEXT, `fueraAsignacion` INTEGER NOT NULL, " +
        "`pasadaId` INTEGER NOT NULL, `timestampDispositivo` TEXT NOT NULL, " +
        "`anulaUuid` TEXT, `estadoSync` TEXT NOT NULL, `motivoRechazo` TEXT, " +
        "PRIMARY KEY(`uuid`))",
    "CREATE TABLE IF NOT EXISTS `asignacion` (`ubicacion` TEXT NOT NULL, " +
        "PRIMARY KEY(`ubicacion`))",
    "CREATE TABLE IF NOT EXISTS `pasada_item` (`articuloId` INTEGER NOT NULL, " +
        "PRIMARY KEY(`articuloId`))",
)

// El `identityHash` del 5.json: sin esta fila la base migrada no parece de
// la versión 5 sino una base ajena, y Room se niega a migrarla.
private const val HASH_V5 = "4ad94ce4a218f3192dcf463daa38f371"

@RunWith(RobolectricTestRunner::class)
class MigracionV6Test {

    private val contexto = ApplicationProvider.getApplicationContext<Context>()

    private fun crearBaseVieja(nombre: String, poblar: (SQLiteDatabase) -> Unit): String {
        val archivo = contexto.getDatabasePath(nombre)
        archivo.parentFile?.mkdirs()
        archivo.delete()

        val vieja = SQLiteDatabase.openOrCreateDatabase(archivo, null)
        ESQUEMA_V5.forEach(vieja::execSQL)
        vieja.execSQL(
            "CREATE TABLE IF NOT EXISTS room_master_table " +
                "(id INTEGER PRIMARY KEY, identity_hash TEXT)",
        )
        vieja.execSQL(
            "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
            arrayOf(HASH_V5),
        )
        poblar(vieja)
        vieja.version = 5
        vieja.close()

        return archivo.absolutePath
    }

    private fun abrirMigrada(ruta: String): BaseLocal =
        Room.databaseBuilder(contexto, BaseLocal::class.java, ruta)
            .addMigrations(BaseLocal.MIGRACION_5_6)
            .build()

    @Test
    fun `un articulo viejo migra con origen importado`() = runTest {
        val ruta = crearBaseVieja("v5-con-articulo.db") { vieja ->
            vieja.execSQL(
                "INSERT INTO articulo (id, idOrden, sku, descripcion, unidad, " +
                    "pasadaNumero, proyectoId, busqueda) " +
                    "VALUES (7, 1, 'A-1', 'Fideos', 'UN', 1, 3, 'fideos a-1')",
            )
        }

        val base = abrirMigrada(ruta)

        val articulo = base.maestroDao().porId(7)
        assertEquals("importado", articulo?.origen)
        base.close()
    }
}
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*MigracionV6Test*"`
Expected: FAIL — no compila (`BaseLocal.MIGRACION_5_6` no existe) o, si compilara por error, fallaría porque `version = 5` no migra a una base declarada en 6.

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/datos/Entidades.kt`, reemplazar la clase `ArticuloEntidad` entera:

```kotlin
@Entity(tableName = "articulo")
data class ArticuloEntidad(
    @PrimaryKey val id: Int,
    val idOrden: Int,
    val tipo: String? = null,
    val material: String? = null,
    val sku: String,
    val descripcion: String,
    val grupo: String? = null,
    val ubicacion: String? = null,
    val unidad: String,
    val pasadaNumero: Int,
    val proyectoId: Int = 0,
    val busqueda: String = "",
    val estadoAlta: String? = null,
    val motivoRechazo: String? = null,
    // De dónde salió: 'importado' del maestro, o 'alta_rapida' si nació en
    // un celular durante el conteo. Es lo que pinta la etiqueta AGREGADO —
    // a diferencia de `estadoAlta`, no se limpia cuando el maestro se
    // reimporta: sale del `origen` que el servidor conserva para siempre.
    val origen: String = "importado",
)
```

(Los comentarios que ya tenían los campos existentes —`pasadaNumero`, `proyectoId`, `busqueda`, `estadoAlta`, `motivoRechazo`— quedan tal cual estaban; el bloque de arriba solo agrega `origen` al final.)

En `celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt`, cambiar `version = 5` por `version = 6`, y agregar la migración después de `MIGRACION_4_5`:

```kotlin
        /**
         * Agrega `origen`, para poder marcar en el celular los artículos
         * nacidos de una alta rápida. Solo una columna, como `MIGRACION_1_2`:
         * no hace falta recrear ninguna tabla.
         */
        val MIGRACION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE articulo ADD COLUMN origen TEXT NOT NULL DEFAULT 'importado'"
                )
            }
        }
```

Y sumarla a la lista de migraciones en `de(contexto: Context)`:

```kotlin
                .addMigrations(
                    MIGRACION_1_2, MIGRACION_2_3, MIGRACION_3_4, MIGRACION_4_5, MIGRACION_5_6,
                )
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*MigracionV6Test*"`
Expected: PASS.

También correr toda la suite del módulo para confirmar que las ~10 construcciones existentes de `ArticuloEntidad` (que no pasan `origen`) siguen compilando gracias al valor por defecto:

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, todo el módulo.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/datos/Entidades.kt celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt celular/app/src/test/kotlin/com/controldestock/datos/MigracionV6Test.kt
git commit -m "Suma origen a la base local del celular (migracion 5 a 6)"
```

---

## Task 9: Celular nucleo — `articuloId` y `agregado` en `RenglonAsignado`

**Files:**
- Modify: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ListaAsignada.kt`
- Test: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ListaAsignadaTest.kt`

**Interfaces:**
- Consumes: `ArticuloParaLista.id` (ya existente).
- Produces: `ArticuloParaLista.origen: String = "importado"`. `RenglonAsignado.articuloId: Int`, `RenglonAsignado.agregado: Boolean = false`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ListaAsignadaTest.kt`, dentro de la clase (la sección `armar`):

```kotlin
    @Test
    fun `cada renglon lleva el id del articulo`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 42, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = emptyList(),
        )

        assertEquals(42, lista.single().renglones.single().articuloId)
    }

    @Test
    fun `un articulo de alta rapida se marca como agregado`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")
                    .copy(origen = "alta_rapida"),
            ),
            conteos = emptyList(),
        )

        assertTrue(lista.single().renglones.single().agregado)
    }

    @Test
    fun `un articulo del maestro original no se marca como agregado`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = emptyList(),
        )

        assertFalse(lista.single().renglones.single().agregado)
    }
```

Y agregar los imports que falten (`assertFalse`) junto a los ya existentes de `org.junit.Assert`.

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL — no compila (`ArticuloParaLista` no tiene `origen`, `RenglonAsignado` no tiene `articuloId` ni `agregado`).

- [ ] **Step 3: Implementar**

En `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ListaAsignada.kt`, cambiar `ArticuloParaLista`:

```kotlin
data class ArticuloParaLista(
    val id: Int,
    val idOrden: Int,
    val sku: String,
    val descripcion: String,
    val ubicacion: String?,
    val unidad: String,
    val codigos: List<String>,
    // 'importado' o 'alta_rapida'. Por defecto «importado»: es lo que vale
    // para casi todos los tests existentes, que no le importa este campo.
    val origen: String = "importado",
)
```

Y `RenglonAsignado`:

```kotlin
data class RenglonAsignado(
    val idOrden: Int,
    val sku: String,
    val descripcion: String,
    val codigos: String,
    val unidad: String,
    val contado: Int?,
    val articuloId: Int,
    // Nace de una alta rápida y no del maestro original.
    val agregado: Boolean = false,
) {
    val fueContado: Boolean get() = contado != null
}
```

Y en `ListaAsignada.armar`, dentro del `.map { articulo -> ... }`, agregar los dos campos:

```kotlin
                .map { articulo ->
                    RenglonAsignado(
                        idOrden = articulo.idOrden,
                        sku = articulo.sku,
                        descripcion = articulo.descripcion,
                        codigos = articulo.codigos.joinToString(", "),
                        unidad = articulo.unidad,
                        contado = contado[articulo.id],
                        articuloId = articulo.id,
                        agregado = articulo.origen == "alta_rapida",
                    )
                }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ListaAsignada.kt celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ListaAsignadaTest.kt
git commit -m "El renglon de Mi Lista lleva el id del articulo y si es un agregado"
```

---

## Task 10: Celular app — `ListaDeTrabajo` pasa `origen`

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ListaDeTrabajo.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ListaDeTrabajoTest.kt`

**Interfaces:**
- Consumes: `ArticuloEntidad.origen` (Task 8), `ArticuloParaLista.origen` (Task 9).

- [ ] **Step 1: Escribir el test que falla**

Agregar a `celular/app/src/test/kotlin/com/controldestock/ListaDeTrabajoTest.kt`:

```kotlin
    @Test
    fun `un alta rapida llega marcada como agregado a la lista`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(1, "A", "P-1").copy(origen = "alta_rapida")),
            codigos = emptyList(), unidades = emptyList(),
        )
        base.asignacionDao().reemplazar(listOf("P-1"))

        assertTrue(lista.armar().single().renglones.single().agregado)
    }
```

(Agregar `import org.junit.Assert.assertTrue` si no está ya en el archivo.)

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ListaDeTrabajoTest*"`
Expected: FAIL — `agregado` da `false` (`ListaDeTrabajo.armar` todavía no manda `origen`).

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/ListaDeTrabajo.kt`, dentro de `armar()`, agregar el campo:

```kotlin
        val paraLista = articulos.map { articulo ->
            ArticuloParaLista(
                id = articulo.id,
                idOrden = articulo.idOrden,
                sku = articulo.sku,
                descripcion = articulo.descripcion,
                ubicacion = articulo.ubicacion,
                unidad = articulo.unidad,
                codigos = codigosPorArticulo[articulo.id] ?: listOf(articulo.sku),
                origen = articulo.origen,
            )
        }
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ListaDeTrabajoTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ListaDeTrabajo.kt celular/app/src/test/kotlin/com/controldestock/ListaDeTrabajoTest.kt
git commit -m "ListaDeTrabajo lleva el origen del articulo hasta el renglon"
```

---

## Task 11: `Contador.buscarPorId` y `origen` en `darDeAlta`

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/Contador.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`

**Interfaces:**
- Produces: `suspend fun Contador.buscarPorId(articuloId: Int): Hallazgo.Encontrado?`. `darDeAlta` deja el artículo con `origen = "alta_rapida"`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`:

```kotlin
    @Test
    fun `buscarPorId encuentra el articulo por su id`() = runTest {
        val hallazgo = contador().buscarPorId(1)

        assertEquals("Fideos", hallazgo?.articulo?.descripcion)
    }

    @Test
    fun `buscarPorId devuelve null si el articulo no existe`() = runTest {
        assertEquals(null, contador().buscarPorId(999))
    }

    @Test
    fun `buscarPorId respeta el recuento parcial`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = "http://172.16.11.12:8000", token = "abc",
                operarioId = 1, operarioNombre = "Juan", proyectoId = 1,
                pasadaId = 2, pasadaNumero = 2, pasadaEtiqueta = "Conteo 2",
                esParcial = true,
            ),
        )
        base.pasadaItemDao().reemplazar(listOf(2)) // solo Harina, no Fideos

        assertEquals(null, contador().buscarPorId(1))
    }

    @Test
    fun `el alta rapida nace marcada como agregado`() = runTest {
        contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        val nuevo = base.maestroDao().porCodigo("7790999")
        assertEquals("alta_rapida", nuevo?.origen)
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ContadorTest*"`
Expected: FAIL — `buscarPorId` no existe (no compila) y, una vez que compile, `el alta rapida nace marcada como agregado` falla porque `origen` sale `"importado"`.

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/Contador.kt`, agregar después de `buscar`:

```kotlin
    /**
     * Resuelve un artículo ya elegido de la lista o de una búsqueda, sin
     * pasar por ningún código de barras.
     *
     * `null` cubre dos casos que se tratan igual: el artículo ya no existe
     * —la lista se armó con un refresco anterior y el maestro se volvió a
     * bajar— o quedó fuera de un recuento parcial que empezó mientras tanto.
     * Ninguno de los dos amerita distinguir del otro lado: no hay ficha que
     * abrir.
     */
    suspend fun buscarPorId(articuloId: Int): Hallazgo.Encontrado? {
        val articulo = base.maestroDao().porId(articuloId) ?: return null

        val vinculacion = base.vinculacionDao().actual()
        if (vinculacion?.esParcial == true && !base.pasadaItemDao().contiene(articulo.id)) {
            return null
        }

        val admite = base.maestroDao().unidad(articulo.unidad)?.admiteDecimales == 1
        val codigo = base.maestroDao().codigoDe(articulo.id) ?: articulo.sku
        return Hallazgo.Encontrado(articulo, admite, codigo)
    }
```

Y en `darDeAlta`, agregar `origen = "alta_rapida",` a la construcción de `ArticuloEntidad`:

```kotlin
        val articulo = ArticuloEntidad(
            id = base.maestroDao().proximoIdLocal(),
            idOrden = base.maestroDao().proximoOrden(),
            sku = codigo,
            descripcion = descripcion,
            ubicacion = ubicacion,
            unidad = unidad,
            pasadaNumero = vinculacion?.pasadaNumero ?: 1,
            proyectoId = vinculacion?.proyectoId ?: 0,
            busqueda = textoDeBusqueda(descripcion, codigo, ubicacion),
            estadoAlta = EstadoSync.PENDIENTE.name,
            origen = "alta_rapida",
        )
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ContadorTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/Contador.kt celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt
git commit -m "Contador resuelve un articulo por id y marca el alta rapida como agregada"
```

---

## Task 12: `Contador.buscarTexto`

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/Contador.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`

**Interfaces:**
- Consumes: `MaestroDao.buscar(texto)` (ya existente), `buscarPorId` (Task 11).
- Produces: `suspend fun Contador.buscarTexto(texto: String): List<Hallazgo.Encontrado>`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`:

```kotlin
    @Test
    fun `buscarTexto encuentra por descripcion`() = runTest {
        val resultados = contador().buscarTexto("fide")

        assertEquals(1, resultados.size)
        assertEquals("Fideos", resultados[0].articulo.descripcion)
    }

    @Test
    fun `buscarTexto encuentra por sku`() = runTest {
        val resultados = contador().buscarTexto("A-2")

        assertEquals("Harina", resultados.single().articulo.descripcion)
    }

    @Test
    fun `buscarTexto sin coincidencias devuelve lista vacia`() = runTest {
        assertTrue(contador().buscarTexto("no existe nada con esto").isEmpty())
    }

    @Test
    fun `buscarTexto no trae lo que quedo fuera de un recuento parcial`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = "http://172.16.11.12:8000", token = "abc",
                operarioId = 1, operarioNombre = "Juan", proyectoId = 1,
                pasadaId = 2, pasadaNumero = 2, pasadaEtiqueta = "Conteo 2",
                esParcial = true,
            ),
        )
        base.pasadaItemDao().reemplazar(listOf(2)) // solo Harina, no Fideos

        assertTrue(contador().buscarTexto("fide").isEmpty())
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ContadorTest*"`
Expected: FAIL — no compila (`buscarTexto` no existe).

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/Contador.kt`, agregar después de `buscarPorId`:

```kotlin
    /**
     * Busca por SKU o por descripción, para cuando la etiqueta está rota y
     * ni la cámara ni «A mano» sirven.
     *
     * Reutiliza `buscarPorId` para cada coincidencia: así hereda de una sola
     * vez el mismo filtro de recuento parcial que ya usa el resto del
     * conteo, en vez de repetirlo acá.
     */
    suspend fun buscarTexto(texto: String): List<Hallazgo.Encontrado> =
        base.maestroDao().buscar(texto).mapNotNull { buscarPorId(it.id) }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ContadorTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/Contador.kt celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt
git commit -m "Contador puede buscar un articulo por texto para la etiqueta rota"
```

---

## Task 13: `Vinculador.identificar()` y `origen` al bajar el maestro

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/Vinculador.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/VinculadorTest.kt`

**Interfaces:**
- Consumes: `ClienteServidor.identificar()` (Task 7), `BaseLocal.vincularA` (ya existente), `ArticuloRemoto.origen` (Task 6).
- Produces: `suspend fun Vinculador.identificar(nombre: String, pin: String? = null): ResultadoDeVinculacion`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/app/src/test/kotlin/com/controldestock/VinculadorTest.kt`:

```kotlin
    @Test
    fun `el maestro descargado guarda el origen de cada articulo`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertEquals("importado", base.maestroDao().articulos().first().origen)
    }

    @Test
    fun `identificarse cambia de operario sin tocar el maestro`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = servidor.url("/").toString().trimEnd('/'), token = "token-viejo",
                operarioId = 1, operarioNombre = "Juan",
                proyectoId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )
        responder(contrato("identificacion"))

        val resultado = vinculador().identificar("Ana", null)

        assertTrue(resultado is ResultadoDeVinculacion.Vinculado)
        val actual = base.vinculacionDao().actual()!!
        assertEquals("Contrato", actual.operarioNombre)
        assertEquals("token-de-contrato-para-identificarse", actual.token)
    }

    @Test
    fun `identificarse sin estar vinculado antes falla`() = runTest {
        val resultado = vinculador().identificar("Ana", null)

        assertTrue(resultado is ResultadoDeVinculacion.Fallo)
    }

    @Test
    fun `identificarse manda el pin al servidor`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = servidor.url("/").toString().trimEnd('/'), token = "token-viejo",
                operarioId = 1, operarioNombre = "Juan",
                proyectoId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )
        responder("""{"detail":"El PIN no coincide"}""", 400)

        val resultado = vinculador().identificar("Ana", "0000")

        val mensaje = (resultado as ResultadoDeVinculacion.Fallo).mensaje
        assertTrue(mensaje.contains("PIN"))
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*VinculadorTest*"`
Expected: FAIL — no compila (`identificar` no existe en `Vinculador`), y `el maestro descargado guarda el origen` falla porque el mapeo todavía no incluye `origen`.

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/Vinculador.kt`, agregar `origen = it.origen,` al mapeo dentro de `vincular`:

```kotlin
            base.maestroDao().reemplazarMaestro(
                articulos = maestro.articulos.map {
                    ArticuloEntidad(
                        id = it.id, idOrden = it.idOrden, tipo = it.tipo,
                        material = it.material, sku = it.sku,
                        descripcion = it.descripcion, grupo = it.grupo,
                        ubicacion = it.ubicacion, unidad = it.unidad,
                        pasadaNumero = quien.pasada.numero,
                        proyectoId = quien.proyecto.id,
                        busqueda = textoDeBusqueda(it.descripcion, it.sku, it.ubicacion),
                        origen = it.origen,
                    )
                },
```

Y agregar el método `identificar`, después de `vincular`:

```kotlin
    /**
     * Identifica a otra persona en un celular que ya está vinculado, sin
     * volver a escanear el QR.
     *
     * A diferencia de `vincular`, no baja el maestro de nuevo: es el mismo
     * proyecto, así que el que ya está en la base local sigue valiendo.
     */
    suspend fun identificar(nombre: String, pin: String?): ResultadoDeVinculacion {
        val actual = base.vinculacionDao().actual()
            ?: return ResultadoDeVinculacion.Fallo(
                "Este celular todavía no está vinculado a ningún panel.",
            )

        val cliente = crearCliente(actual.url, actual.token)

        return try {
            val quien = cliente.identificar(nombre, pin)

            base.vincularA(
                VinculacionEntidad(
                    url = actual.url,
                    token = quien.token,
                    operarioId = quien.operario.id,
                    operarioNombre = quien.operario.nombre,
                    proyectoId = quien.proyecto.id,
                    pasadaId = quien.pasada.id,
                    pasadaNumero = quien.pasada.numero,
                    pasadaEtiqueta = quien.pasada.etiqueta,
                ),
            )

            ResultadoDeVinculacion.Vinculado(quien.operario.nombre, quien.proyecto.nombre)
        } catch (error: ErrorDeServidor) {
            ResultadoDeVinculacion.Fallo(error.message.orEmpty())
        }
    }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*VinculadorTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/Vinculador.kt celular/app/src/test/kotlin/com/controldestock/VinculadorTest.kt
git commit -m "Vinculador permite identificarse sin QR en un celular ya vinculado"
```

---

## Task 14: `Pantalla.kt` — parámetro `buscando`

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`

**Interfaces:**
- Produces: `fichaAbierta(hallazgo, altaDe, ingresandoAMano, buscando: Boolean = false): Boolean`. `Atras.CierraBusqueda`. `atrasCierra(hallazgo, altaDe, ingresandoAMano, buscando: Boolean = false): Atras`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`:

```kotlin
    @Test
    fun `buscar un producto tambien pausa la camara`() {
        assertTrue(
            fichaAbierta(hallazgo = null, altaDe = null, ingresandoAMano = false, buscando = true),
        )
    }

    @Test
    fun `sin buscar nada abierto no pausa la camara por eso`() {
        assertFalse(
            fichaAbierta(hallazgo = null, altaDe = null, ingresandoAMano = false, buscando = false),
        )
    }

    @Test
    fun `atras cierra la busqueda antes que la lista`() {
        assertEquals(
            Atras.CierraBusqueda,
            atrasCierra(hallazgo = null, altaDe = null, ingresandoAMano = false, buscando = true),
        )
    }

    @Test
    fun `atras cierra el ingreso a mano antes que la busqueda`() {
        // Ambos podrían estar abiertos si el operario llegó a «A mano» desde
        // el botón «Ingresarlo a mano» del diálogo de búsqueda.
        assertEquals(
            Atras.CierraIngresoAMano,
            atrasCierra(hallazgo = null, altaDe = null, ingresandoAMano = true, buscando = true),
        )
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*PantallaTest*"`
Expected: FAIL — no compila (`buscando` no es un parámetro válido, `Atras.CierraBusqueda` no existe).

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`, cambiar `fichaAbierta`:

```kotlin
fun fichaAbierta(
    hallazgo: Hallazgo?,
    altaDe: String?,
    ingresandoAMano: Boolean,
    // Con valor por defecto a propósito: son más de una decena de llamadas
    // existentes, ninguna sabe de búsqueda, y agregar un cuarto booleano acá
    // no cambia ninguna de ellas — «false» es exactamente el comportamiento
    // que ya tenían.
    buscando: Boolean = false,
): Boolean = hallazgo is Hallazgo.Encontrado || altaDe != null || ingresandoAMano || buscando
```

Y `Atras`/`atrasCierra`:

```kotlin
sealed class Atras {
    object CierraIngresoAMano : Atras()
    object CierraBusqueda : Atras()
    object CierraAlta : Atras()
    object CierraFicha : Atras()
    object VuelveALaLista : Atras()
}

/**
 * Decide qué hace el botón atrás de Android en la pantalla de escaneo.
 *
 * El orden es al revés de `fichaAbierta`: ahí cualquiera de las causas
 * alcanza para pausar la cámara, acá hay que elegir una sola cosa para
 * cerrar. «A mano» va antes que la búsqueda porque a ese diálogo se puede
 * llegar *desde* la búsqueda (el botón «Ingresarlo a mano»), así que puede
 * haber dos abiertos a la vez y hay que cerrar el de encima primero.
 */
fun atrasCierra(
    hallazgo: Hallazgo?,
    altaDe: String?,
    ingresandoAMano: Boolean,
    buscando: Boolean = false,
): Atras = when {
    ingresandoAMano -> Atras.CierraIngresoAMano
    buscando -> Atras.CierraBusqueda
    altaDe != null -> Atras.CierraAlta
    hallazgo is Hallazgo.Encontrado -> Atras.CierraFicha
    else -> Atras.VuelveALaLista
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*PantallaTest*"`
Expected: PASS, incluidos los tests viejos (siguen llamando sin `buscando`, que ahora vale `false` por defecto).

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt
git commit -m "La busqueda de productos pausa la camara y el boton atras la cierra"
```

---

## Task 15: `Tema.kt` — color Violeta

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/Tema.kt`

**Interfaces:**
- Produces: `val Violeta: Color`.

- [ ] **Step 1: Implementar**

Este archivo es una tabla de constantes sin lógica: no hay nada que un test unitario verifique aparte de que compile (la Task 16 sí prueba, con Compose, que la etiqueta se ve). En `celular/app/src/main/kotlin/com/controldestock/ui/Tema.kt`, agregar junto a las otras:

```kotlin
val Acento = Color(0xFF1F5FA9)
val Verde = Color(0xFF1B7A3D)
val Rojo = Color(0xFFB3261E)
val Ambar = Color(0xFF9A5B12)
// Solo para la etiqueta AGREGADO: no repite Verde (contado), Ambar
// (pendiente) ni Rojo (error), y no reusa Acento porque ese ya es el color
// primario de toda la app —una etiqueta con ese tono se confundiría con un
// botón—. El panel no tiene un color equivalente: ahí la misma marca usa la
// clase `.marca`, neutra, no un color por tipo.
val Violeta = Color(0xFF6A3FA0)
```

- [ ] **Step 2: Compilar**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:compileDebugKotlin --no-daemon`
Expected: BUILD SUCCESSFUL.

- [ ] **Step 3: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/Tema.kt
git commit -m "Suma el color de la etiqueta AGREGADO a la paleta del celular"
```

---

## Task 16: `PantallaMiLista` — tarjeta tocable, AGREGADO y encabezado con operario

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaMiLista.kt`
- Test: `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaMiListaTest.kt`

**Interfaces:**
- Consumes: `RenglonAsignado.articuloId`, `.agregado` (Task 9), `Violeta` (Task 15).
- Produces: `PantallaMiLista` gana los parámetros `operario: String`, `alTocarProducto: (Int) -> Unit` y `alIdentificarse: () -> Unit`; `TarjetaProducto` es tocable.

- [ ] **Step 1: Escribir los tests que fallan**

En `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaMiListaTest.kt`, cambiar el helper `renglon` para que acepte `agregado`:

```kotlin
    private fun renglon(
        idOrden: Int, sku: String, contado: Int? = null,
        articuloId: Int = idOrden, agregado: Boolean = false,
    ) = RenglonAsignado(
        idOrden = idOrden, sku = sku, descripcion = "Producto $sku",
        codigos = sku, unidad = "UN", contado = contado,
        articuloId = articuloId, agregado = agregado,
    )
```

Y el helper `montar` para que acepte los dos parámetros nuevos, con default para no tocar las llamadas existentes:

```kotlin
    private fun montar(
        ubicaciones: List<UbicacionAsignada> = emptyList(),
        pasada: String = "Conteo 1",
        operario: String = "Juan",
        actualizando: Boolean = false,
        avisoDeActualizacion: String? = null,
        pendientes: Int = 0,
        estadoDeSubida: EstadoDeSubida = EstadoDeSubida.Quieto,
        oscuro: Boolean = false,
        version: String = "v2026-08-21 (build 223)",
        alActualizar: () -> Unit = {},
        alSubir: () -> Unit = {},
        alContar: () -> Unit = {},
        alCambiarTema: () -> Unit = {},
        alTocarProducto: (Int) -> Unit = {},
        alIdentificarse: () -> Unit = {},
    ) {
        compose.setContent {
            PantallaMiLista(
                ubicaciones = ubicaciones,
                pasada = pasada,
                operario = operario,
                actualizando = actualizando,
                avisoDeActualizacion = avisoDeActualizacion,
                pendientes = pendientes,
                estadoDeSubida = estadoDeSubida,
                oscuro = oscuro,
                version = version,
                alActualizar = alActualizar,
                alSubir = alSubir,
                alContar = alContar,
                alCambiarTema = alCambiarTema,
                alTocarProducto = alTocarProducto,
                alIdentificarse = alIdentificarse,
            )
        }
    }
```

Y agregar los tests nuevos al final de la clase:

```kotlin
    @Test
    fun `el nombre del operario se muestra en el encabezado`() {
        montar(operario = "María")

        compose.onNodeWithText("María").assertIsDisplayed()
    }

    @Test
    fun `el boton Cambiar llama a alIdentificarse`() {
        var identificando = false
        montar(alIdentificarse = { identificando = true })

        compose.onNodeWithText("Cambiar").performClick()

        assertTrue(identificando)
    }

    @Test
    fun `tocar la tarjeta de un producto llama a alTocarProducto con su id`() {
        var tocado: Int? = null
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A-1", articuloId = 42))),
            ),
            alTocarProducto = { tocado = it },
        )

        scrollHasta("ID: 001 | SKU: A-1", substring = true)
        compose.onNodeWithText("ID: 001 | SKU: A-1", substring = true).performClick()

        assertEquals(42, tocado)
    }

    @Test
    fun `un producto agregado muestra la etiqueta AGREGADO`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A", agregado = true))),
            ),
        )

        scrollHasta("AGREGADO")
        compose.onNodeWithText("AGREGADO").assertIsDisplayed()
    }

    @Test
    fun `un producto del maestro original no muestra AGREGADO`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A"))),
            ),
        )

        scrollHasta("PENDIENTE")
        compose.onAllNodesWithText("AGREGADO").assertCountEquals(0)
    }
```

(Agregar `import androidx.compose.ui.test.performClick` si no está, y usar `performClick()` sobre el `Modifier.clickable` de la fila, que engloba el texto del renglón.)

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*PantallaMiListaTest*"`
Expected: FAIL — no compila (`PantallaMiLista` todavía no tiene `operario` ni `alTocarProducto`, `RenglonAsignado` con `articuloId`/`agregado` ya compila desde la Task 9 pero la pantalla no los usa).

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/ui/PantallaMiLista.kt`:

Agregar los imports que hagan falta: `androidx.compose.foundation.clickable`.

Cambiar la firma de `PantallaMiLista`:

```kotlin
@Composable
fun PantallaMiLista(
    ubicaciones: List<UbicacionAsignada>,
    pasada: String,
    operario: String,
    actualizando: Boolean,
    avisoDeActualizacion: String?,
    pendientes: Int,
    estadoDeSubida: EstadoDeSubida,
    oscuro: Boolean,
    version: String,
    alActualizar: () -> Unit,
    alSubir: () -> Unit,
    alContar: () -> Unit,
    alCambiarTema: () -> Unit,
    alTocarProducto: (Int) -> Unit,
    alIdentificarse: () -> Unit,
) {
```

Mostrar el operario debajo de la pasada, en el bloque del encabezado:

```kotlin
                    Text(
                        pasada,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            operario,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        TextButton(onClick = alIdentificarse) {
                            Text("Cambiar", style = MaterialTheme.typography.bodySmall)
                        }
                    }
```

(Va justo después del `Text(pasada, ...)` que ya existe, dentro del mismo `Column`.)

Pasar `alTocarProducto` hasta `TarjetaProducto`, cambiando la llamada dentro del `items(...)`:

```kotlin
                        items(
                            ubicacion.renglones,
                            key = { "${ubicacion.ubicacion}-${it.sku}" },
                        ) { renglon -> TarjetaProducto(renglon, alTocar = { alTocarProducto(renglon.articuloId) }) }
```

Y hacer tocable `TarjetaProducto`, agregando el parámetro y el modificador:

```kotlin
@Composable
private fun TarjetaProducto(renglon: RenglonAsignado, alTocar: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp).clickable(onClick = alTocar),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    "ID: ${"%03d".format(renglon.idOrden)} | SKU: ${renglon.sku}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                Column(horizontalAlignment = Alignment.End) {
                    if (renglon.fueContado) Etiqueta("CONTADO", Verde) else Etiqueta("PENDIENTE", Ambar)
                    if (renglon.agregado) Etiqueta("AGREGADO", Violeta)
                }
            }
            Text(
                renglon.descripcion,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 4.dp),
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    renglon.codigos,
                    style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                CantidadDelRenglon(renglon)
            }
        }
    }
}
```

(Cambia la fila superior de una sola etiqueta a una `Column` con hasta dos, para que CONTADO/PENDIENTE y AGREGADO convivan sin superponerse.)

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*PantallaMiListaTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/PantallaMiLista.kt celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaMiListaTest.kt
git commit -m "Mi Lista muestra el operario, la etiqueta AGREGADO y cuenta al tocar la tarjeta"
```

---

## Task 17: `DialogoIdentificarse`

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/DialogoIdentificarse.kt`
- Create: `celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoIdentificarseTest.kt`

**Interfaces:**
- Consumes: `OperarioParaIdentificar` (Task 6).
- Produces: `@Composable fun DialogoIdentificarse(operarios: List<OperarioParaIdentificar>, cargando: Boolean, error: String?, alElegir: (nombre: String, pin: String?) -> Unit, alCerrar: () -> Unit)`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoIdentificarseTest.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.controldestock.nucleo.OperarioParaIdentificar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class DialogoIdentificarseTest {

    @get:Rule
    val compose = createComposeRule()

    private val juan = OperarioParaIdentificar(1, "Juan", tienePin = false)
    private val ana = OperarioParaIdentificar(2, "Ana", tienePin = true)

    @Test
    fun `tocar un operario sin pin identifica directo`() {
        var elegido: Pair<String, String?>? = null
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(juan), cargando = false, error = null,
                alElegir = { nombre, pin -> elegido = nombre to pin }, alCerrar = {},
            )
        }

        compose.onNodeWithText("Juan").performClick()

        assertEquals("Juan" to null, elegido)
    }

    @Test
    fun `tocar un operario con pin pide el pin antes de entrar`() {
        var elegido: Pair<String, String?>? = null
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(ana), cargando = false, error = null,
                alElegir = { nombre, pin -> elegido = nombre to pin }, alCerrar = {},
            )
        }

        compose.onNodeWithText("Ana").performClick()
        compose.onNodeWithText("PIN").performScrollTo().performTextInput("1234")
        compose.onNodeWithText("Entrar").performClick()

        assertEquals("Ana" to "1234", elegido)
    }

    @Test
    fun `mientras carga no muestra ningun nombre`() {
        compose.setContent {
            DialogoIdentificarse(
                operarios = emptyList(), cargando = true, error = null,
                alElegir = { _, _ -> }, alCerrar = {},
            )
        }

        compose.onNodeWithText("Cargando…").assertIsDisplayed()
    }

    @Test
    fun `un error se muestra`() {
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(juan), cargando = false, error = "El PIN no coincide",
                alElegir = { _, _ -> }, alCerrar = {},
            )
        }

        compose.onNodeWithText("El PIN no coincide").assertIsDisplayed()
    }

    @Test
    fun `cancelar avisa`() {
        var cancelado = false
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(juan), cargando = false, error = null,
                alElegir = { _, _ -> }, alCerrar = { cancelado = true },
            )
        }

        compose.onNodeWithText("Cancelar").performClick()

        assertTrue(cancelado)
    }
}
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*DialogoIdentificarseTest*"`
Expected: FAIL — no compila (`DialogoIdentificarse` no existe).

- [ ] **Step 3: Implementar**

Crear `celular/app/src/main/kotlin/com/controldestock/ui/DialogoIdentificarse.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.controldestock.nucleo.OperarioParaIdentificar

/**
 * Identificarse en un celular ya vinculado, sin volver a escanear el QR.
 *
 * Pide el PIN solo si ese operario lo tiene cargado desde el panel: la
 * mayoría entra con solo elegir su nombre, a propósito.
 */
@Composable
fun DialogoIdentificarse(
    operarios: List<OperarioParaIdentificar>,
    cargando: Boolean,
    error: String?,
    alElegir: (nombre: String, pin: String?) -> Unit,
    alCerrar: () -> Unit,
) {
    var elegido by remember { mutableStateOf<OperarioParaIdentificar?>(null) }
    var pin by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text(elegido?.let { "PIN de ${it.nombre}" } ?: "¿Quién sos?") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                when {
                    cargando -> Text("Cargando…")
                    elegido == null -> operarios.forEach { o ->
                        TextButton(onClick = {
                            if (o.tienePin) elegido = o else alElegir(o.nombre, null)
                        }) { Text(o.nombre) }
                    }
                    else -> OutlinedTextField(
                        value = pin,
                        onValueChange = { pin = it },
                        label = { Text("PIN") },
                    )
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            elegido?.let { o ->
                TextButton(onClick = { alElegir(o.nombre, pin) }) { Text("Entrar") }
            }
        },
        dismissButton = { TextButton(onClick = alCerrar) { Text("Cancelar") } },
    )
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*DialogoIdentificarseTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/DialogoIdentificarse.kt celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoIdentificarseTest.kt
git commit -m "Agrega el dialogo para identificarse sin QR"
```

---

## Task 18: `DialogoBuscarProducto`

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/DialogoBuscarProducto.kt`
- Create: `celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoBuscarProductoTest.kt`

**Interfaces:**
- Consumes: `Hallazgo.Encontrado` (ya existente).
- Produces: `@Composable fun DialogoBuscarProducto(resultados: List<Hallazgo.Encontrado>, alCambiarTexto: (String) -> Unit, alElegir: (Hallazgo.Encontrado) -> Unit, alIngresarAMano: () -> Unit, alCerrar: () -> Unit)`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoBuscarProductoTest.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.controldestock.Hallazgo
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.textoDeBusqueda
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class DialogoBuscarProductoTest {

    @get:Rule
    val compose = createComposeRule()

    private val fideos = Hallazgo.Encontrado(
        ArticuloEntidad(
            id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
            unidad = "UN", pasadaNumero = 1, proyectoId = 1,
            busqueda = textoDeBusqueda("Fideos", "A-1", null),
        ),
        admiteDecimales = false, codigo = "A-1",
    )

    @Test
    fun `escribir dispara la busqueda con el texto tipeado`() {
        var buscado: String? = null
        compose.setContent {
            DialogoBuscarProducto(
                resultados = emptyList(),
                alCambiarTexto = { buscado = it },
                alElegir = {}, alIngresarAMano = {}, alCerrar = {},
            )
        }

        compose.onNodeWithText("SKU o descripción").performScrollTo().performTextInput("fide")

        assertEquals("fide", buscado)
    }

    @Test
    fun `muestra los resultados y tocar uno lo elige`() {
        var elegido: Hallazgo.Encontrado? = null
        compose.setContent {
            DialogoBuscarProducto(
                resultados = listOf(fideos),
                alCambiarTexto = {}, alElegir = { elegido = it },
                alIngresarAMano = {}, alCerrar = {},
            )
        }

        compose.onNodeWithText("A-1 — Fideos", substring = true).performClick()

        assertEquals(fideos, elegido)
    }

    @Test
    fun `sin resultados con texto tipeado ofrece ingresarlo a mano`() {
        var fueAMano = false
        compose.setContent {
            DialogoBuscarProducto(
                resultados = emptyList(),
                alCambiarTexto = {}, alElegir = {}, alIngresarAMano = { fueAMano = true },
                alCerrar = {},
            )
        }
        compose.onNodeWithText("SKU o descripción").performScrollTo().performTextInput("nada")

        compose.onNodeWithText("Ingresarlo a mano").performClick()

        assertTrue(fueAMano)
    }

    @Test
    fun `sin escribir nada todavia no ofrece ingresarlo a mano`() {
        compose.setContent {
            DialogoBuscarProducto(
                resultados = emptyList(),
                alCambiarTexto = {}, alElegir = {}, alIngresarAMano = {}, alCerrar = {},
            )
        }

        // No hay texto tipeado: no es que no se encontró nada, es que
        // todavía no se buscó nada.
        assertTrue(
            compose.onAllNodesWithText("Ingresarlo a mano").fetchSemanticsNodes().isEmpty(),
        )
    }
}
```

(Requiere `import androidx.compose.ui.test.onAllNodesWithText` para el último test.)

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*DialogoBuscarProductoTest*"`
Expected: FAIL — no compila (`DialogoBuscarProducto` no existe).

- [ ] **Step 3: Implementar**

Crear `celular/app/src/main/kotlin/com/controldestock/ui/DialogoBuscarProducto.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.controldestock.Hallazgo

/**
 * Buscar un producto por SKU o descripción, para cuando la etiqueta está
 * rota y ni la cámara ni «A mano» sirven.
 *
 * Sin resultado propio de alta: si no aparece nada, ofrece «A mano», el
 * mismo camino que ya sabe decir «desconocido» y dar de alta sin
 * duplicar artículos.
 */
@Composable
fun DialogoBuscarProducto(
    resultados: List<Hallazgo.Encontrado>,
    alCambiarTexto: (String) -> Unit,
    alElegir: (Hallazgo.Encontrado) -> Unit,
    alIngresarAMano: () -> Unit,
    alCerrar: () -> Unit,
) {
    var texto by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("Buscar producto") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = texto,
                    onValueChange = { texto = it; alCambiarTexto(it) },
                    label = { Text("SKU o descripción") },
                    modifier = Modifier.fillMaxWidth(),
                )
                if (texto.isNotBlank() && resultados.isEmpty()) {
                    Text("No se encontró ningún producto con ese texto.")
                    TextButton(onClick = alIngresarAMano) { Text("Ingresarlo a mano") }
                }
                resultados.forEach { hallazgo ->
                    TextButton(onClick = { alElegir(hallazgo) }) {
                        Text("${hallazgo.articulo.sku} — ${hallazgo.articulo.descripcion}")
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = alCerrar) { Text("Cerrar") } },
    )
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*DialogoBuscarProductoTest*"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/DialogoBuscarProducto.kt celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoBuscarProductoTest.kt
git commit -m "Agrega el dialogo para buscar un producto por texto"
```

---

## Task 19: `PantallaEscaneo` — botón «Buscar»

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`
- Test: `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt`

**Interfaces:**
- Produces: `PantallaEscaneo` gana los parámetros `puedeBuscar: Boolean` y `alBuscar: () -> Unit`.

- [ ] **Step 1: Escribir los tests que fallan**

En `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt`, agregar `puedeBuscar = true, alBuscar = {}` a las **siete** llamadas existentes a `PantallaEscaneo(...)` en el archivo (una por cada `@Test`), y sumar los dos tests nuevos al final de la clase:

```kotlin
    @Test
    fun `el boton de buscar llama al callback cuando esta habilitado`() {
        var abrio = false
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = false,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = true,
                alIngresarAMano = {},
                puedeBuscar = true,
                alBuscar = { abrio = true },
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("Buscar").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `el boton de buscar queda deshabilitado con algo mas abierto`() {
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = true,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = false,
                alIngresarAMano = {},
                puedeBuscar = false,
                alBuscar = {},
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("Buscar").assertIsNotEnabled()
    }
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*PantallaEscaneoTest*"`
Expected: FAIL — no compila (`puedeBuscar`/`alBuscar` no son parámetros de `PantallaEscaneo` todavía).

- [ ] **Step 3: Implementar**

En `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`, agregar los parámetros a `PantallaEscaneo` (después de `alIngresarAMano`):

```kotlin
    puedeIngresarAMano: Boolean,
    alIngresarAMano: () -> Unit,
    /** Si el operario puede abrir la búsqueda por texto ahora mismo. */
    puedeBuscar: Boolean,
    alBuscar: () -> Unit,
```

Y el botón, al lado de «A mano»:

```kotlin
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(
                    onClick = alIngresarAMano,
                    enabled = puedeIngresarAMano,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                ) {
                    Text("A mano", style = MaterialTheme.typography.bodySmall)
                }
                OutlinedButton(
                    onClick = alBuscar,
                    enabled = puedeBuscar,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                ) {
                    Text("Buscar", style = MaterialTheme.typography.bodySmall)
                }
                IndicadorDePendientes(
                    pendientes = pendientes,
                    estado = estadoDeSubida,
                    alSubir = alSubir,
                )
            }
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*PantallaEscaneoTest*"`
Expected: PASS.

- [ ] **Step 5: Verificar en un celular real**

Instalar un build de depuración en el celular de pruebas y confirmar que, con un nombre de operario largo, el encabezado sigue mostrando «A mano», «Buscar» y el indicador de pendientes sin cortarse ni desbordar. Si no entra cómodo, es la señal anotada en el spec para acortar los textos — no está en el alcance de este plan resolverlo ahora, solo detectarlo.

- [ ] **Step 6: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt
git commit -m "Agrega el boton Buscar a la pantalla de escaneo"
```

---

## Task 20: `MainActivity` — cableado final

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Interfaces:**
- Consumes: todo lo de las Tasks 1-19: `Contador.buscarPorId`/`.buscarTexto` (11, 12), `Vinculador.identificar` (13), `ClienteServidor.operarios`/`.identificar` (7), `fichaAbierta`/`atrasCierra` con `buscando` (14), `PantallaMiLista` con `operario`/`alTocarProducto` (16), `DialogoIdentificarse` (17), `DialogoBuscarProducto` (18), `PantallaEscaneo` con `puedeBuscar`/`alBuscar` (19).

Esta tarea no tiene test unitario propio — es cableado de UI en una `Activity`, del mismo tipo que ya cablea hoy `leerCodigo`, `altaDe` e `ingresandoAMano`, y su única verificación real es en un celular. Se apoya en los tests ya escritos de cada pieza (Tasks 1-19) para confiar en que cada parte anda por separado.

- [ ] **Step 1: Agregar el estado nuevo**

En `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`, dentro de `App(...)`, junto a los demás `var` de estado:

```kotlin
    // Buscar un producto por texto: mismo tratamiento que `ingresandoAMano`,
    // pausa la cámara y el botón atrás lo cierra antes que la ficha.
    var buscando by remember { mutableStateOf(false) }
    var resultadosDeBusqueda by remember { mutableStateOf<List<Hallazgo.Encontrado>>(emptyList()) }

    // Identificarse sin QR.
    var identificando by remember { mutableStateOf(false) }
    var operariosParaIdentificar by remember { mutableStateOf<List<OperarioParaIdentificar>>(emptyList()) }
    var cargandoOperarios by remember { mutableStateOf(false) }
    var errorDeIdentificacion by remember { mutableStateOf<String?>(null) }
```

Y los imports que hagan falta:

```kotlin
import com.controldestock.nucleo.OperarioParaIdentificar
import com.controldestock.ui.DialogoBuscarProducto
import com.controldestock.ui.DialogoIdentificarse
```

- [ ] **Step 2: Actualizar las llamadas a `fichaAbierta`/`atrasCierra`**

En la variable `hayAlgoAbierto` y en el `BackHandler`, agregar `buscando`:

```kotlin
            val hayAlgoAbierto = fichaAbierta(hallazgo, altaDe, ingresandoAMano, buscando)

            BackHandler {
                when (atrasCierra(hallazgo, altaDe, ingresandoAMano, buscando)) {
                    Atras.CierraIngresoAMano -> ingresandoAMano = false
                    Atras.CierraBusqueda -> buscando = false
                    Atras.CierraAlta -> altaDe = null
                    Atras.CierraFicha -> hallazgo = null
                    Atras.VuelveALaLista -> pantalla = Pantalla.EnLaLista
                }
            }
```

- [ ] **Step 3: Cablear «tocar la tarjeta para contar» (Task 9-11, 16)**

Agregar, junto a `leerCodigo`, una función hermana:

```kotlin
    /** Igual que `leerCodigo`, pero para un artículo ya elegido de la lista o de una búsqueda. */
    val contarPorId: (Int) -> Unit = { articuloId ->
        alcance.launch {
            val h = contador.buscarPorId(articuloId) ?: return@launch
            previos = contador.conteosDe(h.articulo)
            hallazgo = h
        }
    }
```

Y pasarla a `PantallaMiLista`:

```kotlin
        Pantalla.EnLaLista -> PantallaMiLista(
            ubicaciones = ubicacionesAsignadas,
            pasada = vinculacion.value?.pasadaEtiqueta.orEmpty(),
            operario = vinculacion.value?.operarioNombre.orEmpty(),
            actualizando = actualizandoLista,
            avisoDeActualizacion = avisoDeActualizacion,
            pendientes = pendientes,
            estadoDeSubida = estadoDeSubida,
            oscuro = oscuro,
            version = version,
            alCambiarTema = alCambiarTema,
            alActualizar = { alcance.launch { refrescarListaAsignada() } },
            alSubir = {
                if (subiendo.compareAndSet(false, true)) {
                    alcance.launch {
                        try {
                            subir(loPidioElOperario = true)
                        } finally {
                            subiendo.set(false)
                        }
                    }
                }
            },
            alContar = { pantalla = Pantalla.Escaneando },
            alTocarProducto = { id ->
                pantalla = Pantalla.Escaneando
                contarPorId(id)
            },
        )
```

- [ ] **Step 4: Cablear el botón «Buscar» y su diálogo (Task 12, 18, 19)**

En la llamada a `PantallaEscaneo`, agregar:

```kotlin
                puedeBuscar = !hayAlgoAbierto,
                alBuscar = { buscando = true; resultadosDeBusqueda = emptyList() },
```

Y, junto al bloque de `if (ingresandoAMano) { DialogoCodigoAMano(...) }`, agregar:

```kotlin
            if (buscando) {
                DialogoBuscarProducto(
                    resultados = resultadosDeBusqueda,
                    alCambiarTexto = { texto ->
                        alcance.launch { resultadosDeBusqueda = contador.buscarTexto(texto) }
                    },
                    alElegir = { h ->
                        buscando = false
                        previos = emptyList()
                        alcance.launch {
                            previos = contador.conteosDe(h.articulo)
                            hallazgo = h
                        }
                    },
                    alIngresarAMano = {
                        buscando = false
                        ingresandoAMano = true
                    },
                    alCerrar = { buscando = false },
                )
            }
```

- [ ] **Step 5: Cablear «Cambiar de operario» (Task 13, 17)**

`PantallaMiLista` ya tiene el botón «Cambiar» y el parámetro `alIdentificarse` desde la Task 16 — acá falta darle su lógica. Agregar, en la llamada a `PantallaMiLista`, junto a `alCambiarTema`:

```kotlin
            alIdentificarse = {
                identificando = true
                errorDeIdentificacion = null
                cargandoOperarios = true
                alcance.launch {
                    val quien = base.vinculacionDao().actual() ?: return@launch
                    try {
                        val respuesta = ClienteServidor(quien.url, quien.token).operarios()
                        operariosParaIdentificar = respuesta.operarios
                    } catch (error: ErrorDeServidor) {
                        errorDeIdentificacion = error.message
                    } finally {
                        cargandoOperarios = false
                    }
                }
            },
```

(Este cambio agrega un parámetro `alIdentificarse: () -> Unit` a `PantallaMiLista` y un botón «Cambiar» que lo llama, junto al nombre del operario del Task 16 — si esa tarea no lo dejó ya cableado, sumarlo ahí: `TextButton(onClick = alIdentificarse) { Text("Cambiar") }` al lado del `Text(operario, ...)`.)

Y el diálogo, en el nivel superior de `App(...)` (fuera del `when (pantalla)`, para que se pueda abrir tanto desde Mi Lista como en cualquier otra pantalla sin duplicar estado):

```kotlin
    if (identificando) {
        DialogoIdentificarse(
            operarios = operariosParaIdentificar,
            cargando = cargandoOperarios,
            error = errorDeIdentificacion,
            alElegir = { nombre, pin ->
                alcance.launch {
                    val vinculador = Vinculador(base) { u, t -> ClienteServidor(u, t) }
                    when (val r = vinculador.identificar(nombre, pin)) {
                        is ResultadoDeVinculacion.Vinculado -> {
                            identificando = false
                            vinculacion.value = base.vinculacionDao().actual()
                            pantalla = Pantalla.EnLaLista
                            refrescarListaAsignada()
                        }
                        is ResultadoDeVinculacion.Fallo -> errorDeIdentificacion = r.mensaje
                    }
                }
            },
            alCerrar = { identificando = false },
        )
    }
```

- [ ] **Step 6: Compilar y correr toda la suite del módulo**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, todo el módulo `app` (y confirmar aparte con `:nucleo:test` que ese módulo también sigue en verde).

- [ ] **Step 7: Verificar en un celular real por USB**

Con `adb devices` mostrando el celular conectado, instalar un build de depuración y probar, en orden:

1. Tocar la tarjeta de un producto asignado en Mi Lista → se abre la ficha de conteo sin pasar por la cámara, y al confirmar el tilde aparece igual que si se hubiera escaneado.
2. Tocar «Buscar», escribir parte de una descripción → aparece el resultado, tocarlo cuenta.
3. Buscar un texto que no existe → aparece «Ingresarlo a mano», tocarlo abre el teclado de código a mano.
4. Dar de alta un producto nuevo y confirmar que en Mi Lista aparece con la etiqueta AGREGADO, y que sigue apareciendo después de tocar «Actualizar».
5. Tocar «Cambiar» en Mi Lista, elegir un operario sin PIN → se identifica directo y el reparto se actualiza.
6. Tocar «Cambiar», elegir un operario con PIN, probar con el PIN incorrecto (mensaje de error) y con el correcto (identifica).
7. Repetir con el celular sin WiFi en el paso 5: tiene que avisar el error de conexión, no cerrarse.

- [ ] **Step 8: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/MainActivity.kt
git commit -m "Cablea identificarse sin QR, contar tocando y buscar por texto en la pantalla principal"
```

---

## Self-Review

**Cobertura del spec:**
- A. Identificarse sin QR → Tasks 1, 2, 6, 7, 13, 17, 20.
- B1. Tocar la tarjeta en Mi Lista → Tasks 9, 10, 11, 16, 20.
- B2. Buscar por texto, con alta si no existe (vía «A mano») → Tasks 12, 18, 19, 20.
- C. Etiqueta AGREGADO (celular y panel) → Tasks 3, 4, 5, 6, 8, 9, 10, 11, 13, 16.
- Contrato compartido actualizado → Task 4.
- Migración de Room 5→6 → Task 8.

**Placeholders:** ninguno — cada paso trae el código completo, no una referencia a "hacer como en la Task N".

**Consistencia de tipos:** `Hallazgo.Encontrado` (no `Hallazgo?`) es el tipo que usan `buscarPorId`, `buscarTexto`, `DialogoBuscarProducto` y el cableado de `MainActivity`, de punta a punta. `OperarioParaIdentificar` es el mismo tipo en `ContratoApi.kt` (Task 6), `ClienteServidor.operarios()` (Task 7) y `DialogoIdentificarse` (Task 17). `ResultadoDeVinculacion` (ya existente) se reutiliza sin cambios para `Vinculador.identificar` (Task 13): no hace falta un tipo de resultado nuevo.
