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

## Configurar la recuperación de contraseña por mail

Las cuentas de rol menor recuperan la contraseña por un código que
llega por mail (Administrator la recupera con TOTP, sin mail de por
medio). Ese envío necesita una casilla de Gmail con contraseña de
aplicación, en `C:\clientes\claves\control-de-stock-mail.properties` —o
la ruta que indique `CONTROL_DE_STOCK_MAIL`—.
`servidor/correo-de-ejemplo.properties` documenta el formato. Sin ese
archivo, o con campos sin completar, el panel arranca igual: recién
falla al pedirse una recuperación, con un mensaje que explica qué falta.
