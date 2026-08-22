# Login del panel — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sumarle al panel varias cuentas con usuario, contraseña y un
segundo factor TOTP, protegiendo todos los endpoints de `panel.router`
sin tocar el flujo de vinculación de los celulares.

**Architecture:** Sesión por token opaco guardado en SQLite (mismo
patrón que `operario.token_dispositivo`), cookie `httponly` sin
`secure`. `panel.router` gana un `Depends` a nivel de router que exige
esa cookie. Un router nuevo, `app/api/auth.py`, queda sin autenticación
—login, logout, «quién soy», y el alta de cuentas—. El frontend gana
tres pantallas nuevas (primera cuenta, login, Usuarios) controladas con
el mismo mecanismo `vista`/`oculta` que ya separa las pestañas.

**Tech Stack:** FastAPI, SQLite, `pyotp` (nuevo), `segno` (ya en uso),
`hashlib.pbkdf2_hmac` de la librería estándar. Panel: HTML/CSS/JS sin
dependencias, sin cambios.

**Spec:** `docs/superpowers/specs/2026-08-22-login-panel-design.md`

## Global Constraints

- Cantidades en milésimas, importes en centavos, siempre `int` — no aplica a este plan (no toca cantidades ni importes).
- `stock_sistema` y `costo_unitario` nunca salen por `/api/dispositivo/*` — no aplica: este plan no toca `dispositivos.router`.
- Nada externo en el navegador: ni CDN, ni fuentes, ni librerías remotas.
- Todo dato del servidor se escapa antes de ir al HTML (`esc()` en `app.js`).
- Fechas ISO 8601 UTC como texto, únicamente desde `app/reloj.py`.
- Nada se edita ni se borra — no aplica a cuentas de panel (dar de baja es un `activo = 0`, no un DELETE, igual que `operario`).
- Textos en castellano rioplatense, sin jerga técnica, también en los mensajes de error.
- Mensajes de commit en castellano, en presente, describiendo el efecto.
- El token de sesión viaja en una cookie `httponly`, `samesite=lax`, **sin** `secure` (el panel se sirve por HTTP plano).
- El QR del secreto TOTP se muestra **una sola vez**, en la respuesta de `POST /api/auth/cuentas`. No existe ningún endpoint para volver a pedirlo.
- `dispositivos.router` y `GET /app.apk` quedan completamente afuera de esta autenticación.

---

## Task 1: Esquema nuevo y dependencia `pyotp`

**Files:**
- Modify: `servidor/app/esquema.sql`
- Modify: `servidor/requirements.txt`
- Test: `servidor/tests/test_esquema.py` (crear)

**Interfaces:**
- Produces: tablas `cuenta_panel(id, usuario, clave_hash, otp_secreto, activo)` y `sesion_panel(token, cuenta_id, creado_en)`, disponibles para las Tasks 3 y 4.

- [ ] **Step 1: Escribir el test que falla**

Crear `servidor/tests/test_esquema.py`:

```python
def test_el_esquema_crea_las_tablas_de_cuentas_de_panel(con):
    tablas = {
        fila["name"]
        for fila in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert "cuenta_panel" in tablas
    assert "sesion_panel" in tablas
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_esquema.py -v --rootdir .`
Expected: FAIL — `assert "cuenta_panel" in tablas` es falso, la tabla no existe todavía.

- [ ] **Step 3: Agregar las tablas al esquema**

En `servidor/app/esquema.sql`, después de la tabla `evento_auditoria` (antes del bloque `INSERT OR IGNORE INTO unidad`), agregar:

```sql
-- Cuentas para entrar al panel. Separadas de `operario` a propósito: son
-- dos identidades sin relación entre sí, y compartir tabla o vocabulario
-- las confundiría la primera vez que alguien lea el esquema.
CREATE TABLE IF NOT EXISTS cuenta_panel (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario     TEXT NOT NULL UNIQUE,
    clave_hash  TEXT NOT NULL,
    otp_secreto TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sesion_panel (
    token      TEXT PRIMARY KEY,
    cuenta_id  INTEGER NOT NULL REFERENCES cuenta_panel(id),
    creado_en  TEXT NOT NULL
);
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_esquema.py -v --rootdir .`
Expected: PASS

- [ ] **Step 5: Sumar `pyotp` a `requirements.txt` e instalarlo**

En `servidor/requirements.txt`, agregar una línea (mantener el orden alfabético que ya tienen las demás si aplica; si no, al final):

```
pyotp==2.9.0
```

Run: `cd servidor && .venv\Scripts\python.exe -m pip install -r requirements.txt`
Expected: instala `pyotp` sin errores.

- [ ] **Step 6: Correr toda la suite para confirmar que nada se rompió**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: todos los tests existentes siguen en verde (esta tarea no tocó ningún endpoint todavía).

- [ ] **Step 7: Commit**

```bash
git add servidor/app/esquema.sql servidor/requirements.txt servidor/tests/test_esquema.py
git commit -m "Suma las tablas de cuentas de panel y la dependencia pyotp"
```

---

## Task 2: Servicio de autenticación (hash de contraseña y TOTP)

**Files:**
- Create: `servidor/app/servicios/autenticacion.py`
- Test: `servidor/tests/test_autenticacion.py`

**Interfaces:**
- Produces: `hashear_clave(clave: str) -> str`, `verificar_clave(clave: str, clave_hash: str) -> bool`, `generar_secreto_totp() -> str`, `verificar_totp(secreto: str, codigo: str) -> bool`, `otpauth_url(secreto: str, usuario: str) -> str`. Los usa la Task 3 (`crear`, verificación de login) y la Task 4 (endpoint de login y de alta de cuenta).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `servidor/tests/test_autenticacion.py`:

