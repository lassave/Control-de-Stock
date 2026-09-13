# Control de Stock — guía para agentes

Toma de inventario con escaneo de códigos de barras. Un servidor FastAPI +
SQLite corre en una PC del cliente; los celulares se conectan por la WiFi
del lugar. El `README.md` es para quien **usa** el sistema; esto es para
quien lo **desarrolla**.

## Comandos

El `python` del PATH en esta máquina es el acceso directo de la Microsoft
Store: abre la tienda y no ejecuta nada. **Siempre el intérprete del venv
por ruta.**

```powershell
# Tests (rápido, sin levantar el servidor)
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor

# Un archivo puntual
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_tablero.py -v --rootdir .\servidor

# Levantar el servidor como lo hace el cliente
.\"Iniciar servidor.bat"          # 127.0.0.1:8000 y la IP de la red
```

La base `servidor/inventario.db` se crea sola al arrancar y está en
`.gitignore`. Borrala para empezar de cero.

## Reglas que no se negocian

- **Cantidades en milésimas, importes en centavos, siempre `int`.** `24 UN`
  es `24000`; `3,5 kg` es `3500`; `$25,00` es `2500`. SQLite usa punto
  flotante para `REAL` y un inventario suma miles de veces. Las columnas
  tienen `CHECK (typeof(...) = 'integer')` para que un decimal colado no
  pase en silencio.
- **`stock_sistema` y `costo_unitario` nunca salen por
  `/api/dispositivo/*`.** El conteo es a ciegas: el dato no debe existir en
  el celular ni siquiera oculto. Por eso los endpoints de dispositivo viven
  en su propio módulo, para que la regla se revise de un vistazo.
- **Nada externo en el navegador.** Ni CDN, ni fuentes, ni librerías
  remotas: durante el conteo puede no haber internet. Hay un test que lo
  verifica.
- **Todo dato del servidor se escapa antes de ir al HTML.** El maestro lo
  escribe el cliente; un `CAÑO 3/4 <PVC>` alcanza para romper la tabla. Hay
  un test que lo verifica.
- **Fechas ISO 8601 UTC** como texto: `2026-08-11T14:32:05Z`. La única
  fuente es `app/reloj.py`.
- **Nada se edita ni se borra.** Una corrección es una anulación que apunta
  al `uuid` original.
- **Textos en castellano rioplatense**, sin jerga técnica, también en los
  mensajes de error.
- **Mensajes de commit en castellano, en presente, describiendo el
  efecto**, y el cuerpo explica *por qué*, no *qué*.

## Estructura

```
servidor/app/repos/       hablan con la base (SQL directo, sin ORM)
servidor/app/servicios/   reglas de negocio, se prueban sin levantar nada
servidor/app/api/         panel.py, dispositivos.py y auth.py
servidor/panel/           HTML/CSS/JS sin dependencias
docs/superpowers/specs/   diseños aprobados
docs/superpowers/plans/   planes de implementación
```

La lógica vive en los servicios y se prueba sin servidor. Los routers solo
traducen HTTP.

## Cómo se trabaja acá

TDD, sin excepciones: test que falla, implementación, test que pasa, commit.
Los planes de `docs/superpowers/plans/` se ejecutan tarea por tarea.

Verificar de verdad, no por inferencia: si algo tiene que andar en el
navegador o en la red, se levanta y se prueba. Varios defectos de este
proyecto —el `.bat` con saltos de línea Unix, `localhost` resolviendo a
IPv6— solo aparecieron ejecutando, con los tests en verde.

## Entorno Android

Instalado en esta máquina, sin Android Studio:

```
JAVA_HOME    C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot
ANDROID_HOME C:\Users\Pablo\AppData\Local\Android\Sdk
Gradle       C:\Gradle\gradle-8.7\bin\gradle.bat
```

SDK 34, build-tools 34.0.0, platform-tools. Verificado compilando un APK.
Las pruebas de escaneo se hacen en un celular real por USB (`adb devices`);
no hay emulador instalado.

## Publicar una versión firmada

Doble clic en `Publicar app.bat`, o desde `celular/`:

```powershell
C:\Gradle\gradle-8.7\bin\gradle.bat :app:publicar --no-daemon
```

La firma se lee de `C:\clientes\claves\control-de-stock.properties`, o de la
ruta que indique la variable de entorno `CONTROL_DE_STOCK_FIRMA`. Sin ese
archivo, o con las contraseñas sin completar, la compilación de release
falla a propósito con un mensaje que explica qué falta.
`celular/claves-de-ejemplo.properties` documenta el formato del archivo, sin
secretos. La clave real y su backup nunca entran al repositorio.

