# Roles y recuperación de contraseña — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sumarle roles al login del panel (un superusuario fijo,
"Administrator", más cuentas de rol menor sin acceso a Usuarios), sacar
el OTP del login normal, agregar "Recordarme", y una recuperación de
contraseña de dos pasos (OTP para el superusuario, código por mail para
las demás).

**Architecture:** Se extiende el esquema (`rol` en `cuenta_panel`,
`recordar` en `sesion_panel`, tabla nueva `codigo_recuperacion`) y el
repo `cuentas_panel.py`. `auth.py` pierde el OTP del login y gana una
dependencia `requerir_superusuario` y dos endpoints de recuperación. Un
módulo nuevo, `servicios/correo.py`, manda el mail por `smtplib` con
credenciales en un archivo fuera del repo, mismo patrón que la firma del
APK. El frontend pierde la pantalla de alta de la primera cuenta, gana
"Recordarme" y la pantalla de recuperación, y oculta la pestaña Usuarios
según el rol.

**Tech Stack:** FastAPI, SQLite (sin ORM), `pyotp` (ya en uso),
`smtplib`/`email.message` (biblioteca estándar, sin dependencia nueva),
JS vanilla sin frameworks.

**Spec:** `docs/superpowers/specs/2026-08-23-roles-y-recuperacion-design.md`
(y, para lo que sigue vigente sin cambios, el spec anterior
`docs/superpowers/specs/2026-08-22-login-panel-design.md`).

## Global Constraints

- Cantidades/importes: no aplica a esta rama (no toca esas tablas).
- `stock_sistema`/`costo_unitario`: no aplica (no toca `dispositivos.router`).
- Nada externo en el navegador: sin CDN, sin librerías remotas. `smtplib`
  corre en el servidor, nunca en el navegador.
- Todo dato del servidor se escapa antes de ir al HTML (`esc()` en
  `app.js`) salvo que se use `.textContent`, que no lo necesita.
- Fechas ISO 8601 UTC de texto, únicamente vía `app/reloj.py`.
- Nada se edita ni se borra: las bajas son lógicas (`activo = 0`).
- Textos en castellano rioplatense, incluidos los mensajes de error.
- Mensajes de commit en castellano, en presente, describiendo el efecto.
- **Hay exactamente un superusuario, para siempre.** Ningún endpoint
  acepta `rol` desde el cliente: el servidor lo decide siempre.
- **`sesion_panel.recordar = 1` significa sin vencimiento por tiempo.**
  Nunca revisar `DIAS_DE_SESION` para esas filas.
- **Sin sistema de migraciones en este proyecto** (`db.crear_esquema`
  solo corre `CREATE TABLE IF NOT EXISTS`, no agrega columnas a una tabla
  que ya existe). Nota operativa para quien despliegue esto: el
  servidor productivo de este cliente ya creó `cuenta_panel`/
  `sesion_panel` con el esquema viejo (sin `rol` ni `recordar`), aunque
  todavía sin ninguna fila cargada — hay que borrar esas dos tablas a
  mano antes de arrancar el servidor con esta rama, para que se
  recreen con el esquema nuevo. El resto de la base (artículos,
  sesiones de conteo, etc.) no se toca.

---

## Task 1: Esquema — rol, recordar, código de recuperación

**Files:**
- Modify: `servidor/app/esquema.sql:147-166`
- Test: `servidor/tests/test_esquema.py`

**Interfaces:**
- Produces: columna `cuenta_panel.rol` (`'superusuario'`|`'menor'`,
  default `'menor'`); `cuenta_panel.otp_secreto` ahora nullable; columna
  `sesion_panel.recordar` (`INTEGER NOT NULL DEFAULT 0`); tabla
  `codigo_recuperacion(cuenta_id PK, codigo_hash, creado_en)`.

- [ ] **Step 1: Escribir el test que falla**

```python
# servidor/tests/test_esquema.py — agregar al final del archivo

def test_cuenta_panel_tiene_rol_y_otp_opcional(con):
    columnas = {
        fila["name"]: fila for fila in con.execute("PRAGMA table_info(cuenta_panel)")
    }
    assert columnas["rol"]["notnull"] == 1
    assert columnas["rol"]["dflt_value"] == "'menor'"
    assert columnas["otp_secreto"]["notnull"] == 0


def test_sesion_panel_tiene_recordar(con):
    columnas = {
        fila["name"]: fila for fila in con.execute("PRAGMA table_info(sesion_panel)")
    }
    assert columnas["recordar"]["notnull"] == 1
    assert columnas["recordar"]["dflt_value"] == "0"


def test_el_esquema_crea_codigo_recuperacion(con):
    tablas = {
        fila["name"]
        for fila in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "codigo_recuperacion" in tablas


def test_no_se_puede_crear_una_cuenta_con_rol_invalido(con):
    import pytest
    with pytest.raises(Exception):
        con.execute(
            "INSERT INTO cuenta_panel (usuario, clave_hash, rol) "
            "VALUES ('x', 'y', 'lo-que-sea')"
        )
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_esquema.py -v --rootdir .`
(parado en `servidor/`)
Expected: FAIL — falta la columna `rol`, falta `recordar`, no existe
`codigo_recuperacion`.

- [ ] **Step 3: Reescribir el bloque de cuentas en `esquema.sql`**

Reemplazar el bloque completo `servidor/app/esquema.sql:144-166` (desde
el comentario `-- Cuentas para entrar al panel` hasta el `);` de
`sesion_panel`) por:

```sql
-- Cuentas para entrar al panel. Separadas de `operario` a propósito: son
-- dos identidades sin relación entre sí, y compartir tabla o vocabulario
-- las confundiría la primera vez que alguien lea el esquema.
--
-- Hay exactamente un superusuario, para siempre: se crea a mano, directo
-- contra la base, nunca a través de un endpoint. Las cuentas de rol
-- `menor` no tienen segundo factor —el login no lo pide para nadie, y
-- ellas se recuperan por mail, no por TOTP— así que `otp_secreto` es
-- opcional.
CREATE TABLE IF NOT EXISTS cuenta_panel (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario     TEXT NOT NULL,
    clave_hash  TEXT NOT NULL,
    otp_secreto TEXT,
    activo      INTEGER NOT NULL DEFAULT 1,
    rol         TEXT NOT NULL DEFAULT 'menor' CHECK (rol IN ('superusuario', 'menor'))
);

-- Única solo entre cuentas activas: como `desactivar()` es una baja
-- lógica (nunca se borra la fila), esto permite recrear una cuenta con
-- el mismo usuario después de darla de baja —es el único camino de
-- recuperación de un OTP perdido.
CREATE UNIQUE INDEX IF NOT EXISTS cuenta_panel_usuario_activo
    ON cuenta_panel(usuario) WHERE activo = 1;

CREATE TABLE IF NOT EXISTS sesion_panel (
    token      TEXT PRIMARY KEY,
    cuenta_id  INTEGER NOT NULL REFERENCES cuenta_panel(id),
    creado_en  TEXT NOT NULL,
    -- Con "Recordarme" tildado: la sesión no vence por tiempo, solo con
    -- un logout explícito. `sesion_valida()` no revisa el vencimiento
    -- de estas filas.
    recordar   INTEGER NOT NULL DEFAULT 0
);

-- Un código de recuperación por cuenta: pedir uno nuevo reemplaza al
-- anterior, no lo acumula. Solo lo usan las cuentas de rol `menor`
-- —el superusuario recupera con el TOTP que ya tiene, sin necesitar
-- esta tabla—.
CREATE TABLE IF NOT EXISTS codigo_recuperacion (
    cuenta_id   INTEGER PRIMARY KEY REFERENCES cuenta_panel(id),
    codigo_hash TEXT NOT NULL,
    creado_en   TEXT NOT NULL
);
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_esquema.py -v --rootdir .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/app/esquema.sql servidor/tests/test_esquema.py
git commit -m "Suma rol, recordarme y el código de recuperación al esquema del panel"
```

---

## Task 2: `cuentas_panel.crear()` gana rol; OTP condicional

**Files:**
- Modify: `servidor/app/repos/cuentas_panel.py:19-48`
- Modify: `servidor/tests/test_repos_cuentas_panel.py`