```python
import pyotp

from app.servicios import autenticacion


def test_una_clave_hasheada_se_verifica_con_la_misma_clave():
    hash_ = autenticacion.hashear_clave("secreta123")

    assert autenticacion.verificar_clave("secreta123", hash_)


def test_una_clave_distinta_no_verifica():
    hash_ = autenticacion.hashear_clave("secreta123")

    assert not autenticacion.verificar_clave("otra-clave", hash_)


def test_dos_hashes_de_la_misma_clave_son_distintos():
    """La sal tiene que ser al azar en cada llamada, o dos cuentas con la
    misma contraseña quedarían con el mismo hash, delatándolo."""
    assert autenticacion.hashear_clave("secreta123") != autenticacion.hashear_clave("secreta123")


def test_un_hash_con_otro_formato_no_verifica_en_vez_de_explotar():
    assert not autenticacion.verificar_clave("cualquiera", "no-es-un-hash-valido")


def test_el_secreto_totp_generado_es_valido_para_pyotp():
    secreto = autenticacion.generar_secreto_totp()

    codigo = pyotp.TOTP(secreto).now()

    assert autenticacion.verificar_totp(secreto, codigo)


def test_un_codigo_incorrecto_no_verifica():
    secreto = autenticacion.generar_secreto_totp()

    assert not autenticacion.verificar_totp(secreto, "000000")


def test_la_url_otpauth_lleva_el_usuario_y_el_nombre_del_sistema():
    secreto = autenticacion.generar_secreto_totp()

    url = autenticacion.otpauth_url(secreto, "pablo")

    assert url.startswith("otpauth://totp/")
    assert "pablo" in url
    assert "Control%20de%20Stock" in url or "Control+de+Stock" in url
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_autenticacion.py -v --rootdir .`
Expected: FAIL — `ModuleNotFoundError` o `ImportError`, `app.servicios.autenticacion` no existe todavía.

- [ ] **Step 3: Implementar el servicio**

Crear `servidor/app/servicios/autenticacion.py`:

```python
"""Hash de contraseña y verificación TOTP, sin tocar la base ni el request.

Funciones puras a propósito: son las dos piezas de este sistema donde un
error sale más caro que en cualquier otro lado del proyecto, y probarlas
solas —sin la base, sin el servidor— es lo que las hace fáciles de
revisar.
"""

import hashlib
import secrets

import pyotp

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 260_000
EMISOR = "Control de Stock"


def hashear_clave(clave: str) -> str:
    """Un string autodescriptivo: algoritmo, iteraciones, sal y hash, juntos.

    Autodescriptivo para que el día que las iteraciones suban, los hashes
    viejos se sigan verificando igual: la función lee sus propios
    parámetros del string en vez de asumirlos fijos.
    """
    sal = secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal.encode("utf-8"), ITERACIONES
    )
    return f"{ALGORITMO}${ITERACIONES}${sal}${derivada.hex()}"


def verificar_clave(clave: str, clave_hash: str) -> bool:
    """False ante cualquier hash con forma rara, en vez de tirar una excepción."""
    partes = clave_hash.split("$")
    if len(partes) != 4:
        return False
    algoritmo, iteraciones, sal, derivada_hex = partes
    if algoritmo != ALGORITMO:
        return False
    try:
        iteraciones = int(iteraciones)
    except ValueError:
        return False

    calculada = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal.encode("utf-8"), iteraciones
    )
    return secrets.compare_digest(calculada.hex(), derivada_hex)


def generar_secreto_totp() -> str:
    return pyotp.random_base32()


def verificar_totp(secreto: str, codigo: str) -> bool:
    """Admite un paso de 30 segundos de diferencia de reloj para cada lado."""
    return pyotp.TOTP(secreto).verify(codigo, valid_window=1)


def otpauth_url(secreto: str, usuario: str) -> str:
    """La URL que codifica el QR de alta, para cualquier app autenticadora."""
    return pyotp.totp.TOTP(secreto).provisioning_uri(name=usuario, issuer_name=EMISOR)
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_autenticacion.py -v --rootdir .`
Expected: PASS, los 7 tests.

- [ ] **Step 5: Commit**

```bash
git add servidor/app/servicios/autenticacion.py servidor/tests/test_autenticacion.py
git commit -m "Agrega el servicio de hash de contraseña y verificación TOTP"
```

---

## Task 3: Repositorio `cuentas_panel`

**Files:**
- Create: `servidor/app/repos/cuentas_panel.py`
- Test: `servidor/tests/test_repos_cuentas_panel.py`

**Interfaces:**
- Consumes: `autenticacion.hashear_clave`, `autenticacion.generar_secreto_totp` (Task 2), `reloj.ahora` (ya existe).
- Produces: `crear(con, usuario, clave) -> dict` (con `id`, `usuario`, `otp_secreto`), `existe_alguna(con) -> bool`, `por_usuario(con, usuario) -> dict | None` (con `clave_hash`, `otp_secreto`, para verificar login), `listar(con) -> list[dict]` (sin `clave_hash` ni `otp_secreto`), `desactivar(con, cuenta_id)`, `crear_sesion(con, cuenta_id) -> str`, `sesion_valida(con, token) -> dict | None` (con `id`, `usuario`), `borrar_sesion(con, token)`. Los usa la Task 4.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `servidor/tests/test_repos_cuentas_panel.py`:

```python
import pytest

from app.repos import cuentas_panel


def test_crear_devuelve_el_secreto_totp_en_texto_plano(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert creada["usuario"] == "pablo"
    assert creada["otp_secreto"]
    assert "id" in creada


def test_no_se_puede_repetir_usuario(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    with pytest.raises(ValueError, match="pablo"):
        cuentas_panel.crear(con, "pablo", "otra-clave")


def test_sin_usuario_no_se_puede_crear(con):
    with pytest.raises(ValueError):
        cuentas_panel.crear(con, "", "clave-larga-123")


def test_sin_clave_no_se_puede_crear(con):
    with pytest.raises(ValueError):
        cuentas_panel.crear(con, "pablo", "")


def test_existe_alguna_es_falso_sin_cuentas(con):
    assert cuentas_panel.existe_alguna(con) is False


def test_existe_alguna_es_verdadero_con_una_cuenta(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert cuentas_panel.existe_alguna(con) is True


def test_por_usuario_trae_el_hash_y_el_secreto(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuenta = cuentas_panel.por_usuario(con, "pablo")

    assert cuenta["usuario"] == "pablo"
    assert cuenta["clave_hash"]
    assert cuenta["otp_secreto"]


def test_por_usuario_inexistente_devuelve_none(con):
    assert cuentas_panel.por_usuario(con, "nadie") is None


def test_listar_no_trae_el_hash_ni_el_secreto(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    listado = cuentas_panel.listar(con)

    assert listado == [{"id": listado[0]["id"], "usuario": "pablo", "activo": 1}]


def test_desactivar_saca_la_cuenta_del_listado(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuentas_panel.desactivar(con, creada["id"])

    assert cuentas_panel.listar(con) == []


def test_desactivar_una_cuenta_inexistente_avisa(con):
    with pytest.raises(ValueError):
        cuentas_panel.desactivar(con, 999)


def test_una_cuenta_desactivada_no_aparece_por_usuario(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cuentas_panel.desactivar(con, creada["id"])

    assert cuentas_panel.por_usuario(con, "pablo") is None


def test_crear_sesion_y_validarla(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    token = cuentas_panel.crear_sesion(con, creada["id"])
    validada = cuentas_panel.sesion_valida(con, token)

    assert validada == {"id": creada["id"], "usuario": "pablo"}


def test_un_token_que_no_existe_no_es_valido(con):
    assert cuentas_panel.sesion_valida(con, "token-inventado") is None


def test_borrar_sesion_la_invalida(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])

    cuentas_panel.borrar_sesion(con, token)

    assert cuentas_panel.sesion_valida(con, token) is None


def test_una_sesion_vencida_no_es_valida(con, monkeypatch):
    from datetime import datetime, timedelta, timezone

    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])

    vencida = (datetime.now(timezone.utc) - timedelta(days=31)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    con.execute(
        "UPDATE sesion_panel SET creado_en = ? WHERE token = ?", (vencida, token)
    )
    con.commit()

    assert cuentas_panel.sesion_valida(con, token) is None
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_repos_cuentas_panel.py -v --rootdir .`
Expected: FAIL — `ModuleNotFoundError`, `app.repos.cuentas_panel` no existe.

