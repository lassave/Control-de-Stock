# Roles y recuperación de contraseña — diseño

Fecha: 2026-08-23

## El problema

El login del panel (mergeado hoy, `docs/superpowers/specs/2026-08-22-login-panel-design.md`)
tiene un solo tipo de cuenta: todas piden usuario + contraseña + OTP en
cada login, y cualquiera puede crear cuentas nuevas. El cliente pidió,
en vivo, apenas terminó de probarlo:

- Que exista un **superusuario** (Administrator) distinto de las cuentas
  que ese superusuario cree, y que solo el superusuario pueda gestionar
  cuentas.
- Que el login sea más simple: usuario + contraseña, sin pedir el OTP en
  cada entrada.
- Un botón **"Recordarme"** que evite tener que loguearse de nuevo.
- Una forma de **recuperar la contraseña** si se olvida: con el código
  OTP para el superusuario, con un código por mail para las demás.

Este documento reemplaza, para estas partes, lo que describe el spec del
2026-08-22: el login deja de pedir OTP en cada entrada, y el alta de
cuentas deja de tener una ventana sin sesión. Todo lo demás de ese spec
—la tabla `sesion_panel`, el hash de contraseña, el patrón de sesión por
cookie, que `dispositivos.router` y `/app.apk` quedan afuera— sigue
vigente sin cambios.

## Roles

Dos roles, con una sola diferencia de permisos entre ellos:

- **`superusuario`**: puede hacer todo lo que ya podía hacer cualquier
  cuenta del panel, más gestionar cuentas (pestaña Usuarios).
- **`menor`**: todo lo mismo, salvo gestionar cuentas.

**Hay exactamente un superusuario, para siempre.** Se crea a mano,
directo contra la base, nunca a través de un endpoint. No existe —ni va
a existir— un camino en el panel para crear un segundo superusuario, ni
para ascender una cuenta de rol `menor`. Si alguna vez hiciera falta
cambiarlo, es la misma clase de operación que "borrá `inventario.db` para
empezar de cero": cirugía directa sobre la base, documentada, no una
funcionalidad del producto.

`cuenta_panel` suma una columna:

```sql
ALTER TABLE cuenta_panel ADD COLUMN rol TEXT NOT NULL DEFAULT 'menor'
    CHECK (rol IN ('superusuario', 'menor'));
```

(la base se recrea desde cero en cada instalación nueva —no hay sistema
de migraciones en este proyecto—, así que en la práctica esto se suma
directo a la sentencia `CREATE TABLE` de `esquema.sql`; el `ALTER TABLE`
de arriba es solo para dejar la intención documentada).

No hace falta una columna `correo` aparte. Para una cuenta de rol
`menor`, el `usuario` que ya existe **es** su dirección de mail —ahí se
manda el código de recuperación—. Para el superusuario, `usuario` sigue
siendo un nombre común, sin relación con ningún mail.

## Login

Un solo formulario, para las dos cuentas: usuario + contraseña. El campo
de OTP desaparece del login normal.

```
POST /api/auth/login
{ "usuario": "...", "clave": "...", "recordarme": true|false }
```

Igual que hoy: usuario+clave inválidos devuelven el mismo mensaje
genérico ("Usuario o contraseña incorrecto"), sin decir cuál falló.

`sesion_panel` suma una columna:

```sql
ALTER TABLE sesion_panel ADD COLUMN recordar INTEGER NOT NULL DEFAULT 0;
```

`sesion_valida()` sigue chequeando el vencimiento de 30 días **solo** si
`recordar = 0`. Con `recordar = 1`, la sesión no vence por tiempo; el
único final es un logout explícito (`POST /api/auth/logout`, que ya
borra la fila de `sesion_panel` sin cambios) o que la cuenta se dé de
baja (`sesion_valida` ya invalida sesiones de cuentas inactivas, sin
cambios).

## Recuperar contraseña

Una sola pantalla para las dos cuentas, en dos pasos, para no revelar con
la respuesta si un usuario existe ni de qué tipo de cuenta se trata:

```
POST /api/auth/recuperar/solicitar
{ "usuario": "..." }
→ 200 siempre, mismo cuerpo: {"mensaje": "Si la cuenta existe, ya podés poner el código."}
```

Atrás de escena: si el usuario no existe, no hace nada. Si es el
superusuario, tampoco hace nada —el código ya vive en su app
autenticadora, no hay nada que generar ni mandar—. Si es una cuenta
`menor`, genera un código de 6 dígitos al azar, lo guarda hasheado
(mismo `hashlib.pbkdf2_hmac` que ya usa `autenticacion.py`, no hace
falta un segundo esquema de hash) con vencimiento a los 15 minutos, y lo
manda por mail a esa dirección (ver más abajo).

```sql
CREATE TABLE IF NOT EXISTS codigo_recuperacion (
    cuenta_id  INTEGER PRIMARY KEY REFERENCES cuenta_panel(id),
    codigo_hash TEXT NOT NULL,
    creado_en   TEXT NOT NULL
);
```