**Interfaces:**
- Consumes: esquema de Task 1.
- Produces: `crear(con, usuario, clave, rol="menor") -> {"id", "usuario", "otp_secreto", "rol"}`
  (`otp_secreto` es `None` si `rol != "superusuario"`). `por_usuario(con, usuario)`
  ahora también trae `rol`. `listar()` sin cambios (no expone `rol`).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_repos_cuentas_panel.py

# Reemplazar test_crear_devuelve_el_secreto_totp_en_texto_plano por:
def test_crear_superusuario_devuelve_el_secreto_totp_en_texto_plano(con):
    creada = cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    assert creada["usuario"] == "Administrator"
    assert creada["otp_secreto"]
    assert creada["rol"] == "superusuario"
    assert "id" in creada


def test_crear_menor_no_genera_secreto_totp(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert creada["otp_secreto"] is None
    assert creada["rol"] == "menor"


# Reemplazar test_por_usuario_trae_el_hash_y_el_secreto por:
def test_por_usuario_trae_el_hash_y_el_rol(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuenta = cuentas_panel.por_usuario(con, "pablo")

    assert cuenta["usuario"] == "pablo"
    assert cuenta["clave_hash"]
    assert cuenta["rol"] == "menor"


def test_por_usuario_de_un_superusuario_trae_el_secreto(con):
    cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    cuenta = cuentas_panel.por_usuario(con, "Administrator")

    assert cuenta["otp_secreto"]


# Eliminar por completo (existe_alguna desaparece):
#   test_existe_alguna_es_falso_sin_cuentas
#   test_existe_alguna_es_verdadero_con_una_cuenta
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_repos_cuentas_panel.py -v --rootdir .`
Expected: FAIL en los tests nuevos/modificados (`crear()` no acepta
`rol` todavía).

- [ ] **Step 3: Reescribir `crear()` y `por_usuario()`, borrar `existe_alguna()`**

En `servidor/app/repos/cuentas_panel.py`, reemplazar la función `crear`
completa (líneas 19-48) por:

```python
def crear(con, usuario, clave, rol="menor"):
    """Da de alta una cuenta. Solo el superusuario tiene TOTP —las cuentas
    de rol menor no lo necesitan: el login no lo pide para nadie, y ellas
    se recuperan por mail, no por segundo factor.

    Si genera un secreto, lo devuelve en texto plano: es la única vez que
    existe fuera de la base. Nadie vuelve a pedirlo después.
    """
    usuario = (usuario or "").strip() if isinstance(usuario, str) else ""
    if not usuario:
        raise ValueError("La cuenta necesita un usuario")
    if not clave or len(clave) < 8:
        raise ValueError("La contraseña tiene que tener al menos 8 caracteres")

    clave_hash = autenticacion.hashear_clave(clave)
    secreto = autenticacion.generar_secreto_totp() if rol == "superusuario" else None

    try:
        with con:
            cursor = con.execute(
                "INSERT INTO cuenta_panel (usuario, clave_hash, otp_secreto, rol) "
                "VALUES (?, ?, ?, ?)",
                (usuario, clave_hash, secreto, rol),
            )
            cuenta_id = cursor.lastrowid
    except sqlite3.IntegrityError as error:
        if "cuenta_panel.usuario" in str(error):
            raise ValueError(f"Ya existe una cuenta con el usuario «{usuario}»") from error
        raise

    return {"id": cuenta_id, "usuario": usuario, "otp_secreto": secreto, "rol": rol}
```

Borrar la función `existe_alguna` (líneas 51-52) por completo.

Reemplazar `por_usuario` (antes líneas 55-62) por:

```python
def por_usuario(con, usuario):
    """Con clave_hash, otp_secreto y rol: solo para login/recuperación, nunca se expone."""
    fila = con.execute(
        "SELECT id, usuario, clave_hash, otp_secreto, rol FROM cuenta_panel "
        "WHERE usuario = ? AND activo = 1",
        (usuario,),
    ).fetchone()
    return dict(fila) if fila else None
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_repos_cuentas_panel.py -v --rootdir .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/cuentas_panel.py servidor/tests/test_repos_cuentas_panel.py
git commit -m "Solo el superusuario recibe secreto TOTP al crear una cuenta"
```

---

## Task 3: Sesiones con "Recordarme"

**Files:**
- Modify: `servidor/app/repos/cuentas_panel.py:81-108` (`crear_sesion`, `sesion_valida`)
- Modify: `servidor/tests/test_repos_cuentas_panel.py`

**Interfaces:**
- Consumes: `crear(con, usuario, clave, rol="menor")` de Task 2.
- Produces: `crear_sesion(con, cuenta_id, recordar=False) -> token`;
  `sesion_valida(con, token) -> {"id", "usuario", "rol"} | None`, sin
  chequear vencimiento cuando la fila tiene `recordar = 1`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_repos_cuentas_panel.py

# Reemplazar test_crear_sesion_y_validarla por:
def test_crear_sesion_y_validarla(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    token = cuentas_panel.crear_sesion(con, creada["id"])
    validada = cuentas_panel.sesion_valida(con, token)

    assert validada == {"id": creada["id"], "usuario": "pablo", "rol": "menor"}


def test_una_sesion_recordada_no_vence_aunque_pasen_mas_de_30_dias(con, monkeypatch):
    from datetime import datetime, timedelta, timezone

    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"], recordar=True)

    vencida = (datetime.now(timezone.utc) - timedelta(days=400)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    con.execute(
        "UPDATE sesion_panel SET creado_en = ? WHERE token = ?", (vencida, token)
    )
    con.commit()

    assert cuentas_panel.sesion_valida(con, token) is not None
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_repos_cuentas_panel.py -v --rootdir .`
Expected: FAIL — `crear_sesion()` todavía no acepta `recordar`, y
`sesion_valida()` no trae `rol`.

- [ ] **Step 3: Reescribir `crear_sesion()` y `sesion_valida()`**

Reemplazar ambas funciones (antes líneas 81-108) por:

```python
def crear_sesion(con, cuenta_id, recordar=False):
    token = secrets.token_urlsafe(32)
    with con:
        con.execute(
            "INSERT INTO sesion_panel (token, cuenta_id, creado_en, recordar) "
            "VALUES (?, ?, ?, ?)",
            (token, cuenta_id, reloj.ahora(), int(recordar)),
        )
    return token


def sesion_valida(con, token):
    """La cuenta dueña de esta sesión, o None si no existe, venció, o la
    cuenta se dio de baja. Una sesión con `recordar = 1` no vence nunca
    por tiempo."""
    fila = con.execute(
        "SELECT s.creado_en, s.recordar, c.id, c.usuario, c.activo, c.rol "
        "FROM sesion_panel s JOIN cuenta_panel c ON c.id = s.cuenta_id "
        "WHERE s.token = ?",
        (token,),
    ).fetchone()
    if fila is None or not fila["activo"]:
        return None

    if not fila["recordar"]:
        creado = datetime.strptime(fila["creado_en"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        if datetime.now(timezone.utc) - creado > timedelta(days=DIAS_DE_SESION):
            return None

    return {"id": fila["id"], "usuario": fila["usuario"], "rol": fila["rol"]}
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_repos_cuentas_panel.py -v --rootdir .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/cuentas_panel.py servidor/tests/test_repos_cuentas_panel.py
git commit -m "Agrega Recordarme: una sesión marcada no vence por tiempo"
```

---

## Task 4: Repo de recuperación de contraseña

**Files:**
- Modify: `servidor/app/repos/cuentas_panel.py` (agregar al final)
- Test: `servidor/tests/test_repos_cuentas_panel.py`

**Interfaces:**
- Consumes: `autenticacion.hashear_clave`/`verificar_clave` (ya existen,
  sin cambios); `reloj.ahora()`.
- Produces: `generar_codigo_recuperacion(con, cuenta_id) -> codigo:str`
  (6 dígitos, en texto plano, para mandar por mail o comparar con el
  TOTP); `verificar_codigo_recuperacion(con, cuenta_id, codigo) -> bool`
  (vence a los 15 minutos); `cambiar_clave(con, cuenta_id, clave_nueva)`
  (levanta `ValueError` si la clave es débil; si no, actualiza el hash,
  borra el código de recuperación pendiente si había, y cierra todas las
  sesiones abiertas de esa cuenta).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_repos_cuentas_panel.py — agregar al final

def test_generar_codigo_de_recuperacion_es_de_6_digitos(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert len(codigo) == 6
    assert codigo.isdigit()


def test_el_codigo_de_recuperacion_generado_es_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], codigo) is True


def test_un_codigo_incorrecto_no_es_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], "000000") is False