- [ ] **Step 3: Implementar el repositorio**

Crear `servidor/app/repos/cuentas_panel.py`:

```python
"""Cuentas del panel y sus sesiones de login.

Separado de `operarios.py` a propósito: el operario que escanea códigos
y la cuenta que administra el panel son identidades sin relación entre
sí, y compartir tabla o vocabulario las confundiría.
"""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from app import reloj
from app.servicios import autenticacion

CAMPOS_PUBLICOS = "id, usuario, activo"
DIAS_DE_SESION = 30


def crear(con, usuario, clave):
    """Da de alta una cuenta con un secreto TOTP nuevo.

    Devuelve el secreto en texto plano: es la única vez que existe fuera
    de la base, porque el llamador lo necesita para armar el QR de alta.
    Nadie vuelve a pedirlo después.
    """
    usuario = (usuario or "").strip() if isinstance(usuario, str) else ""
    if not usuario:
        raise ValueError("La cuenta necesita un usuario")
    if not clave:
        raise ValueError("La cuenta necesita una contraseña")

    clave_hash = autenticacion.hashear_clave(clave)
    secreto = autenticacion.generar_secreto_totp()

    try:
        with con:
            cursor = con.execute(
                "INSERT INTO cuenta_panel (usuario, clave_hash, otp_secreto) "
                "VALUES (?, ?, ?)",
                (usuario, clave_hash, secreto),
            )
            cuenta_id = cursor.lastrowid
    except sqlite3.IntegrityError as error:
        if "cuenta_panel.usuario" in str(error):
            raise ValueError(f"Ya existe una cuenta con el usuario «{usuario}»") from error
        raise

    return {"id": cuenta_id, "usuario": usuario, "otp_secreto": secreto}


def existe_alguna(con):
    return con.execute("SELECT 1 FROM cuenta_panel LIMIT 1").fetchone() is not None


def por_usuario(con, usuario):
    """Con clave_hash y otp_secreto: solo para verificar un login, nunca se expone."""
    fila = con.execute(
        "SELECT id, usuario, clave_hash, otp_secreto FROM cuenta_panel "
        "WHERE usuario = ? AND activo = 1",
        (usuario,),
    ).fetchone()
    return dict(fila) if fila else None


def listar(con):
    filas = con.execute(
        f"SELECT {CAMPOS_PUBLICOS} FROM cuenta_panel WHERE activo = 1 ORDER BY usuario"
    ).fetchall()
    return [dict(fila) for fila in filas]


def desactivar(con, cuenta_id):
    with con:
        cursor = con.execute(
            "UPDATE cuenta_panel SET activo = 0 WHERE id = ?", (cuenta_id,)
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No existe la cuenta {cuenta_id}")


def crear_sesion(con, cuenta_id):
    token = secrets.token_urlsafe(32)
    with con:
        con.execute(
            "INSERT INTO sesion_panel (token, cuenta_id, creado_en) VALUES (?, ?, ?)",
            (token, cuenta_id, reloj.ahora()),
        )
    return token


def sesion_valida(con, token):
    """La cuenta dueña de esta sesión, o None si no existe, venció, o la cuenta se dio de baja."""
    fila = con.execute(
        "SELECT s.creado_en, c.id, c.usuario, c.activo "
        "FROM sesion_panel s JOIN cuenta_panel c ON c.id = s.cuenta_id "
        "WHERE s.token = ?",
        (token,),
    ).fetchone()
    if fila is None or not fila["activo"]:
        return None

    creado = datetime.strptime(fila["creado_en"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    if datetime.now(timezone.utc) - creado > timedelta(days=DIAS_DE_SESION):
        return None

    return {"id": fila["id"], "usuario": fila["usuario"]}


def borrar_sesion(con, token):
    with con:
        con.execute("DELETE FROM sesion_panel WHERE token = ?", (token,))
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_repos_cuentas_panel.py -v --rootdir .`
Expected: PASS, los 16 tests.

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/cuentas_panel.py servidor/tests/test_repos_cuentas_panel.py
git commit -m "Agrega el repositorio de cuentas y sesiones del panel"
```

---

## Task 4: Router de autenticación y protección de `panel.router`

Esta tarea rompe a propósito, en el Step 3, la suite completa de
`test_api.py` y `test_panel_estatico.py`: es el punto donde
`panel.router` empieza a exigir sesión. La Task 5, inmediatamente
después, la repara. No hacer commit entre el Step 3 y el final de la
Task 5 — quedaría un commit con ~500 tests rojos.

**Files:**
- Create: `servidor/app/api/auth.py`
- Modify: `servidor/app/api/panel.py:6,13` (imports y línea del `router`)
- Modify: `servidor/app/main.py:11,48-49` (imports e `include_router`)
- Test: `servidor/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `cuentas_panel.*` (Task 3), `autenticacion.*` (Task 2), `vinculacion.svg` (ya existe en `app/servicios/vinculacion.py`).
- Produces: `verificar_sesion(request: Request) -> dict`, la dependencia que usa `panel.router`. Endpoints `GET /api/auth/estado`, `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/cuentas`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `servidor/tests/test_auth_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

import pyotp

from app.main import crear_app


@pytest.fixture
def cliente_sin_loguear(tmp_path):
    """A diferencia del `cliente` de los demás archivos, este no se loguea:
    es el que hace falta para probar el login en sí y los 401."""
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


def test_estado_sin_cuentas(cliente_sin_loguear):
    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": False, "usuario": None, "hay_cuentas": False}


def _crear_primera_cuenta(cliente, usuario="pablo", clave="clave-larga-123"):
    respuesta = cliente.post(
        "/api/auth/cuentas", json={"usuario": usuario, "clave": clave}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_se_puede_crear_la_primera_cuenta_sin_sesion(cliente_sin_loguear):
    cuerpo = _crear_primera_cuenta(cliente_sin_loguear)

    assert cuerpo["usuario"] == "pablo"
    assert cuerpo["otpauth_url"].startswith("otpauth://")
    assert "<svg" in cuerpo["qr_svg"]


def test_una_segunda_cuenta_sin_sesion_se_rechaza(cliente_sin_loguear):
    _crear_primera_cuenta(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "otra", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 401


def test_login_con_los_tres_datos_correctos(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    assert respuesta.status_code == 200
    assert "sesion_panel" in respuesta.cookies


def test_login_con_clave_incorrecta(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "otra-clave", "codigo_otp": codigo},
    )

    assert respuesta.status_code == 401


def test_login_con_codigo_otp_incorrecto(cliente_sin_loguear):
    _crear_primera_cuenta(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": "000000"},
    )

    assert respuesta.status_code == 401


def test_login_con_usuario_inexistente(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "nadie", "clave": "loquesea", "codigo_otp": "000000"},
    )

    assert respuesta.status_code == 401


def test_estado_despues_de_loguearse(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": True, "usuario": "pablo", "hay_cuentas": True}


def test_logout_invalida_la_sesion(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    cliente_sin_loguear.post("/api/auth/logout")

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()
    assert cuerpo["logueado"] is False


def test_una_cuenta_ya_logueada_puede_crear_otra(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana", "clave": "clave-larga-789"}
    )

    assert respuesta.status_code == 200


def test_endpoint_del_panel_sin_sesion_da_401(cliente_sin_loguear):
    assert cliente_sin_loguear.get("/api/sesiones").status_code == 401


def test_endpoint_del_panel_con_sesion_funciona(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    assert cliente_sin_loguear.get("/api/sesiones").status_code == 200


def test_dispositivos_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    """La vinculación de celulares no tiene nada que ver con esto."""
    respuesta = cliente_sin_loguear.post(
        "/api/dispositivo/vincular", headers={"X-Token": "token-inventado"}
    )

    assert respuesta.status_code != 401


def test_app_apk_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.get("/app.apk")

    assert respuesta.status_code != 401
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_auth_api.py -v --rootdir .`
Expected: FAIL en la mayoría — `/api/auth/*` no existe (404), y los que pegan a `/api/sesiones` sin sesión hoy dan 200 en vez de 401 (`test_endpoint_del_panel_sin_sesion_da_401` falla porque HOY no hay protección).

