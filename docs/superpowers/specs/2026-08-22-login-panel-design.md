# Login del panel — diseño

Fecha: 2026-08-22

## El problema

El panel (`servidor/panel/`) no tiene ningún control de acceso: quien
entra a la IP del servidor entra directo al tablero, ve el maestro, los
tokens de vinculación de los operarios, y puede borrar sesiones. Pedido
del cliente: varias cuentas (usuario y contraseña), cada una con un
segundo factor por código de un solo uso (OTP).

Este documento no toca el celular ni `dispositivos.router` — los
operarios siguen vinculándose con su token de siempre, sin relación con
esto. Tampoco toca `/app.apk`: lo descarga el celular directo desde el
QR de instalación, sin sesión de panel de por medio.

## Por qué TOTP y no otra cosa

CLAUDE.md fija que durante el conteo puede no haber internet, y el
servidor corre en una PC del depósito sin garantía de conexión. Un OTP
por SMS o email necesita mandar algo por una red que puede no estar. TOTP
(RFC 6238 — el código de 6 dígitos que cambia cada 30 segundos, el mismo
mecanismo de Google Authenticator o Authy) no manda nada: una vez que el
secreto está en la app autenticadora del responsable, el código se genera
y se verifica sin ninguna conexión, en los dos lados.

## Arquitectura de sesión

Mismo patrón que ya usa `operario.token_dispositivo`: un token al azar
(`secrets.token_urlsafe(32)`), guardado en una tabla, verificado contra
la base en cada pedido. Nada de JWT: sumaría una dependencia nueva
(PyJWT) sin ninguna ventaja a esta escala —un servidor, un puñado de
cuentas—, y revocar una sesión antes de tiempo con JWT stateless exige de
todos modos una lista de baja en algún lado, que es exactamente lo que
esto ya tiene con la tabla.

El token viaja en una cookie `httponly`, `samesite=lax`, **sin**
`secure`: el panel se sirve por HTTP plano en la red del depósito (ver
`app/red.py`), y una cookie `secure` sobre HTTP nunca se manda —el login
funcionaría en la demo y fallaría en la instalación real, sin ningún
error visible.

## Esquema nuevo

```sql
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

Nombres separados de `operario`/`token_dispositivo` a propósito: son dos
identidades completamente distintas —el operario que escanea códigos, la
cuenta que administra el panel— y compartir tabla o vocabulario las
confundiría la primera vez que alguien lea el esquema.

`clave_hash` guarda un string autodescriptivo, `pbkdf2_sha256$<iteraciones>$<sal_b64>$<hash_b64>`,
con `hashlib.pbkdf2_hmac` de la librería estándar —no hace falta sumar
`bcrypt`/`passlib` para esto—. `otp_secreto` es el secreto TOTP en
base32, como lo pide el estándar.

`sesion_panel.creado_en` usa el mismo formato ISO 8601 UTC de
`app/reloj.py` que el resto del sistema. Una sesión vence a los 30 días
de creada —se recalcula en cada verificación, no hay un trabajo de
limpieza aparte—.

## Dependencias nuevas

`pyotp` para generar y verificar TOTP: es chica, sin dependencias
pesadas, y es la biblioteca estándar de facto para esto en Python. No
tiene sentido reimplementar HMAC-based OTP a mano —a diferencia del
resto de este proyecto, que evita dependencias para lógica de negocio
propia, esto es criptografía, y ahí «no inventes tu propia
implementación» pesa más que «una dependencia menos».

`segno` ya está: se reutiliza para el QR del secreto TOTP (`otpauth://`),
igual que ya se usa para los QR de vinculación e instalación.

## Los endpoints

Un router nuevo, `app/api/auth.py`, montado en `/api/auth`, **sin**
autenticación —es el único lugar donde no puede haberla, por definición—:

- `GET /api/auth/estado` → `{logueado, usuario, hay_cuentas}`. Lo primero
  que pide el panel al cargar, para decidir qué pantalla mostrar: si
  `hay_cuentas` es falso, el alta de la primera cuenta; si es verdadero y
  `logueado` es falso, el login; si `logueado` es verdadero, el panel de
  siempre.
- `POST /api/auth/login` con `{usuario, clave, codigo_otp}`, los tres
  juntos en un solo formulario —no en dos pasos—. Verifica los tres antes
  de contestar: un error genérico, *"Usuario, contraseña o código
  incorrecto"*, sin decir cuál de los tres falló, para no confirmarle a
  quien prueba a ciegas que acertó el usuario. Éxito: crea la fila en
  `sesion_panel`, pone la cookie.
- `POST /api/auth/logout` → borra la fila de `sesion_panel` del token de
  la cookie, la limpia. No hace falta estar logueado para llamarlo —una
  cookie vencida o inválida no rompe nada, simplemente no hay nada que
  borrar—.