def test_sin_ningun_codigo_pedido_no_hay_codigo_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], "123456") is False


def test_pedir_un_codigo_nuevo_invalida_el_anterior(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    viejo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])
    cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], viejo) is False


def test_un_codigo_vencido_no_es_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    from datetime import datetime, timedelta, timezone
    vencido = (datetime.now(timezone.utc) - timedelta(minutes=16)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    con.execute(
        "UPDATE codigo_recuperacion SET creado_en = ? WHERE cuenta_id = ?",
        (vencido, creada["id"]),
    )
    con.commit()

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], codigo) is False


def test_cambiar_clave_actualiza_el_hash(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuentas_panel.cambiar_clave(con, creada["id"], "clave-nueva-456")

    cuenta = cuentas_panel.por_usuario(con, "pablo")
    assert autenticacion.verificar_clave("clave-nueva-456", cuenta["clave_hash"])
    assert not autenticacion.verificar_clave("clave-larga-123", cuenta["clave_hash"])


def test_cambiar_clave_con_una_debil_avisa(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    with pytest.raises(ValueError, match="8 caracteres"):
        cuentas_panel.cambiar_clave(con, creada["id"], "corta")


def test_cambiar_clave_borra_el_codigo_de_recuperacion_pendiente(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    cuentas_panel.cambiar_clave(con, creada["id"], "clave-nueva-456")

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], codigo) is False


def test_cambiar_clave_cierra_las_sesiones_abiertas(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])
    assert cuentas_panel.sesion_valida(con, token) is not None

    cuentas_panel.cambiar_clave(con, creada["id"], "clave-nueva-456")

    assert cuentas_panel.sesion_valida(con, token) is None
```

Agregar `import pytest` y `from app.servicios import autenticacion` al
encabezado de `test_repos_cuentas_panel.py` si no están ya.

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_repos_cuentas_panel.py -v --rootdir .`
Expected: FAIL — las tres funciones no existen todavía.

- [ ] **Step 3: Implementar, al final de `cuentas_panel.py`**

```python
MINUTOS_CODIGO_RECUPERACION = 15


def generar_codigo_recuperacion(con, cuenta_id):
    """Reemplaza cualquier código pendiente de esta cuenta —no se acumulan—."""
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    codigo_hash = autenticacion.hashear_clave(codigo)
    with con:
        con.execute(
            "INSERT INTO codigo_recuperacion (cuenta_id, codigo_hash, creado_en) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(cuenta_id) DO UPDATE SET "
            "codigo_hash = excluded.codigo_hash, creado_en = excluded.creado_en",
            (cuenta_id, codigo_hash, reloj.ahora()),
        )
    return codigo


def verificar_codigo_recuperacion(con, cuenta_id, codigo):
    fila = con.execute(
        "SELECT codigo_hash, creado_en FROM codigo_recuperacion WHERE cuenta_id = ?",
        (cuenta_id,),
    ).fetchone()
    if fila is None:
        return False

    creado = datetime.strptime(fila["creado_en"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    if datetime.now(timezone.utc) - creado > timedelta(minutes=MINUTOS_CODIGO_RECUPERACION):
        return False

    return autenticacion.verificar_clave(codigo, fila["codigo_hash"])


def cambiar_clave(con, cuenta_id, clave_nueva):
    if not clave_nueva or len(clave_nueva) < 8:
        raise ValueError("La contraseña tiene que tener al menos 8 caracteres")

    clave_hash = autenticacion.hashear_clave(clave_nueva)
    with con:
        con.execute(
            "UPDATE cuenta_panel SET clave_hash = ? WHERE id = ?", (clave_hash, cuenta_id)
        )
        con.execute("DELETE FROM codigo_recuperacion WHERE cuenta_id = ?", (cuenta_id,))
        con.execute("DELETE FROM sesion_panel WHERE cuenta_id = ?", (cuenta_id,))
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_repos_cuentas_panel.py -v --rootdir .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/app/repos/cuentas_panel.py servidor/tests/test_repos_cuentas_panel.py
git commit -m "Suma la generación y verificación del código de recuperación"
```

---

## Task 5: Envío de mail

**Files:**
- Create: `servidor/app/servicios/correo.py`
- Create: `servidor/correo-de-ejemplo.properties`
- Test: `servidor/tests/test_correo.py`
- Modify: `CLAUDE.md` (agregar sección corta, ver Step 6)

**Interfaces:**
- Produces: `correo.mandar_codigo_recuperacion(destinatario: str, codigo: str)`,
  levanta `correo.ErrorDeCorreo` si falta el archivo de configuración, le
  faltan campos, o falla el envío. `correo.RUTA_CONFIG` (Path, lee
  `CONTROL_DE_STOCK_MAIL` o usa el default) — se expone para que los
  tests puedan pisarla con `monkeypatch`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_correo.py
import smtplib

import pytest

from app.servicios import correo


class SMTPFalso:
    """Reemplaza smtplib.SMTP_SSL en los tests: nunca abre una conexión real."""

    instancias = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.logueado_con = None
        self.mensajes_mandados = []
        SMTPFalso.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def login(self, usuario, clave):
        self.logueado_con = (usuario, clave)

    def send_message(self, mensaje):
        self.mensajes_mandados.append(mensaje)


class SMTPQueFalla(SMTPFalso):
    def send_message(self, mensaje):
        raise smtplib.SMTPException("el servidor de Gmail rechazó el mensaje")


@pytest.fixture
def config_de_correo(tmp_path, monkeypatch):
    archivo = tmp_path / "correo.properties"
    archivo.write_text("usuario=deposito@gmail.com\nclave=una-clave-de-aplicacion\n")
    monkeypatch.setattr(correo, "RUTA_CONFIG", archivo)
    return archivo


def test_sin_archivo_de_configuracion_avisa(tmp_path, monkeypatch):
    monkeypatch.setattr(correo, "RUTA_CONFIG", tmp_path / "no-existe.properties")

    with pytest.raises(correo.ErrorDeCorreo, match="configuración"):
        correo.mandar_codigo_recuperacion("alguien@x.com", "123456")


def test_con_campos_incompletos_avisa(tmp_path, monkeypatch):
    archivo = tmp_path / "correo.properties"
    archivo.write_text("usuario=deposito@gmail.com\n")
    monkeypatch.setattr(correo, "RUTA_CONFIG", archivo)

    with pytest.raises(correo.ErrorDeCorreo, match="clave"):
        correo.mandar_codigo_recuperacion("alguien@x.com", "123456")


def test_manda_el_codigo_por_smtp(config_de_correo, monkeypatch):
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", SMTPFalso)
    SMTPFalso.instancias.clear()

    correo.mandar_codigo_recuperacion("alguien@x.com", "123456")

    servidor = SMTPFalso.instancias[0]
    assert servidor.logueado_con == ("deposito@gmail.com", "una-clave-de-aplicacion")
    mensaje = servidor.mensajes_mandados[0]
    assert mensaje["To"] == "alguien@x.com"
    assert "123456" in mensaje.get_content()