- [ ] **Step 3: Implementar el router de autenticación**

Crear `servidor/app/api/auth.py`:

```python
"""Login del panel: cuentas, sesión, y el segundo factor por TOTP.

Sin autenticación —es el único lugar donde no puede haberla, por
definición—. `panel.router` importa `verificar_sesion` de acá para
protegerse a sí mismo.
"""

from fastapi import APIRouter, HTTPException, Request, Response

from app.repos import cuentas_panel
from app.servicios import autenticacion, vinculacion

router = APIRouter(prefix="/api/auth")

COOKIE_SESION = "sesion_panel"
SEGUNDOS_DE_SESION = 60 * 60 * 24 * 30


def _con(request):
    return request.app.state.con


def verificar_sesion(request: Request) -> dict:
    """La dependencia que protege `panel.router`: quién está logueado, o 401."""
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        raise HTTPException(status_code=401, detail="No hay sesión iniciada")

    cuenta = cuentas_panel.sesion_valida(_con(request), token)
    if cuenta is None:
        raise HTTPException(status_code=401, detail="La sesión no es válida o venció")

    return cuenta


@router.get("/estado")
def estado(request: Request):
    con = _con(request)
    token = request.cookies.get(COOKIE_SESION)
    cuenta = cuentas_panel.sesion_valida(con, token) if token else None

    return {
        "logueado": cuenta is not None,
        "usuario": cuenta["usuario"] if cuenta else None,
        "hay_cuentas": cuentas_panel.existe_alguna(con),
    }


@router.post("/login")
async def login(request: Request, response: Response):
    cuerpo = await request.json()
    con = _con(request)

    usuario = (cuerpo.get("usuario") or "").strip()
    clave = cuerpo.get("clave") or ""
    codigo_otp = cuerpo.get("codigo_otp") or ""

    # Un solo mensaje para las tres formas de fallar: no le confirma a
    # quien prueba a ciegas cuál de los tres datos acertó.
    credenciales_invalidas = HTTPException(
        status_code=401, detail="Usuario, contraseña o código incorrecto"
    )

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is None:
        raise credenciales_invalidas
    if not autenticacion.verificar_clave(clave, cuenta["clave_hash"]):
        raise credenciales_invalidas
    if not autenticacion.verificar_totp(cuenta["otp_secreto"], codigo_otp):
        raise credenciales_invalidas

    token = cuentas_panel.crear_sesion(con, cuenta["id"])
    response.set_cookie(
        COOKIE_SESION, token,
        httponly=True, samesite="lax", max_age=SEGUNDOS_DE_SESION,
    )
    return {"usuario": cuenta["usuario"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_SESION)
    if token:
        cuentas_panel.borrar_sesion(_con(request), token)
    response.delete_cookie(COOKIE_SESION)
    return {"ok": True}


@router.post("/cuentas")
async def crear_cuenta(request: Request):
    """Sin cuentas todavía, se permite sin sesión: es el arranque. Con al
    menos una ya creada, exige sesión válida como cualquier otro endpoint
    del panel — acá adentro, con un `if`, porque expresarlo como una
    dependencia de FastAPI sería más confuso que la condición misma."""
    con = _con(request)
    if cuentas_panel.existe_alguna(con):
        verificar_sesion(request)

    cuerpo = await request.json()
    try:
        creada = cuentas_panel.crear(con, cuerpo.get("usuario"), cuerpo.get("clave"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    otpauth = autenticacion.otpauth_url(creada["otp_secreto"], creada["usuario"])
    return {
        "id": creada["id"],
        "usuario": creada["usuario"],
        "otpauth_url": otpauth,
        "qr_svg": vinculacion.svg(otpauth),
    }
```

- [ ] **Step 4: Proteger `panel.router`**

En `servidor/app/api/panel.py`, línea 6, cambiar:

```python
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
```