- `POST /api/auth/cuentas` con `{usuario, clave}` → crea la cuenta,
  genera el secreto TOTP, y devuelve **una sola vez**,
  `{id, usuario, otpauth_url, qr_svg}`, con el QR ya renderizado en SVG
  —mismo mecanismo que `vinculacion.svg()`—. Sin cuentas todavía, el
  pedido se permite sin sesión —es el arranque—; con al menos una cuenta
  ya creada, exige sesión válida como cualquier otro endpoint del panel.
  Esta es la única regla condicional de todo el diseño, y por eso vive
  acá adentro en vez de en el `dependencies` del router: expresar «sin
  sesión solo si la tabla está vacía» como una dependencia de FastAPI
  sería más confuso que un `if` explícito al principio de la función.

**Deliberado: no hay forma de volver a pedir el QR después.** Ni
`GET /api/auth/cuentas/{id}/qr` ni nada parecido —esa ruta, autenticada o
no, sería una forma de que cualquiera con sesión de panel se lleve el
segundo factor de una cuenta ajena, lo que anula la mitad del sentido de
tener un segundo factor. Si alguien no llega a escanear el código a
tiempo, la cuenta se borra y se crea de nuevo. No hay «recuperación» de
TOTP en este diseño —perder el teléfono con la app autenticadora exige
que otra cuenta ya logueada borre y recree la cuenta afectada, o cirugía
directa sobre la base como último recurso, en la misma línea que
«borrá `inventario.db` para empezar de cero» ya documentado en el
`README.md`—. Se anota en la deuda conocida al cerrar esta rama.

`app/repos/cuentas_panel.py` concentra el acceso a `cuenta_panel` y
`sesion_panel` —`crear`, `por_usuario`, `listar`, `desactivar`,
`crear_sesion`, `sesion_valida`, `borrar_sesion`—, mismo estilo que
`repos/operarios.py`.

`panel.router` gana un `Depends` a nivel de router
(`APIRouter(prefix="/api", dependencies=[Depends(verificar_sesion)])`),
que lee la cookie, busca el token en `sesion_panel`, verifica que no
venció, y tira 401 si falta o es inválido. Una sola línea cubre los ~25
endpoints existentes sin tocarlos uno por uno.

`dispositivos.router` y el `GET /app.apk` de `main.py` no se tocan: son
routers y rutas aparte, fuera de esta lista de dependencias.

## El panel (frontend)

`app.js` pide `/api/auth/estado` antes de cualquier otra cosa. Según la
respuesta, muestra una de tres pantallas nuevas —alta de la primera
cuenta, login, o el panel de siempre— controladas con el mismo mecanismo
`vista`/`oculta` que ya separa las pestañas actuales. Ninguna pestaña ni
pedido a `/api/*` (fuera de `/api/auth/*`) se dispara hasta que
`logueado` sea verdadero.

Pestaña nueva, **Usuarios** —mismo lugar en el menú que Operarios—: alta
de cuentas (`POST /api/auth/cuentas`, mostrando el QR una vez, con un
aviso explícito de que no se puede volver a ver), lista de cuentas
activas, y dar de baja —mismo patrón que `operarios.desactivar`—. La
propia cuenta logueada no se puede dar de baja a sí misma, para no
dejar el panel sin ninguna cuenta activa por accidente.

Un botón de **Cerrar sesión** en la barra superior, al lado del de tema.

## Qué queda afuera a propósito

- **Recuperación de OTP perdido** — ver arriba.
- **Rate limiting / bloqueo por intentos fallidos** — esto corre en la
  red de un depósito, no expuesto a internet; agregarlo ahora es
  complejidad sin una amenaza real que la justifique hoy.
- **Cambiar la propia contraseña o el propio OTP** — se puede crear una
  cuenta nueva y dar de baja la vieja. Si en el uso real esto resulta
  incómodo, es una extensión chica y acotada, no hace falta preverla
  ahora.
- **Roles o permisos distintos entre cuentas** — todas las cuentas del
  panel pueden hacer lo mismo. No hay ningún pedido de diferenciarlas.

## Testing

Los ~500 tests existentes de `test_api.py` y `test_panel_estatico.py`
pegan contra `panel.router` sin ninguna sesión: agregar el `Depends` a
nivel de router los rompe a todos de una. La fixture compartida `cliente`
pasa a loguearse una vez al arrancar —crea una cuenta de prueba con
`cuentas_panel.crear` directo contra la base (sin pasar por el endpoint,
para no encadenar un test con otro) y pisa la cookie del `TestClient`— así
los tests existentes siguen probando lo que ya probaban, autenticados
por default. Los tests de `auth.py` en sí —login, logout, alta de
cuenta, bloqueo sin sesión— usan un cliente aparte, sin loguear, para
poder probar los 401 y el flujo completo.

`app/servicios/autenticacion.py` concentra el hash de contraseña y la
verificación TOTP como funciones puras, sin tocar la base ni el
request —se prueban solas, como el resto de `servicios/`—.
`verificar_sesion`, el `Depends` que usa `panel.router`, vive en
`app/api/auth.py` junto con el resto de esa API, e importa
`cuentas_panel.sesion_valida` para resolverlo.