def test_una_falla_de_smtp_se_traduce_a_errordecorreo(config_de_correo, monkeypatch):
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", SMTPQueFalla)

    with pytest.raises(correo.ErrorDeCorreo):
        correo.mandar_codigo_recuperacion("alguien@x.com", "123456")
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_correo.py -v --rootdir .`
Expected: FAIL — el módulo `app.servicios.correo` no existe.

- [ ] **Step 3: Implementar `servidor/app/servicios/correo.py`**

```python
"""Envío del código de recuperación por mail.

Solo hace falta para recuperar la contraseña de una cuenta de rol
menor —el uso normal del panel nunca depende de esto—, así que su
ausencia o mala configuración no impide que el servidor arranque: este
módulo no se toca hasta que alguien pide recuperar una contraseña.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

RUTA_CONFIG = Path(
    os.environ.get(
        "CONTROL_DE_STOCK_MAIL", "C:/clientes/claves/control-de-stock-mail.properties"
    )
)

CAMPOS_REQUERIDOS = ["usuario", "clave"]


class ErrorDeCorreo(Exception):
    pass


def _leer_config():
    if not RUTA_CONFIG.exists():
        raise ErrorDeCorreo(
            f"Falta el archivo de configuración de mail: {RUTA_CONFIG}. "
            "Copiá servidor/correo-de-ejemplo.properties a esa ruta y completá "
            "usuario y clave, o poné otra ruta en la variable de entorno "
            "CONTROL_DE_STOCK_MAIL."
        )

    config = {}
    for linea in RUTA_CONFIG.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        config[clave.strip()] = valor.strip()

    faltantes = [campo for campo in CAMPOS_REQUERIDOS if not config.get(campo)]
    if faltantes:
        raise ErrorDeCorreo(
            f"Al archivo de configuración de mail ({RUTA_CONFIG}) le falta "
            f"completar: {', '.join(faltantes)}"
        )
    return config


def mandar_codigo_recuperacion(destinatario, codigo):
    config = _leer_config()

    mensaje = EmailMessage()
    mensaje["Subject"] = "Código para recuperar tu contraseña — Control de Stock"
    mensaje["From"] = config["usuario"]
    mensaje["To"] = destinatario
    mensaje.set_content(
        f"Tu código para recuperar la contraseña es: {codigo}\n\n"
        "Vence en 15 minutos. Si no lo pediste vos, ignorá este mail."
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(config["usuario"], config["clave"])
            servidor.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as error:
        raise ErrorDeCorreo(f"No se pudo mandar el mail: {error}") from error
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_correo.py -v --rootdir .`
Expected: PASS

- [ ] **Step 5: Crear el archivo de ejemplo**

`servidor/correo-de-ejemplo.properties`:

```
# Copiá este archivo a C:\clientes\claves\control-de-stock-mail.properties
# —fuera del proyecto— y completá con una casilla de Gmail y su
# contraseña de aplicación (no la contraseña normal de la cuenta: Gmail
# exige generar una aparte para esto, en
# https://myaccount.google.com/apppasswords).
#
# Si preferís otra ubicación, poné la ruta en la variable de entorno
# CONTROL_DE_STOCK_MAIL.
#
# Sin este archivo, o con estos campos sin completar, el panel arranca
# igual: el mail solo hace falta para "Olvidé mi contraseña" de las
# cuentas que no son Administrator.
usuario=
clave=
```

- [ ] **Step 6: Documentar en `CLAUDE.md`**

Agregar, después de la sección "## Publicar una versión firmada":

```markdown
## Configurar la recuperación de contraseña por mail

Las cuentas de rol menor recuperan la contraseña por un código que
llega por mail (Administrator la recupera con TOTP, sin mail de por
medio). Ese envío necesita una casilla de Gmail con contraseña de
aplicación, en `C:\clientes\claves\control-de-stock-mail.properties` —o
la ruta que indique `CONTROL_DE_STOCK_MAIL`—.
`servidor/correo-de-ejemplo.properties` documenta el formato. Sin ese
archivo, o con campos sin completar, el panel arranca igual: recién
falla al pedirse una recuperación, con un mensaje que explica qué falta.
```

- [ ] **Step 7: Commit**

```bash
git add servidor/app/servicios/correo.py servidor/tests/test_correo.py \
    servidor/correo-de-ejemplo.properties CLAUDE.md
git commit -m "Suma el envío del código de recuperación por mail"
```

---

## Task 6: Login sin OTP, "Recordarme", y `requerir_superusuario`

**Files:**
- Modify: `servidor/app/api/auth.py`
- Test: `servidor/tests/test_auth_api.py` (tests puntuales de esta tarea;
  el resto del archivo se reescribe en la Task 10)

**Interfaces:**
- Consumes: `cuentas_panel.por_usuario`, `crear_sesion(con, cuenta_id, recordar=False)`
  de Tasks 2-3; `autenticacion.verificar_clave`.
- Produces: `verificar_sesion(request) -> dict` (sin cambios de firma,
  el dict ahora trae `rol`); `requerir_superusuario(cuenta=Depends(verificar_sesion)) -> dict`,
  403 si `cuenta["rol"] != "superusuario"`; `POST /api/auth/login` con
  `{usuario, clave, recordarme}` (sin `codigo_otp`); `GET /api/auth/estado`
  devuelve `{logueado, usuario, rol}` (sin `hay_cuentas`).

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_auth_api.py — agregar (no reemplaza todavía el resto del archivo)

def test_login_sin_otp_funciona(cliente_sin_loguear):
    from app.repos import cuentas_panel
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "clave-larga-123"}
    )

    assert respuesta.status_code == 200
    assert "sesion_panel" in respuesta.cookies


def test_login_con_recordarme_pone_una_cookie_de_diez_anios(cliente_sin_loguear):
    from app.repos import cuentas_panel
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "recordarme": True},
    )

    import time
    cookie = next(c for c in respuesta.cookies.jar if c.name == "sesion_panel")
    # cookie.expires es una marca de tiempo absoluta (epoch): comparar contra
    # "ahora + 5 años" confirma que vence lejos en el futuro, sin depender del
    # valor exacto de SEGUNDOS_RECORDAR.
    assert cookie.expires > time.time() + 60 * 60 * 24 * 365 * 5


def test_estado_sin_login_no_trae_rol(cliente_sin_loguear):
    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": False, "usuario": None, "rol": None}


def test_requerir_superusuario_rechaza_una_cuenta_menor(cliente_sin_loguear):
    from app.repos import cuentas_panel
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "clave-larga-123"}
    )

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "otra@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 403
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v --rootdir . -k "sin_otp or recordarme or sin_login_no_trae_rol or requerir_superusuario"`
Expected: FAIL — el login todavía pide `codigo_otp`, `estado` todavía
trae `hay_cuentas`, `requerir_superusuario` no existe.

- [ ] **Step 3: Reescribir `servidor/app/api/auth.py`**

Reemplazar el archivo completo por (la Task 7 le agrega todavía el
cuerpo de `crear_cuenta`; acá queda con un `TODO` explícito que la Task 7
resuelve, para no dejar el archivo roto entre tareas — la Task 7 es
inmediatamente siguiente):

```python
"""Login del panel: cuentas, sesión, roles, y la recuperación de contraseña.

Sin autenticación en el propio router —es el único lugar donde no puede
haberla, por definición—. `panel.router` importa `verificar_sesion` y
`requerir_superusuario` de acá para protegerse a sí mismo.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.repos import cuentas_panel
from app.servicios import autenticacion, correo

router = APIRouter(prefix="/api/auth")

COOKIE_SESION = "sesion_panel"
SEGUNDOS_DE_SESION = 60 * 60 * 24 * 30
# "Recordarme": no vuelve a pedir login salvo un logout explícito. La
# cookie necesita un vencimiento largo para eso —`sesion_valida()` ya no
# chequea el vencimiento del lado del servidor para estas sesiones, pero
# el navegador igual descarta una cookie sin `max_age`—, así que se usa
# un número grande en vez de "para siempre" (no existe esa opción en HTTP).
SEGUNDOS_RECORDAR = 60 * 60 * 24 * 365 * 10


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


def requerir_superusuario(cuenta: dict = Depends(verificar_sesion)) -> dict:
    """Como `verificar_sesion`, pero además exige el rol superusuario."""
    if cuenta["rol"] != "superusuario":
        raise HTTPException(
            status_code=403, detail="Esta acción es solo para el superusuario"
        )
    return cuenta


@router.get("/estado")
def estado(request: Request):
    con = _con(request)
    token = request.cookies.get(COOKIE_SESION)
    cuenta = cuentas_panel.sesion_valida(con, token) if token else None

    return {
        "logueado": cuenta is not None,
        "usuario": cuenta["usuario"] if cuenta else None,
        "rol": cuenta["rol"] if cuenta else None,
    }