por:

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
```

Y agregar, justo debajo del bloque de imports de `app` (después de la línea `from app.servicios import exportacion, importacion, novedades, reparto, tablero, vinculacion`):

```python
from app.api.auth import verificar_sesion
```

Y en la línea 13, cambiar:

```python
router = APIRouter(prefix="/api")
```

por:

```python
router = APIRouter(prefix="/api", dependencies=[Depends(verificar_sesion)])
```

- [ ] **Step 5: Registrar el router nuevo en `main.py`**

En `servidor/app/main.py`, línea 11, cambiar:

```python
from app.api import dispositivos, panel
```

por:

```python
from app.api import auth, dispositivos, panel
```

Y en las líneas 48-49, cambiar:

```python
    app.include_router(panel.router)
    app.include_router(dispositivos.router)
```

por:

```python
    app.include_router(auth.router)
    app.include_router(panel.router)
    app.include_router(dispositivos.router)
```

- [ ] **Step 6: Correr los tests de esta tarea y confirmar que pasan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_auth_api.py -v --rootdir .`
Expected: PASS, los 14 tests.

- [ ] **Step 7: Correr toda la suite y confirmar que se rompió como se esperaba**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: cientos de fallos en `test_api.py`, `test_panel_estatico.py` y `test_contrato.py` — todos con 401 en vez del código que esperaban. **Es lo esperado en este punto**, la Task 5 los repara. No hacer commit todavía.

---

## Task 5: Autenticar la fixture compartida de los tests existentes

**Files:**
- Modify: `servidor/tests/conftest.py`
- Modify: `servidor/tests/test_api.py:7-11`
- Modify: `servidor/tests/test_panel_estatico.py:14-18`
- Modify: `servidor/tests/test_contrato.py:52-65`

**Interfaces:**
- Consumes: `cuentas_panel.crear`, `cuentas_panel.crear_sesion` (Task 3).
- Produces: `loguear(cliente)`, la función que usan las tres fixtures de esta tarea.

- [ ] **Step 1: Agregar el helper de login a `conftest.py`**

En `servidor/tests/conftest.py`, agregar al final:

```python
def loguear(cliente):
    """Crea una cuenta de panel directo contra la base del `TestClient` ya
    arrancado, y le pisa la cookie de sesión.

    Directo contra la base y no vía `/api/auth/*`: encadenar el login real
    en cada uno de los cientos de tests que ya existían antes de esta
    cuenta los volvería frágiles ante cualquier cambio futuro del propio
    flujo de login, que ya tiene sus propios tests en `test_auth_api.py`.
    """
    from app.repos import cuentas_panel

    con = cliente.app.state.con
    creada = cuentas_panel.crear(con, "prueba", "clave-de-prueba-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])
    cliente.cookies.set("sesion_panel", token)
```

- [ ] **Step 2: Usarlo en la fixture `cliente` de `test_api.py`**

En `servidor/tests/test_api.py`, líneas 7-11, cambiar:

```python
@pytest.fixture
def cliente(tmp_path):
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente
```

por:

```python
@pytest.fixture
def cliente(tmp_path):
    from conftest import loguear

    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        loguear(cliente)
        yield cliente
```

- [ ] **Step 3: Lo mismo en `test_panel_estatico.py`**

En `servidor/tests/test_panel_estatico.py`, líneas 14-18, aplicar el mismo cambio que en el Step 2 (mismo patrón exacto: agregar `from conftest import loguear` e insertar `loguear(cliente)` antes del `yield`).

- [ ] **Step 4: Lo mismo en la fixture `vivo` de `test_contrato.py`**

En `servidor/tests/test_contrato.py`, dentro de la fixture `vivo` (líneas 52-65), después de la línea `with TestClient(app) as c:`, agregar como primera línea del bloque:

```python
    with TestClient(app) as c:
        from conftest import loguear
        loguear(c)

        sesion = c.post("/api/sesiones", json={"nombre": "Contrato"}).json()
```

(la línea `sesion = ...` ya existe; solo se agregan las dos líneas de arriba antes de ella).

- [ ] **Step 5: Correr toda la suite y confirmar que vuelve a estar verde**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: PASS, todos los tests — los que ya existían antes de esta rama, más los nuevos de `test_esquema.py`, `test_autenticacion.py`, `test_repos_cuentas_panel.py` y `test_auth_api.py`.

- [ ] **Step 6: Commit**

Este commit incluye el trabajo de la Task 4 y de esta tarea juntas —es el primer punto desde el Step 3 de la Task 4 donde la suite vuelve a estar verde—:

```bash
git add servidor/app/api/auth.py servidor/app/api/panel.py servidor/app/main.py \
        servidor/tests/test_auth_api.py servidor/tests/conftest.py \
        servidor/tests/test_api.py servidor/tests/test_panel_estatico.py \
        servidor/tests/test_contrato.py
git commit -m "Protege el panel con login: cuentas, sesión y TOTP"
```

---

## Task 6: Listar y dar de baja cuentas desde el panel autenticado

**Files:**
- Modify: `servidor/app/api/panel.py`
- Test: `servidor/tests/test_api.py` (agregar al final)

**Interfaces:**
- Consumes: `cuentas_panel.listar`, `cuentas_panel.desactivar` (Task 3). Ya protegidos por el `Depends` a nivel de router de la Task 4 — no hace falta nada especial acá.
- Produces: `GET /api/usuarios`, `POST /api/usuarios/{cuenta_id}/desactivar`. Los usa la Task 8 (frontend).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `servidor/tests/test_api.py`:

```python
def test_listar_usuarios_incluye_la_cuenta_de_prueba(cliente):
    cuerpo = cliente.get("/api/usuarios").json()

    assert any(u["usuario"] == "prueba" for u in cuerpo)
    assert "clave_hash" not in cuerpo[0]
    assert "otp_secreto" not in cuerpo[0]


def test_dar_de_baja_un_usuario(cliente):
    creada = cliente.post(
        "/api/auth/cuentas", json={"usuario": "temporal", "clave": "clave-larga-123"}
    ).json()

    respuesta = cliente.post(f"/api/usuarios/{creada['id']}/desactivar")

    assert respuesta.status_code == 200
    usuarios = cliente.get("/api/usuarios").json()
    assert not any(u["usuario"] == "temporal" for u in usuarios)


def test_dar_de_baja_un_usuario_inexistente_da_404(cliente):
    assert cliente.post("/api/usuarios/999999/desactivar").status_code == 404
```

- [ ] **Step 2: Correr los tests y confirmar que fallan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_api.py -k usuario -v --rootdir .`
Expected: FAIL — 404, las rutas no existen todavía.

- [ ] **Step 3: Agregar los endpoints**

En `servidor/app/api/panel.py`, agregar el import de `cuentas_panel` a la línea de imports de `app.repos` (línea 10):

```python
from app.repos import asignaciones, cuentas_panel, operarios, pasada_item, sesiones
```

Y agregar, cerca de los endpoints de `/operarios` (después del bloque de `@router.get("/operarios/{operario_id}/qr")`, antes de `/sesiones/{sesion_id}/exportar/{tipo_exportacion}`):

```python
@router.get("/usuarios")
def listar_usuarios(request: Request):
    return cuentas_panel.listar(_con(request))


@router.post("/usuarios/{cuenta_id}/desactivar")
def desactivar_usuario(cuenta_id: int, request: Request):
    try:
        cuentas_panel.desactivar(_con(request), cuenta_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return {"activo": False}
```

- [ ] **Step 4: Correr los tests y confirmar que pasan**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_api.py -k usuario -v --rootdir .`
Expected: PASS, los 3 tests.

- [ ] **Step 5: Correr toda la suite**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: PASS, todo.

- [ ] **Step 6: Commit**

```bash
git add servidor/app/api/panel.py servidor/tests/test_api.py
git commit -m "Agrega listar y dar de baja usuarios del panel"
```

---

## Task 7: Frontend — pantallas de primera cuenta y login, y el arranque protegido

**Files:**
- Modify: `servidor/panel/index.html`
- Modify: `servidor/panel/app.js`
- Modify: `servidor/panel/estilos.css`

**Interfaces:**
- Consumes: `GET /api/auth/estado`, `POST /api/auth/login`, `POST /api/auth/cuentas`, `POST /api/auth/logout` (Task 4).
- Produces: `mostrarSoloVista(nombre)`, `mostrarPanel()`, `cargarEstadoDeAuth()`, `arrancarPanel()` — la Task 8 los reusa para la pestaña Usuarios.

No hay test automático para esto —el panel no tiene infraestructura de tests de UI, más allá del chequeo de sintaxis de `app.js` y el guardián de escapado, que ya corren en `test_panel_estatico.py`—. Se verifica a mano en el navegador al final de la Task 8, con las dos pantallas ya completas.

- [ ] **Step 1: Agregar las pantallas al HTML**

En `servidor/panel/index.html`, cambiar el `<header>` (líneas 10-18) por:

```html
  <header class="barra">
    <h1>Control de Stock</h1>
    <div class="barra-derecha oculta" id="barra-derecha">
      <button id="cambiar-tema" class="secundario" type="button" aria-label="Cambiar entre tema claro y oscuro">
        🌓 Tema
      </button>
      <div id="sesion-actual" class="sesion-actual"></div>
      <span id="usuario-logueado" class="usuario-logueado"></span>
      <button id="cerrar-sesion-panel" class="secundario" type="button">Cerrar sesión</button>
    </div>
  </header>
```

Cambiar el `<nav>` (línea 20) de:

```html
  <nav class="pestanas">
```

a:

```html
  <nav class="pestanas oculta" id="pestanas">
```

Y agregar un botón más al final de esa lista de pestañas (después de `<button data-vista="sesiones">Sesiones</button>`, antes de `<button data-vista="novedades">Novedades</button>` o después, el orden entre estas dos no importa):

```html
    <button data-vista="usuarios">Usuarios</button>
```

Agregar, como primer hijo de `<main>` (antes de `<section id="vista-tablero" ...>`), las dos pantallas nuevas:

```html
    <section id="vista-primera-cuenta" class="vista oculta">
      <h2>Creá la primera cuenta del panel</h2>
      <p class="ayuda">
        Todavía no hay ninguna cuenta para entrar acá. Esta va a poder
        crear las demás después.
      </p>
      <form id="form-primera-cuenta">
        <input id="primera-cuenta-usuario" placeholder="Usuario" required>
        <input id="primera-cuenta-clave" type="password" placeholder="Contraseña" required>
        <button>Crear cuenta</button>
      </form>
      <p class="error" id="primera-cuenta-error"></p>
      <div id="primera-cuenta-qr-envoltorio" class="qr-otp oculta">
        <p class="ayuda">
          Escaneá este código con tu app autenticadora (Google
          Authenticator, Authy, o cualquier otra) antes de continuar.
          <strong>No se puede volver a mostrar.</strong>
        </p>
        <img id="primera-cuenta-qr" class="qr" alt="Código para configurar el segundo factor">
        <button id="primera-cuenta-continuar" type="button">Ya lo escaneé, entrar</button>
      </div>
    </section>

    <section id="vista-login" class="vista oculta">
      <h2>Iniciar sesión</h2>
      <form id="form-login">
        <input id="login-usuario" placeholder="Usuario" required>
        <input id="login-clave" type="password" placeholder="Contraseña" required>
        <input id="login-otp" placeholder="Código de 6 dígitos" required inputmode="numeric" pattern="[0-9]*">
        <button>Entrar</button>
      </form>
      <p class="error" id="login-error"></p>
    </section>

```

- [ ] **Step 2: Estilos mínimos**

En `servidor/panel/estilos.css`, agregar al final:

```css
.qr-otp {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.6rem;
  max-width: 32rem;
}

.error {
  color: var(--rojo);
}

.usuario-logueado {
  color: var(--tenue);
  font-size: 0.9rem;
}
```

`--rojo` y `--tenue` ya están definidas en `:root` de este archivo — se confirmó al escribir este plan.

- [ ] **Step 3: La lógica de arranque en `app.js`**

En `servidor/panel/app.js`, agregar una sección nueva justo antes de `// --- Tema --------`:

```javascript
// --- Autenticación -----------------------------------------------------------

/** Tapa todo —pestañas y contenido— salvo la vista de autenticación pedida. */
function mostrarSoloVista(nombre) {
  document.querySelectorAll(".vista").forEach((vista) => vista.classList.add("oculta"));
  $(`#vista-${nombre}`).classList.remove("oculta");
  $("#pestanas").classList.add("oculta");
  $("#barra-derecha").classList.add("oculta");
}

/** Vuelve al panel de siempre, con el Tablero como pestaña activa. */
function mostrarPanel() {
  document.querySelectorAll(".vista").forEach((vista) => vista.classList.add("oculta"));
  $("#vista-tablero").classList.remove("oculta");
  $("#pestanas").classList.remove("oculta");
  $("#barra-derecha").classList.remove("oculta");
}

/** Pide el estado de auth y muestra la pantalla que corresponda. Nunca
 * dispara ningún otro pedido: eso queda para `arrancarPanel()`, y solo si
 * hay sesión. */
async function cargarEstadoDeAuth() {
  const auth = await pedir("/api/auth/estado");
  estado.usuarioActual = auth.usuario;

  if (!auth.hay_cuentas) {
    mostrarSoloVista("primera-cuenta");
  } else if (!auth.logueado) {
    mostrarSoloVista("login");
  }
  return auth;
}