El número de versión sale solo de `git rev-list --count HEAD`, así que
**esta rama hay que mergearla con fast-forward o merge normal, nunca
squash**: un squash-merge dejaría a `master` con menos commits que los que
ya tiene instalados un celular real, y la próxima publicación quedaría por
debajo del número ya instalado — Android la rechazaría con un error que no
explica nada.

## Crear el superusuario del panel

Hay exactamente un superusuario del panel, para siempre —no hay ningún
endpoint que lo cree—. Se crea una sola vez, corriendo:

```powershell
.\servidor\.venv\Scripts\python.exe servidor\crear_superusuario.py
```

Pide usuario y contraseña, y muestra un código QR (guardado como
`servidor/superusuario-qr.svg`, hay que borrarlo después de escanearlo)
para configurar la app autenticadora. Ese código no se puede volver a
generar: si se pierde el acceso al segundo factor, hay que correr este
script de nuevo con un usuario distinto —no se puede reusar el mismo
mientras la cuenta vieja siga activa— o dar de baja la cuenta vieja
primero desde la base.

**Nota para esta instalación en particular:** el servidor productivo de
este cliente ya creó las tablas `cuenta_panel`/`sesion_panel` con el
esquema viejo (sin roles, todavía vacías). Antes de correr este script
ahí, hay que borrar esas dos tablas a mano para que se recreen con el
esquema nuevo —el resto de la base (inventario real) no se toca—.

## Migrar una base ya creada de «sesión» a «proyecto»

La entidad que antes se llamaba `sesion` (tabla, columnas `sesion_id` /
`sesion_origen_id`, índices) pasó a llamarse `proyecto` en todo el código.
`servidor/app/esquema.sql` usa `CREATE TABLE IF NOT EXISTS`, así que una
base ya creada con el esquema viejo no se actualiza sola. Antes de poner
en marcha esta versión sobre una `servidor/inventario.db` que ya existe
—la de este cliente incluida—, hay que correr una sola vez, con el
servidor apagado:

```powershell
.\servidor\.venv\Scripts\python.exe -c "
import sqlite3
con = sqlite3.connect('servidor/inventario.db')
con.executescript('''
    ALTER TABLE sesion RENAME TO proyecto;
    ALTER TABLE articulo RENAME COLUMN sesion_id TO proyecto_id;
    ALTER TABLE pasada RENAME COLUMN sesion_id TO proyecto_id;
    ALTER TABLE conteo RENAME COLUMN sesion_id TO proyecto_id;
    ALTER TABLE evento_auditoria RENAME COLUMN sesion_id TO proyecto_id;
    ALTER TABLE codigo_aprendido RENAME COLUMN sesion_origen_id TO proyecto_origen_id;
    DROP INDEX IF EXISTS ix_sesion_abierta;
    CREATE UNIQUE INDEX IF NOT EXISTS ix_proyecto_abierta ON proyecto(estado) WHERE estado = 'abierta';
    DROP INDEX IF EXISTS ix_conteo_sesion;
    CREATE INDEX IF NOT EXISTS ix_conteo_proyecto ON conteo(proyecto_id, operario_id);
''')
con.commit()
"
```

`ALTER TABLE ... RENAME TO` y `RENAME COLUMN` actualizan solos las
cláusulas `REFERENCES` de las demás tablas: no hace falta tocarlas a
mano. No toca `sesion_panel` —esa tabla es del login, no de esta
entidad—. La tabla `cuenta_panel`/`sesion_panel` de la nota de arriba y
esta migración son independientes, pero si las dos aplican en la misma
instalación conviene hacerlas en la misma visita.

No confundir con la vinculación del celular: la app Android guarda su
propia copia local de `sesionId` (ahora `proyectoId`) en su base Room,
y se migra sola al abrirse con la versión nueva del APK, sin que haya
que tocar nada a mano en el teléfono.

## Configurar la recuperación de contraseña por mail

Las cuentas de rol menor recuperan la contraseña por un código que
llega por mail (Administrator la recupera con TOTP, sin mail de por
medio). Ese envío necesita una casilla de Gmail con contraseña de
aplicación, en `C:\clientes\claves\control-de-stock-mail.properties` —o
la ruta que indique `CONTROL_DE_STOCK_MAIL`—.
`servidor/correo-de-ejemplo.properties` documenta el formato. Sin ese
archivo, o con campos sin completar, el panel arranca igual: recién
falla al pedirse una recuperación, con un mensaje que explica qué falta.