@router.post("/login")
async def login(request: Request, response: Response):
    cuerpo = await request.json()
    con = _con(request)

    usuario = (cuerpo.get("usuario") or "").strip()
    clave = cuerpo.get("clave") or ""
    recordarme = bool(cuerpo.get("recordarme"))

    credenciales_invalidas = HTTPException(
        status_code=401, detail="Usuario o contraseña incorrecto"
    )

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is None:
        raise credenciales_invalidas
    if not autenticacion.verificar_clave(clave, cuenta["clave_hash"]):
        raise credenciales_invalidas

    token = cuentas_panel.crear_sesion(con, cuenta["id"], recordar=recordarme)
    response.set_cookie(
        COOKIE_SESION, token,
        httponly=True, samesite="lax",
        max_age=SEGUNDOS_RECORDAR if recordarme else SEGUNDOS_DE_SESION,
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
async def crear_cuenta(request: Request, _: dict = Depends(requerir_superusuario)):
    raise NotImplementedError("completado en la Task 7 de este plan")


@router.post("/recuperar/solicitar")
async def recuperar_solicitar(request: Request):
    raise NotImplementedError("completado en la Task 8 de este plan")


@router.post("/recuperar/confirmar")
async def recuperar_confirmar(request: Request):
    raise NotImplementedError("completado en la Task 8 de este plan")
```

Nota para quien ejecute esta tarea: los dos `NotImplementedError` de
recuperación y el de `crear_cuenta` son intencionales y temporales — las
Tasks 7 y 8, inmediatamente siguientes, los completan. No corras la
batería completa de `test_auth_api.py` todavía en este punto (va a fallar
en los tests que tocan esos tres endpoints, ya sea porque no existen o
porque tiran `NotImplementedError`); corré solo el filtro `-k` indicado
en el Step 4 de abajo.

- [ ] **Step 4: Correr los tests de esta tarea, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v --rootdir . -k "sin_otp or recordarme or sin_login_no_trae_rol or requerir_superusuario"`
Expected: PASS (los demás tests de este archivo siguen rotos hasta la
Task 10 — es esperado, ver la nota del Step 3).

- [ ] **Step 5: Commit**

```bash
git add servidor/app/api/auth.py servidor/tests/test_auth_api.py
git commit -m "Saca el OTP del login normal y suma Recordarme y requerir_superusuario"
```

---

## Task 7: Alta de cuentas siempre protegida, sin QR

**Files:**
- Modify: `servidor/app/api/auth.py` (completa `crear_cuenta`, deja
  `otpauth_url`/`vinculacion` del import solo si hace falta en otra
  parte — no hace falta ya en este archivo, sacarlo del import)
- Test: `servidor/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `cuentas_panel.crear(con, usuario, clave, rol="menor")` de
  Task 2; `requerir_superusuario` de Task 6.
- Produces: `POST /api/auth/cuentas` exige sesión de superusuario
  siempre, crea solo cuentas `rol="menor"` (ignora cualquier `rol` del
  cuerpo del pedido), responde `{"id", "usuario"}` sin QR.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_auth_api.py — agregar

def _crear_superusuario_y_loguearse(cliente, usuario="Administrator", clave="clave-larga-123"):
    from app.repos import cuentas_panel
    con = cliente.app.state.con
    cuentas_panel.crear(con, usuario, clave, rol="superusuario")
    cliente.post("/api/auth/login", json={"usuario": usuario, "clave": clave})


def test_crear_cuenta_sin_sesion_da_401(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 401


def test_superusuario_puede_crear_una_cuenta_menor(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo == {"id": cuerpo["id"], "usuario": "ana@x.com"}


def test_crear_cuenta_ignora_el_rol_del_pedido(cliente_sin_loguear):
    from app.repos import cuentas_panel
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cliente_sin_loguear.post(
        "/api/auth/cuentas",
        json={"usuario": "ana@x.com", "clave": "clave-larga-456", "rol": "superusuario"},
    )

    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.por_usuario(con, "ana@x.com")
    assert creada["rol"] == "menor"
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v --rootdir . -k "crear_cuenta"`
Expected: FAIL — `crear_cuenta` todavía tira `NotImplementedError`.

- [ ] **Step 3: Completar `crear_cuenta` en `auth.py`**

Reemplazar:

```python
@router.post("/cuentas")
async def crear_cuenta(request: Request, _: dict = Depends(requerir_superusuario)):
    raise NotImplementedError("completado en la Task 7 de este plan")
```

por:

```python
@router.post("/cuentas")
async def crear_cuenta(request: Request, _: dict = Depends(requerir_superusuario)):
    """El rol nunca sale del cliente: esta ruta solo crea cuentas de rol
    menor. Hay exactamente un superusuario, y se crea a mano contra la
    base, nunca por acá."""
    con = _con(request)
    cuerpo = await request.json()
    try:
        creada = cuentas_panel.crear(con, cuerpo.get("usuario"), cuerpo.get("clave"), rol="menor")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"id": creada["id"], "usuario": creada["usuario"]}
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v --rootdir . -k "crear_cuenta"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/app/api/auth.py servidor/tests/test_auth_api.py
git commit -m "Cierra el alta de cuentas: siempre superusuario, siempre rol menor"
```

---

## Task 8: Endpoints de recuperación

**Files:**
- Modify: `servidor/app/api/auth.py` (completa los dos endpoints de
  recuperación)
- Test: `servidor/tests/test_auth_api.py`

**Interfaces:**
- Consumes: `cuentas_panel.por_usuario`, `generar_codigo_recuperacion`,
  `verificar_codigo_recuperacion`, `cambiar_clave` de Tasks 2 y 4;
  `autenticacion.verificar_totp`; `correo.mandar_codigo_recuperacion`/`ErrorDeCorreo`
  de Task 5.
- Produces: `POST /api/auth/recuperar/solicitar {usuario}` → siempre 200,
  mismo mensaje. `POST /api/auth/recuperar/confirmar {usuario, codigo,
  clave_nueva}` → 200 y cierra sesiones existentes si el código es
  válido; 401 genérico si no; 400 si la clave nueva es débil.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_auth_api.py — agregar

import pyotp


def test_solicitar_recuperacion_siempre_da_el_mismo_mensaje(cliente_sin_loguear):
    respuesta_existe = cliente_sin_loguear.post(
        "/api/auth/recuperar/solicitar", json={"usuario": "nadie@x.com"}
    )

    assert respuesta_existe.status_code == 200
    assert respuesta_existe.json()["mensaje"]


def test_solicitar_recuperacion_de_una_cuenta_menor_manda_un_mail(
    cliente_sin_loguear, monkeypatch
):
    from app.repos import cuentas_panel
    from app.servicios import correo

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")

    mandados = []
    monkeypatch.setattr(
        correo, "mandar_codigo_recuperacion",
        lambda destinatario, codigo: mandados.append((destinatario, codigo)),
    )

    cliente_sin_loguear.post("/api/auth/recuperar/solicitar", json={"usuario": "ana@x.com"})

    assert len(mandados) == 1
    assert mandados[0][0] == "ana@x.com"
    assert len(mandados[0][1]) == 6


def test_solicitar_recuperacion_del_superusuario_no_manda_mail(
    cliente_sin_loguear, monkeypatch
):
    from app.repos import cuentas_panel
    from app.servicios import correo

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    mandados = []
    monkeypatch.setattr(
        correo, "mandar_codigo_recuperacion",
        lambda destinatario, codigo: mandados.append((destinatario, codigo)),
    )

    cliente_sin_loguear.post(
        "/api/auth/recuperar/solicitar", json={"usuario": "Administrator"}
    )

    assert mandados == []


def test_confirmar_recuperacion_del_superusuario_con_totp(cliente_sin_loguear):
    from app.repos import cuentas_panel

    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")
    codigo = pyotp.TOTP(creada["otp_secreto"]).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "Administrator", "codigo": codigo, "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 200
    login = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "Administrator", "clave": "clave-nueva-456"}
    )
    assert login.status_code == 200


def test_confirmar_recuperacion_de_una_cuenta_menor_con_el_codigo_de_mail(cliente_sin_loguear):
    from app.repos import cuentas_panel

    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": codigo, "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 200


def test_confirmar_recuperacion_con_codigo_incorrecto_da_401(cliente_sin_loguear):
    from app.repos import cuentas_panel

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": "000000", "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 401