async function arrancarPanel() {
  mostrarPanel();
  try {
    await cargarSesiones();
    await cargarOperarios();
  } catch (error) {
    $("#sesion-actual").classList.add("error");
    $("#sesion-actual").textContent = `No se pudo conectar: ${error.message}`;
  }
}

async function enviarLogin(evento) {
  evento.preventDefault();
  $("#login-error").textContent = "";
  try {
    await pedir("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario: $("#login-usuario").value,
        clave: $("#login-clave").value,
        codigo_otp: $("#login-otp").value,
      }),
    });
    await arrancarPanel();
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
}

async function cerrarSesionDePanel() {
  await pedir("/api/auth/logout", { method: "POST" });
  location.reload();
}

/**
 * Crea una cuenta y muestra su QR una sola vez.
 *
 * `prefijo` identifica el juego de elementos a usar —`primera-cuenta` o
 * `usuario-nuevo`—, para no duplicar esta función pantalla por pantalla.
 */
async function crearCuentaYMostrarQr(prefijo, usuario, clave) {
  const errorEl = $(`#${prefijo}-error`);
  errorEl.textContent = "";
  try {
    const cuenta = await pedir("/api/auth/cuentas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, clave }),
    });
    // Como imagen y no como `innerHTML`: mismo criterio que el resto del
    // panel con los QR de vinculación, y evita tratar el SVG como marcado
    // vivo de la página.
    $(`#${prefijo}-qr`).src = `data:image/svg+xml;base64,${btoa(cuenta.qr_svg)}`;
    $(`#${prefijo}-qr-envoltorio`).classList.remove("oculta");
    $(`#${prefijo}-form`).classList.add("oculta");
    return cuenta;
  } catch (error) {
    errorEl.textContent = error.message;
    return null;
  }
}