Una fila por cuenta —pedir un código nuevo reemplaza al anterior, no lo
acumula—.

```
POST /api/auth/recuperar/confirmar
{ "usuario": "...", "codigo": "...", "clave_nueva": "..." }
```

El servidor valida el código distinto según el rol: `pyotp` contra el
`otp_secreto` de la cuenta si es superusuario, o contra
`codigo_recuperacion` (hasheado, con el vencimiento de 15 minutos) si es
`menor`. Código inválido o vencido: mismo mensaje genérico que el login,
sin distinguir motivo. Válido: cambia `clave_hash` (misma validación de
mínimo 8 caracteres que ya tiene `cuentas_panel.crear`), borra la fila de
`codigo_recuperacion` si había una, y **cierra todas las sesiones
abiertas de esa cuenta** (`DELETE FROM sesion_panel WHERE cuenta_id = ?`)
—incluida la de quien se había quedado logueado en otro navegador—.

## Envío de mail

`smtplib` de la biblioteca estándar —sin sumar una dependencia nueva—,
contra una casilla de Gmail con contraseña de aplicación (la opción más
simple para un solo depósito). Las credenciales viven en un archivo de
configuración fuera del repositorio, mismo patrón que ya usa la firma del
APK: un archivo de ejemplo documenta el formato sin secretos, la ruta
real se toma de una variable de entorno, y sin ese archivo o con
credenciales incompletas el sistema **arranca igual** —el mail solo hace
falta para recuperar contraseña, no para el uso normal del panel—. Si el
envío falla en el momento (sin internet, credenciales mal puestas), el
paso 1 de la recuperación **no lo distingue del caso de éxito** —misma
razón que el resto del diseño: una respuesta distinta ahí confirmaría
que la cuenta existe y es de rol menor—. El error completo queda en la
consola del servidor. Documentado como deuda conocida.

## Alta de cuentas: se cierra la ventana sin sesión

`POST /api/auth/cuentas` deja de tener la rama "sin cuentas todavía, se
permite sin sesión" del spec anterior —ese hueco documentado en la deuda conocida
desaparece del todo, no se ajusta—. Pasa a exigir sesión de
**superusuario** siempre, sin excepción, y crea únicamente cuentas con
`rol = 'menor'`: el rol no es un parámetro que mande el cliente, lo fija
el servidor.

La pantalla "Creá la primera cuenta" del panel se elimina: no hay ningún
estado del sistema en el que tenga sentido mostrarla, porque siempre va
a existir ya un superusuario (creado a mano al instalar). Cualquier
instalación nueva de este sistema —no solo la de este cliente— va a
necesitar ese paso manual.

## Permisos

`verificar_sesion` ya devuelve la cuenta logueada; ese dict suma `rol`.
Una dependencia nueva, `requerir_superusuario` (envuelve a
`verificar_sesion`, chequea `rol == "superusuario"`, 403 si no), protege:

- `GET /api/usuarios`
- `POST /api/usuarios/{id}/desactivar`
- el endpoint de alta de cuentas

El resto de los ~25 endpoints del panel quedan como están: cualquier
cuenta logueada, sin distinción de rol.

## Riesgo aceptado

La recuperación no tiene límite de intentos —mismo criterio ya aceptado
para el login: red del depósito, sin exposición a internet, sin rate
limiting en ningún lado del panel—. Es un poco más sensible que el login
porque termina en un cambio de contraseña, pero se acepta el mismo
riesgo por consistencia con el resto del diseño, no por descuido.

## Qué queda afuera a propósito

- Roles más finos que "puede gestionar cuentas o no".
- Que un superusuario pueda ceder o compartir su rol.
- Cambiar la propia contraseña estando logueado, sin pasar por "olvidé
  mi contraseña" (ya estaba afuera del spec anterior, sigue afuera).
- Un segundo superusuario, bajo cualquier circunstancia, desde el panel.

## Testing

Los tests existentes de `test_auth_api.py`/`test_repos_cuentas_panel.py`
que arman el login con `codigo_otp` se actualizan al nuevo contrato
(`{usuario, clave, recordarme}`, sin OTP). Nuevos tests cubren: que
`requerir_superusuario` devuelve 403 a una cuenta `menor`; que
`POST /api/auth/cuentas` sin sesión devuelve 401 siempre (ya no hay
bootstrap); que una cuenta creada por ese endpoint sale con `rol =
'menor'` pase lo que pase en el cuerpo del pedido; que
`sesion_valida` no vence una sesión con `recordar = 1` aunque pasen más
de 30 días (usando `app/reloj.py` para simular el tiempo, mismo patrón
que ya usan los tests de sesión existentes); y el flujo completo de
recuperación para cada rol, con el envío de mail mockeado —el test no
puede depender de una casilla de Gmail real—.