def test_confirmar_recuperacion_con_clave_nueva_debil_da_400(cliente_sin_loguear):
    from app.repos import cuentas_panel

    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": codigo, "clave_nueva": "corta"},
    )

    assert respuesta.status_code == 400
```

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v --rootdir . -k "recuperar"`
Expected: FAIL — los endpoints tiran `NotImplementedError`.

- [ ] **Step 3: Completar los dos endpoints en `auth.py`**

Reemplazar:

```python
@router.post("/recuperar/solicitar")
async def recuperar_solicitar(request: Request):
    raise NotImplementedError("completado en la Task 8 de este plan")


@router.post("/recuperar/confirmar")
async def recuperar_confirmar(request: Request):
    raise NotImplementedError("completado en la Task 8 de este plan")
```

por:

```python
MENSAJE_RECUPERAR_SOLICITADO = "Si la cuenta existe, ya podés poner el código."


@router.post("/recuperar/solicitar")
async def recuperar_solicitar(request: Request):
    """Mismo mensaje siempre, exista o no la cuenta, sea cual sea su rol:
    no hay que confirmarle a quien prueba a ciegas ninguno de los dos datos.

    Al superusuario no le manda nada —su código ya vive en la app
    autenticadora, no hay nada que generar—. A una cuenta de rol menor le
    genera un código y se lo manda por mail; si el envío falla, se avisa
    por consola en vez de romper la respuesta genérica —una respuesta
    distinta ahí confirmaría que la cuenta existe y es de rol menor—.
    """
    cuerpo = await request.json()
    con = _con(request)
    usuario = (cuerpo.get("usuario") or "").strip()

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is not None and cuenta["rol"] == "menor":
        codigo = cuentas_panel.generar_codigo_recuperacion(con, cuenta["id"])
        try:
            correo.mandar_codigo_recuperacion(cuenta["usuario"], codigo)
        except correo.ErrorDeCorreo as error:
            print(f"No se pudo mandar el mail de recuperación a {cuenta['usuario']}: {error}")

    return {"mensaje": MENSAJE_RECUPERAR_SOLICITADO}


@router.post("/recuperar/confirmar")
async def recuperar_confirmar(request: Request):
    cuerpo = await request.json()
    con = _con(request)

    usuario = (cuerpo.get("usuario") or "").strip()
    codigo = cuerpo.get("codigo") or ""
    clave_nueva = cuerpo.get("clave_nueva") or ""

    codigo_invalido = HTTPException(status_code=401, detail="Código o datos incorrectos")

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is None:
        raise codigo_invalido

    if cuenta["rol"] == "superusuario":
        valido = autenticacion.verificar_totp(cuenta["otp_secreto"], codigo)
    else:
        valido = cuentas_panel.verificar_codigo_recuperacion(con, cuenta["id"], codigo)

    if not valido:
        raise codigo_invalido

    try:
        cuentas_panel.cambiar_clave(con, cuenta["id"], clave_nueva)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"ok": True}
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_auth_api.py -v --rootdir . -k "recuperar"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add servidor/app/api/auth.py servidor/tests/test_auth_api.py
git commit -m "Agrega la recuperación de contraseña por OTP o por mail"
```

---

## Task 9: Proteger la gestión de usuarios con `requerir_superusuario`

**Files:**
- Modify: `servidor/app/api/panel.py:10,382-397`
- Modify: `servidor/tests/conftest.py:19-33`
- Test: `servidor/tests/test_api.py`

**Interfaces:**
- Consumes: `requerir_superusuario` de Task 6.
- Produces: `GET /api/usuarios` y `POST /api/usuarios/{id}/desactivar`
  exigen rol superusuario (403 si no). `conftest.loguear(cliente, rol="superusuario")`
  —con ese default, ninguno de los ~500 tests existentes que dependen de
  `loguear()`/`cliente` cambia de comportamiento—.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# servidor/tests/test_api.py — agregar

def test_listar_usuarios_rechaza_una_cuenta_menor(tmp_path):
    from tests.conftest import loguear
    from fastapi.testclient import TestClient
    from app.main import crear_app

    app = crear_app(str(tmp_path / "prueba-menor.db"))
    with TestClient(app) as otro_cliente:
        loguear(otro_cliente, rol="menor")
        assert otro_cliente.get("/api/usuarios").status_code == 403


def test_dar_de_baja_rechaza_una_cuenta_menor(tmp_path):
    from tests.conftest import loguear
    from fastapi.testclient import TestClient
    from app.main import crear_app

    app = crear_app(str(tmp_path / "prueba-menor2.db"))
    with TestClient(app) as otro_cliente:
        loguear(otro_cliente, rol="menor")
        assert otro_cliente.post("/api/usuarios/1/desactivar").status_code == 403
```

Nota: se arma un `TestClient` propio en vez de reusar el fixture
`cliente` porque `loguear()` corre una sola vez por fixture, con el rol
que ya quedó fijo (superusuario) para no romper el resto de la batería;
estos dos tests necesitan una cuenta de rol menor en su lugar.

- [ ] **Step 2: Correr los tests, confirmar que fallan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_api.py -v --rootdir . -k "rechaza_una_cuenta_menor"`
Expected: FAIL — `loguear()` todavía no acepta `rol`, y los endpoints
todavía no exigen superusuario.

- [ ] **Step 3: Actualizar `conftest.py` y `panel.py`**

En `servidor/tests/conftest.py`, reemplazar `loguear` (líneas 19-33) por:

```python
def loguear(cliente, rol="superusuario"):
    """Crea una cuenta de panel directo contra la base del `TestClient` ya
    arrancado, y le pisa la cookie de sesión.

    Superusuario por default: la mayoría de los ~500 tests que usan esto
    no tienen nada que ver con roles, y necesitan poder tocar cualquier
    endpoint —incluidos los de gestión de usuarios— sin pensar en esto.
    Los tests que sí prueban la restricción de rol pasan `rol="menor"`.
    """
    from app.repos import cuentas_panel

    con = cliente.app.state.con
    creada = cuentas_panel.crear(con, "prueba", "clave-de-prueba-123", rol=rol)
    token = cuentas_panel.crear_sesion(con, creada["id"])
    cliente.cookies.set("sesion_panel", token)
```

En `servidor/app/api/panel.py`, cambiar el import de la línea 10:

```python
from app.api.auth import requerir_superusuario, verificar_sesion
```

Y en las líneas 382-397, agregar la dependencia a los dos endpoints:

```python
@router.get("/usuarios")
def listar_usuarios(request: Request, _: dict = Depends(requerir_superusuario)):
    return cuentas_panel.listar(_con(request))


@router.post("/usuarios/{cuenta_id}/desactivar")
def desactivar_usuario(
    cuenta_id: int, request: Request, cuenta_actual: dict = Depends(requerir_superusuario)
):
    if cuenta_id == cuenta_actual["id"]:
        raise HTTPException(status_code=400, detail="No podés dar de baja tu propia cuenta")
    try:
        cuentas_panel.desactivar(_con(request), cuenta_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return {"activo": False}
```

- [ ] **Step 4: Correr los tests, confirmar que pasan**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_api.py -v --rootdir . -k "rechaza_una_cuenta_menor"`
Expected: PASS

- [ ] **Step 5: Correr la batería completa hasta ahora**

Run: `.\.venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: PASS en todo salvo `test_auth_api.py` (se termina de reescribir
en la Task 10) — si algo más falla, investigar antes de seguir.

- [ ] **Step 6: Commit**

```bash
git add servidor/app/api/panel.py servidor/tests/conftest.py servidor/tests/test_api.py
git commit -m "Restringe la gestión de usuarios al superusuario"
```

---

## Task 10: Reescribir `test_auth_api.py` para el contrato nuevo

**Files:**
- Modify: `servidor/tests/test_auth_api.py`

**Interfaces:**
- Consumes: todo lo de Tasks 1-9.

Esta tarea elimina los tests que probaban el bootstrap sin sesión (ya no
existe) y el login con OTP (ya no existe para el login normal), y agrega
los equivalentes con el contrato nuevo. Los tests agregados en las Tasks
6-9 quedan como están.

- [ ] **Step 1: Reemplazar el archivo completo**

`servidor/tests/test_auth_api.py`:

```python
import pyotp
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.repos import cuentas_panel


@pytest.fixture
def cliente_sin_loguear(tmp_path):
    """A diferencia del `cliente` de los demás archivos, este no se loguea:
    es el que hace falta para probar el login en sí y los 401/403."""
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


def _crear_superusuario_y_loguearse(cliente, usuario="Administrator", clave="clave-larga-123"):
    con = cliente.app.state.con
    creada = cuentas_panel.crear(con, usuario, clave, rol="superusuario")
    cliente.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
    return creada


def test_login_sin_otp_funciona(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "clave-larga-123"}
    )

    assert respuesta.status_code == 200
    assert "sesion_panel" in respuesta.cookies


def test_login_con_recordarme_pone_una_cookie_de_diez_anios(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "recordarme": True},
    )

    cookie = next(c for c in respuesta.cookies.jar if c.name == "sesion_panel")
    assert cookie.expires - cookie.expires % 100 > 315_000_000


def test_login_con_clave_incorrecta(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "otra-clave"}
    )

    assert respuesta.status_code == 401


def test_login_con_usuario_inexistente(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "nadie", "clave": "loquesea"}
    )

    assert respuesta.status_code == 401


def test_estado_sin_login_no_trae_rol(cliente_sin_loguear):
    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": False, "usuario": None, "rol": None}


def test_estado_despues_de_loguearse(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": True, "usuario": "Administrator", "rol": "superusuario"}


def test_logout_invalida_la_sesion(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cliente_sin_loguear.post("/api/auth/logout")

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()
    assert cuerpo["logueado"] is False


def test_crear_cuenta_sin_sesion_da_401(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 401


def test_requerir_superusuario_rechaza_una_cuenta_menor(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "clave-larga-123"}
    )

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "otra@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 403


def test_superusuario_puede_crear_una_cuenta_menor(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo == {"id": cuerpo["id"], "usuario": "ana@x.com"}


def test_crear_cuenta_ignora_el_rol_del_pedido(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cliente_sin_loguear.post(
        "/api/auth/cuentas",
        json={"usuario": "ana@x.com", "clave": "clave-larga-456", "rol": "superusuario"},
    )

    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.por_usuario(con, "ana@x.com")
    assert creada["rol"] == "menor"


def test_solicitar_recuperacion_siempre_da_el_mismo_mensaje(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/solicitar", json={"usuario": "nadie@x.com"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mensaje"]


def test_solicitar_recuperacion_de_una_cuenta_menor_manda_un_mail(
    cliente_sin_loguear, monkeypatch
):
    from app.servicios import correo

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")

    mandados = []
    monkeypatch.setattr(
        correo, "mandar_codigo_recuperacion",
        lambda destinatario, codigo: mandados.append((destinatario, codigo)),
    )

    cliente_sin_loguear.post("/api/auth/recuperar/solicitar", json={"usuario": "ana@x.com"})

    assert len(mandados) == 1
    assert mandados[0][0] == "ana@x.com"


def test_solicitar_recuperacion_del_superusuario_no_manda_mail(
    cliente_sin_loguear, monkeypatch
):
    from app.servicios import correo

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    mandados = []
    monkeypatch.setattr(
        correo, "mandar_codigo_recuperacion",
        lambda destinatario, codigo: mandados.append((destinatario, codigo)),
    )

    cliente_sin_loguear.post(
        "/api/auth/recuperar/solicitar", json={"usuario": "Administrator"}
    )

    assert mandados == []


def test_confirmar_recuperacion_del_superusuario_con_totp(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")
    codigo = pyotp.TOTP(creada["otp_secreto"]).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "Administrator", "codigo": codigo, "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 200
    login = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "Administrator", "clave": "clave-nueva-456"}
    )
    assert login.status_code == 200


def test_confirmar_recuperacion_de_una_cuenta_menor_con_el_codigo(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": codigo, "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 200


def test_confirmar_recuperacion_con_codigo_incorrecto_da_401(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": "000000", "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 401


def test_confirmar_recuperacion_con_clave_nueva_debil_da_400(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": codigo, "clave_nueva": "corta"},
    )

    assert respuesta.status_code == 400


def test_endpoint_del_panel_sin_sesion_da_401(cliente_sin_loguear):
    assert cliente_sin_loguear.get("/api/sesiones").status_code == 401


def test_endpoint_del_panel_con_sesion_funciona(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    assert cliente_sin_loguear.get("/api/sesiones").status_code == 200


def test_dispositivos_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    """La vinculación de celulares no tiene nada que ver con esto.

    Un token inventado ya da 401 por su cuenta —`_contexto` en
    `dispositivos.py` rechaza cualquier token de operario que no exista,
    sesión de panel aparte—, así que probarlo con eso no demostraría
    nada. Acá se crea un operario y una sesión de inventario de verdad
    estando logueado, se cierra la sesión de panel, y se comprueba que
    `/api/dispositivo/vincular` igual funciona con el token real.
    """
    _crear_superusuario_y_loguearse(cliente_sin_loguear)
    cliente_sin_loguear.post("/api/sesiones", json={"nombre": "Cliente X"})
    operario = cliente_sin_loguear.post(
        "/api/operarios", json={"nombre": "Juan"}
    ).json()

    cliente_sin_loguear.post("/api/auth/logout")

    respuesta = cliente_sin_loguear.post(
        "/api/dispositivo/vincular",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 200


def test_app_apk_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.get("/app.apk")

    assert respuesta.status_code != 401
```

- [ ] **Step 2: Correr la batería completa**

Run: `.\.venv\Scripts\python.exe -m pytest tests -q --rootdir .`
Expected: PASS, todo verde.

- [ ] **Step 3: Commit**

```bash
git add servidor/tests/test_auth_api.py
git commit -m "Reescribe los tests de auth para el login sin OTP y sin bootstrap"
```

---

## Task 11: Frontend — login, Recordarme, recuperación, pestaña Usuarios

**Files:**
- Modify: `servidor/panel/index.html`
- Modify: `servidor/panel/app.js`
- Modify: `servidor/panel/estilos.css`

**Interfaces:**
- Consumes: los endpoints de Tasks 6-9.

Este proyecto no tiene arnés de tests para JS —la verificación de esta
tarea es manual, en el navegador, siguiendo la convención ya establecida
para todo el frontend del panel—.

- [ ] **Step 1: Reescribir la vista de login y sacar la de primera cuenta**

En `servidor/panel/index.html`, **eliminar por completo** la sección
`<section id="vista-primera-cuenta">` (líneas 34-55: desde
`<section id="vista-primera-cuenta"` hasta el `</section>` que le sigue).

Reemplazar `<section id="vista-login">` (antes líneas 57-66) por:

```html
    <section id="vista-login" class="vista oculta">
      <h2>Iniciar sesión</h2>
      <form id="form-login">
        <input id="login-usuario" placeholder="Usuario" required autocomplete="username">
        <input id="login-clave" type="password" placeholder="Contraseña" required autocomplete="current-password">
        <label class="recordarme">
          <input id="login-recordarme" type="checkbox">
          Recordarme
        </label>
        <button>Entrar</button>
      </form>
      <p class="error" id="login-error"></p>
      <button id="ir-a-recuperar" class="enlace" type="button">¿Olvidaste tu contraseña?</button>
    </section>

    <section id="vista-recuperar" class="vista oculta">
      <h2>Recuperar contraseña</h2>
      <form id="form-recuperar-solicitar">
        <input id="recuperar-usuario" placeholder="Usuario" required autocomplete="username">
        <button>Enviar</button>
      </form>
      <p class="ayuda" id="recuperar-mensaje"></p>
      <form id="form-recuperar-confirmar" class="oculta">
        <input id="recuperar-codigo" placeholder="Código" required inputmode="numeric" pattern="[0-9]*" autocomplete="one-time-code" maxlength="6">
        <input id="recuperar-clave-nueva" type="password" placeholder="Contraseña nueva" required autocomplete="new-password">
        <button>Cambiar contraseña</button>
      </form>
      <p class="error" id="recuperar-error"></p>
      <button id="volver-a-login" class="enlace" type="button">Volver a iniciar sesión</button>
    </section>
```

- [ ] **Step 2: Simplificar la pestaña Usuarios, sin el paso de QR**