function conectarEventosDeAuth() {
  $("#form-primera-cuenta").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    await crearCuentaYMostrarQr(
      "primera-cuenta",
      $("#primera-cuenta-usuario").value,
      $("#primera-cuenta-clave").value,
    );
  });

  $("#primera-cuenta-continuar").addEventListener("click", async () => {
    const auth = await cargarEstadoDeAuth();
    if (auth.logueado) await arrancarPanel();
  });

  $("#form-login").addEventListener("submit", enviarLogin);
  $("#cerrar-sesion-panel").addEventListener("click", cerrarSesionDePanel);
}
```

- [ ] **Step 4: Enganchar el arranque**

En `servidor/panel/app.js`, en `function conectarEventos() {`, agregar como primera línea del cuerpo:

```javascript
function conectarEventos() {
  conectarEventosDeAuth();
  $("#cambiar-tema").addEventListener("click", alternarTema);
  // ... el resto de la función sigue igual ...
```

(Solo se agrega la línea `conectarEventosDeAuth();`; el resto del cuerpo de `conectarEventos()` no cambia.)

Y cambiar la función `iniciar()` (al final del archivo), de:

```javascript
async function iniciar() {
  aplicarTemaGuardado();
  conectarEventos();
  try {
    await cargarSesiones();
    await cargarOperarios();
  } catch (error) {
    $("#sesion-actual").classList.add("error");
    $("#sesion-actual").textContent = `No se pudo conectar: ${error.message}`;
  }
  setInterval(refrescarSinRomper, 4000);
}
```

a:

```javascript
async function iniciar() {
  aplicarTemaGuardado();
  conectarEventos();
  const auth = await cargarEstadoDeAuth();
  if (auth.logueado) await arrancarPanel();
  setInterval(refrescarSinRomper, 4000);
}
```

- [ ] **Step 5: Chequeo de sintaxis**

Run: `cd servidor && node --check panel/app.js` (si `node` está instalado; si no, este chequeo lo hace igual `test_panel_estatico.py::test_el_javascript_del_panel_parsea` en el Step 6).

Expected: sin salida, código de salida 0.

- [ ] **Step 6: Correr la suite del panel**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_panel_estatico.py -q --rootdir .`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add servidor/panel/index.html servidor/panel/app.js servidor/panel/estilos.css
git commit -m "Suma las pantallas de primera cuenta y login al panel"
```

---

## Task 8: Frontend — pestaña Usuarios

**Files:**
- Modify: `servidor/panel/index.html`
- Modify: `servidor/panel/app.js`
- Modify: `servidor/tests/test_panel_estatico.py:75` (guardián de escapado)

**Interfaces:**
- Consumes: `GET /api/usuarios`, `POST /api/usuarios/{id}/desactivar` (Task 6), `crearCuentaYMostrarQr` (Task 7).

- [ ] **Step 1: Sumar `cuenta` a la lista blanca del guardián de escapado**

En `servidor/tests/test_panel_estatico.py`, línea 75, cambiar:

```python
DATOS_DEL_SERVIDOR = re.compile(r"\b(fila|sesion|operario|vista|resultado|estado|novedad)\.")
```

por:

```python
DATOS_DEL_SERVIDOR = re.compile(r"\b(fila|sesion|operario|vista|resultado|estado|novedad|cuenta)\.")
```

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests/test_panel_estatico.py::test_los_datos_del_servidor_se_escapan_antes_de_ir_al_html -v --rootdir .`
Expected: PASS (todavía no hay ningún `cuenta.` en `app.js`, así que este chequeo no tiene nada que auditar todavía — pasa trivialmente hasta el Step 3).

- [ ] **Step 2: Agregar la sección al HTML**

En `servidor/panel/index.html`, agregar antes de `</main>` (después de la sección `vista-novedades`):

```html
    <section id="vista-usuarios" class="vista oculta">
      <h2>Usuarios del panel</h2>
      <p class="ayuda">Quién puede entrar a este panel.</p>

      <form id="form-usuario-nuevo">
        <input id="usuario-nuevo-nombre" placeholder="Usuario" required>
        <input id="usuario-nuevo-clave" type="password" placeholder="Contraseña" required>
        <button>Agregar</button>
      </form>
      <p class="error" id="usuario-nuevo-error"></p>
      <div id="usuario-nuevo-qr-envoltorio" class="qr-otp oculta">
        <p class="ayuda">
          Escaneá este código con la app autenticadora de quien va a usar
          esta cuenta. <strong>No se puede volver a mostrar.</strong>
        </p>
        <img id="usuario-nuevo-qr" class="qr" alt="Código para configurar el segundo factor">
        <button id="usuario-nuevo-listo" type="button">Listo</button>
      </div>

      <ul id="lista-usuarios" class="lista"></ul>
    </section>
```

- [ ] **Step 3: La lógica en `app.js`**

Agregar, dentro de la sección `// --- Autenticación ---` creada en la Task 7 (al final de esa sección, después de `conectarEventosDeAuth`):

```javascript
function dibujarUsuario(cuenta) {
  const botonBaja = cuenta.usuario === estado.usuarioActual
    ? ""
    : `<button class="secundario" data-baja-usuario="${esc(cuenta.id)}">Dar de baja</button>`;
  return `<li>${esc(cuenta.usuario)} ${botonBaja}</li>`;
}

async function cargarUsuarios() {
  const lista = await pedir("/api/usuarios");
  $("#lista-usuarios").innerHTML = lista.map(dibujarUsuario).join("")
    || "<li>Todavía no hay usuarios.</li>";
}

async function darDeBajaUsuario(cuentaId) {
  if (!confirm("¿Dar de baja esta cuenta? No va a poder volver a entrar.")) return;
  await pedir(`/api/usuarios/${cuentaId}/desactivar`, { method: "POST" });
  await cargarUsuarios();
}
```

Y extender `conectarEventosDeAuth()` (agregado en la Task 7), sumando antes de su cierre:

```javascript
  $("#form-usuario-nuevo").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const cuenta = await crearCuentaYMostrarQr(
      "usuario-nuevo",
      $("#usuario-nuevo-nombre").value,
      $("#usuario-nuevo-clave").value,
    );
    if (cuenta) await cargarUsuarios();
  });

  $("#usuario-nuevo-listo").addEventListener("click", () => {
    $("#usuario-nuevo-qr-envoltorio").classList.add("oculta");
    $("#form-usuario-nuevo").classList.remove("oculta");
    $("#usuario-nuevo-nombre").value = "";
    $("#usuario-nuevo-clave").value = "";
  });

  $("#lista-usuarios").addEventListener("click", (evento) => {
    const id = evento.target.dataset.bajaUsuario;
    if (id) darDeBajaUsuario(id);
  });
```

- [ ] **Step 4: Enganchar la pestaña al cambio de vista**

En `servidor/panel/app.js`, dentro de `conectarEventos()`, en el bloque que ya escucha los clicks de `.pestanas button` (el que tiene `if (boton.dataset.vista === "novedades") cargarNovedades();`), agregar una línea más:

```javascript
      if (boton.dataset.vista === "novedades") cargarNovedades();
      if (boton.dataset.vista === "usuarios") cargarUsuarios();
```

- [ ] **Step 5: Correr toda la suite del servidor**

Run: `cd servidor && .venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: PASS, todo — incluido el guardián de escapado, ahora auditando `cuenta.usuario` y `cuenta.id` de verdad.

- [ ] **Step 6: Commit**

```bash
git add servidor/panel/index.html servidor/panel/app.js servidor/tests/test_panel_estatico.py
git commit -m "Agrega la pestaña Usuarios: alta, listado y baja de cuentas del panel"
```

---

## Task 9: Deuda conocida, CLAUDE.md, y verificación manual de punta a punta

**Files:**
- Modify: `docs/superpowers/deuda-conocida.md`
- Modify: `CLAUDE.md:59`

**Interfaces:**
- Ninguna — última tarea del plan.

- [ ] **Step 1: Actualizar la mención de `app/api/` en CLAUDE.md**

En `CLAUDE.md`, línea 59, cambiar:

```
servidor/app/api/         panel.py y dispositivos.py
```

por:

```
servidor/app/api/         panel.py, dispositivos.py y auth.py
```

- [ ] **Step 2: Anotar la deuda ya identificada en el diseño**

En `docs/superpowers/deuda-conocida.md`, agregar una sección nueva al final:

```markdown
## Login del panel

**No hay recuperación de OTP perdido.** Si quien usa una cuenta pierde el
teléfono con la app autenticadora, no hay forma de volver a ver el QR
—`POST /api/auth/cuentas` lo muestra una sola vez, a propósito, por
diseño—. Otra cuenta ya logueada tiene que dar de baja esa cuenta y
crearla de nuevo, o en su defecto cirugía directa sobre `inventario.db`.

**Sin rate limiting en el login.** Corre en la red de un depósito, no
expuesto a internet; se aceptó como riesgo razonable en el diseño de
2026-08-22, no por descuido.

**Ninguna cuenta puede cambiar su propia contraseña u OTP.** Se puede
crear una cuenta nueva y dar de baja la vieja. Si en el uso real esto
resulta incómodo, es una extensión chica y acotada.
```

- [ ] **Step 3: Levantar el servidor y probar el flujo completo a mano**

Run: `cd servidor && .venv\Scripts\python.exe iniciar.py`

En el navegador, contra la dirección que imprime la consola:

1. Confirmar que aparece la pantalla "Creá la primera cuenta del panel" —no el tablero—.
2. Crear una cuenta. Confirmar que aparece el QR.
3. Escanear el QR con una app autenticadora real (Google Authenticator, Authy, o similar) en un celular.
4. Tocar "Ya lo escaneé, entrar". Confirmar que aparece la pantalla de login, no el panel.
5. Loguearse con el usuario, la contraseña, y el código de 6 dígitos que muestra la app autenticadora en ese momento. Confirmar que entra al Tablero.
6. Ir a la pestaña Usuarios, crear una segunda cuenta, confirmar que muestra el QR.
7. Tocar "Cerrar sesión". Confirmar que vuelve a la pantalla de login —no a la de primera cuenta, porque ya hay cuentas creadas—.
8. Volver a entrar con la primera cuenta. Ir a Usuarios, dar de baja la segunda cuenta. Confirmar que desaparece del listado.
9. Confirmar que la propia cuenta logueada **no** tiene botón "Dar de baja" en su propia fila.
10. Recargar la página (F5) estando logueado. Confirmar que sigue logueado —la cookie de sesión sobrevive el recargo— y que entra directo al Tablero sin pedir login de nuevo.

- [ ] **Step 4: Confirmar que el celular sigue vinculándose sin tocar nada de esto**

Con el servidor de la Task 9 Step 3 todavía arriba y logueado en el panel:

1. Ir a Operarios, crear un operario, ver su QR de vinculación.
2. Con un celular real (o el emulado por USB si hay uno disponible), vincularlo escaneando ese QR.
3. Confirmar que la vinculación funciona igual que siempre —esto nunca pasó por `/api/auth/*`, y no debería notarse ningún cambio—.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/deuda-conocida.md
git commit -m "Anota la deuda conocida del login del panel"
```