En `servidor/panel/index.html`, reemplazar el `<section id="vista-usuarios">`
completo (líneas 247-267) por:

```html
    <section id="vista-usuarios" class="vista oculta">
      <h2>Usuarios del panel</h2>
      <p class="ayuda">Quién puede entrar a este panel.</p>

      <form id="form-usuario-nuevo">
        <input id="usuario-nuevo-nombre" placeholder="Mail" required autocomplete="username">
        <input id="usuario-nuevo-clave" type="password" placeholder="Contraseña" required autocomplete="new-password">
        <button>Agregar</button>
      </form>
      <p class="error" id="usuario-nuevo-error"></p>

      <ul id="lista-usuarios" class="lista"></ul>
    </section>
```

- [ ] **Step 3: Reescribir el bloque de Autenticación en `app.js`**

En `servidor/panel/app.js`, reemplazar `cargarEstadoDeAuth` (antes
líneas 937-948) por:

```javascript
/** Pide el estado de auth y muestra la pantalla que corresponda. Nunca
 * dispara ningún otro pedido: eso queda para `arrancarPanel()`, y solo si
 * hay sesión. */
async function cargarEstadoDeAuth() {
  const auth = await pedir("/api/auth/estado");
  estado.usuarioActual = auth.usuario;
  $("#usuario-logueado").textContent = auth.usuario ?? "";
  $('[data-vista="usuarios"]').classList.toggle("oculta", auth.rol !== "superusuario");

  if (!auth.logueado) {
    mostrarSoloVista("login");
  }
  return auth;
}
```

Reemplazar `enviarLogin` (antes líneas 972-990) por:

```javascript
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
        recordarme: $("#login-recordarme").checked,
      }),
    });
    await cargarEstadoDeAuth();
    await arrancarPanel();
  } catch (error) {
    $("#login-error").textContent = error.message;
  }
}

async function solicitarRecuperacion(evento) {
  evento.preventDefault();
  $("#recuperar-mensaje").textContent = "";
  $("#recuperar-error").textContent = "";
  try {
    const respuesta = await pedir("/api/auth/recuperar/solicitar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario: $("#recuperar-usuario").value }),
    });
    $("#recuperar-mensaje").textContent = respuesta.mensaje;
    $("#form-recuperar-confirmar").classList.remove("oculta");
  } catch (error) {
    $("#recuperar-mensaje").textContent = error.message;
  }
}

async function confirmarRecuperacion(evento) {
  evento.preventDefault();
  $("#recuperar-error").textContent = "";
  try {
    await pedir("/api/auth/recuperar/confirmar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario: $("#recuperar-usuario").value,
        codigo: $("#recuperar-codigo").value,
        clave_nueva: $("#recuperar-clave-nueva").value,
      }),
    });
    mostrarSoloVista("login");
    $("#login-error").textContent = "Contraseña cambiada. Iniciá sesión de nuevo.";
    $("#form-recuperar-confirmar").classList.add("oculta");
    $("#recuperar-mensaje").textContent = "";
  } catch (error) {
    $("#recuperar-error").textContent = error.message;
  }
}
```

Borrar por completo la función `crearCuentaYMostrarQr` (antes líneas
997-1023): ya no la usa nadie —el alta de la primera cuenta desapareció,
y el alta de un usuario nuevo (Step 4 de acá abajo) no muestra QR—.

- [ ] **Step 4: Actualizar `conectarEventosDeAuth`**

Reemplazar la función completa (antes líneas 1025-1066) por:

```javascript
function conectarEventosDeAuth() {
  $("#form-login").addEventListener("submit", enviarLogin);
  $("#cerrar-sesion-panel").addEventListener("click", cerrarSesionDePanel);

  $("#ir-a-recuperar").addEventListener("click", () => mostrarSoloVista("recuperar"));
  $("#volver-a-login").addEventListener("click", () => mostrarSoloVista("login"));
  $("#form-recuperar-solicitar").addEventListener("submit", solicitarRecuperacion);
  $("#form-recuperar-confirmar").addEventListener("submit", confirmarRecuperacion);

  $("#form-usuario-nuevo").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    $("#usuario-nuevo-error").textContent = "";
    try {
      await pedir("/api/auth/cuentas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          usuario: $("#usuario-nuevo-nombre").value,
          clave: $("#usuario-nuevo-clave").value,
        }),
      });
      $("#usuario-nuevo-nombre").value = "";
      $("#usuario-nuevo-clave").value = "";
      await cargarUsuarios();
    } catch (error) {
      $("#usuario-nuevo-error").textContent = error.message;
    }
  });

  $("#lista-usuarios").addEventListener("click", (evento) => {
    const id = evento.target.dataset.bajaUsuario;
    if (id) darDeBajaUsuario(id);
  });
}
```

- [ ] **Step 5: CSS para "Recordarme" y los links de texto**

En `servidor/panel/estilos.css`, agregar al final:

```css
.recordarme {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9rem;
  color: var(--tenue);
}

.recordarme input { width: auto; }

button.enlace {
  background: none;
  border: none;
  color: var(--acento);
  text-decoration: underline;
  padding: 0.3rem 0;
  cursor: pointer;
}
```

- [ ] **Step 6: Probar a mano en el navegador**

Levantar el servidor de prueba (ver "Verificar de verdad" más abajo) y
confirmar en el navegador:
1. Login con usuario+contraseña, sin ningún campo de OTP visible.
2. "Recordarme" tildado: cerrar el navegador entero y volver a abrirlo
   —sigue logueado—.
3. "¿Olvidaste tu contraseña?" lleva a la pantalla de recuperación; con
   el superusuario, el código de la app autenticadora cambia la
   contraseña; con una cuenta de rol menor (usando `CONTROL_DE_STOCK_MAIL`
   apuntando a un archivo de prueba con una casilla real), el mail
   llega con el código.
4. Con una cuenta de rol menor logueada, la pestaña "Usuarios" no
   aparece en el menú.
5. Crear un usuario nuevo desde "Usuarios": no aparece ningún paso de
   QR, la cuenta queda lista al toque.

- [ ] **Step 7: Commit**

```bash
git add servidor/panel/index.html servidor/panel/app.js servidor/panel/estilos.css
git commit -m "Rehace el login del panel: sin OTP, con Recordarme y recuperación"
```

---

## Task 12: Documentación

**Files:**
- Modify: `docs/superpowers/deuda-conocida.md`

**Interfaces:**
- Consumes: nada de código; documenta el resultado final.

- [ ] **Step 1: Reescribir la sección "Login del panel"**

Reemplazar la sección completa `## Login del panel` de
`docs/superpowers/deuda-conocida.md` por:

```markdown
## Login del panel

**Un solo superusuario, para siempre.** Se crea a mano, directo contra
la base — no hay, ni va a haber, ningún camino en el panel para crear
un segundo superusuario ni para ascender una cuenta de rol menor. Si
alguna vez hiciera falta cambiarlo, es la misma clase de operación que
"borrá `inventario.db` para empezar de cero": cirugía directa sobre la
base.

**Recuperación sin límite de intentos.** Ni el código OTP del
superusuario ni el código por mail de una cuenta de rol menor tienen un
freno de reintentos — mismo criterio que el login: red del depósito, sin
exposición a internet. Es un poco más sensible que el login porque
termina en un cambio de contraseña, pero se acepta el mismo riesgo por
consistencia, no por descuido.

**Una falla al mandar el mail de recuperación no se le avisa a quien la
pide.** El paso 1 de "olvidé mi contraseña" siempre contesta el mismo
mensaje genérico, exista la cuenta o no, sea del rol que sea — así que
si el mail falla (sin internet, credenciales de Gmail mal puestas), la
persona ve el mismo mensaje de éxito y nunca le llega nada. El error
completo queda en la consola del servidor (`print`, en la misma ventana
que "Dejá esta ventana abierta mientras dure el conteo"), no en ningún
otro lado. Si esto resulta confuso en el uso real, vale la pena
revisarlo.

**Ninguna cuenta puede cambiar su propia contraseña estando logueada.**
Se pasa por "olvidé mi contraseña" incluso para eso. Si en el uso real
esto resulta incómodo, es una extensión chica y acotada.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/deuda-conocida.md
git commit -m "Actualiza la deuda conocida del login con roles y recuperación"
```
