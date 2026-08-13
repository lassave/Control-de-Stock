# El APK firmado que se baja desde el panel — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** que un celular se sume al inventario escaneando el QR del panel,
sin cable, y que las actualizaciones siguientes se instalen encima sin que el
operario pierda lo que todavía no subió.

**Arquitectura:** el APK se compila firmado en esta máquina con una clave que
vive fuera del proyecto, y una tarea de Gradle lo deja donde el panel ya lo
busca junto a un archivo con su versión. El servidor informa esa versión y la
fecha del archivo; el panel las muestra al lado del QR que ya existe.

**Herramientas:** Gradle, Android SDK, FastAPI, pytest, JavaScript sin
dependencias.

**Especificación:**
`docs/superpowers/specs/2026-08-13-apk-firmado-desde-el-panel-design.md`

## Global Constraints

- **Fechas ISO 8601 UTC como texto** (`2026-08-13T14:32:05Z`). La única fuente
  es `servidor/app/reloj.py`.
- **Nada externo en el navegador**: ni CDN, ni fuentes, ni librerías remotas.
  Hay un test que lo verifica.
- **Todo dato del servidor se escapa antes de ir al HTML.** Lo que va por
  `textContent` no interpreta HTML y no se escapa; lo que arma marcado, sí.
  Hay un test que lo audita.
- **La clave de firma nunca entra al repositorio ni a la carpeta del
  proyecto.** El `.gitignore` ya excluye `*.apk`, `*.keystore` y `*.jks`.
- **Textos en castellano rioplatense**, sin jerga técnica, también en los
  mensajes de error — incluidos los que salen de Gradle y del `.bat`.
- **Mensajes de commit en castellano, en presente, describiendo el efecto**;
  el cuerpo explica *por qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- **Los comentarios explican por qué, no qué.**
- **TDD sin excepciones** donde haya algo que probar.

## Entorno

El `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta
nada: siempre el intérprete del venv por ruta.

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
cd "C:\clientes\Control de Stock\celular" ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
```

Android, ya instalado en esta máquina:

```
JAVA_HOME    C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot
ANDROID_HOME C:\Users\Pablo\AppData\Local\Android\Sdk
Gradle       C:\Gradle\gradle-8.7\bin\gradle.bat
```

## Lo que ya existe y se consume

- `RUTA_APK = <raíz del proyecto>/app.apk` en `servidor/app/api/panel.py:21`.
- `GET /api/instalacion` → `{"disponible": bool, "url": str}`, y
  `GET /api/instalacion/qr` → el SVG. Los dos ya andan y tienen tests.
- `GET /app.apk` entrega el archivo, en `servidor/app/main.py`.
- El bloque `#instalacion` en `servidor/panel/index.html:87`, adentro de la
  pestaña de Operarios, con su `#qr-instalacion`. Se desesconde solo cuando
  `/api/instalacion` dice que hay APK.
- `cargarInstalacion()` en `servidor/panel/app.js:334`.
- Las fixtures `sin_apk` y `con_apk` en `servidor/tests/test_api.py:550`, que
  apuntan `RUTA_APK` a un archivo temporal.
- El molde del `.bat`: `Iniciar servidor.bat` en la raíz.
- `reloj.ahora()` en `servidor/app/reloj.py`.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `servidor/app/reloj.py` | Suma `desde_epoch`, para dar formato a una fecha que ya existe. |
| `servidor/app/api/panel.py` | `/api/instalacion` suma `version` y `publicado`. |
| `servidor/panel/index.html` | El renglón donde va la versión. |
| `servidor/panel/app.js` | Lo completa por `textContent`. |
| `celular/app/build.gradle.kts` | La firma de release, el número de versión y la tarea `publicar`. |
| `Publicar app.bat` *(nuevo)* | Lo que se toca dos veces para publicar. |

---

### Task 1: El servidor informa qué está ofreciendo

**Files:**
- Modify: `servidor/app/reloj.py`
- Modify: `servidor/app/api/panel.py`
- Test: `servidor/tests/test_api.py`

**Interfaces:**
- Produces:
  - `reloj.desde_epoch(segundos: float) -> str` — ISO 8601 UTC
  - `GET /api/instalacion` → `{"disponible", "url", "version", "publicado"}`

- [ ] **Step 1: Escribir los tests**

Agregar a `servidor/tests/test_api.py`, junto a los otros de instalación:

```python
def test_la_instalacion_informa_la_version_publicada(cliente, con_apk):
    """El responsable tiene que poder mirar el panel y saber si el cliente
    tiene la versión nueva o la vieja, sin desinstalar nada para comparar."""
    con_apk.with_name("app.apk.txt").write_text("2026-08-13 (build 42)", encoding="utf-8")

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["version"] == "2026-08-13 (build 42)"


def test_sin_el_archivo_de_version_igual_se_informa_cuando_se_publico(cliente, con_apk):
    """Alguien copió un APK a mano. La fecha sale del archivo, así que no
    puede desactualizarse, y responde la misma pregunta."""
    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["version"] == ""
    assert cuerpo["publicado"].endswith("Z")


def test_la_fecha_de_publicacion_es_la_del_archivo(cliente, con_apk):
    import os
    from datetime import datetime, timezone

    # Construida y no escrita a mano: un número de época puesto a ojo se
    # equivoca de día y el test pasa a probar la aritmética del que lo
    # escribió.
    momento = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    os.utime(con_apk, (momento, momento))

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["publicado"] == "2026-08-13T12:00:00Z"


def test_sin_apk_no_se_informa_ninguna_version(cliente, sin_apk):
    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["disponible"] is False
    assert cuerpo["version"] == ""
    assert cuerpo["publicado"] == ""


def test_una_version_con_saltos_de_linea_no_ensucia_el_panel(cliente, con_apk):
    """El archivo lo escribe la publicación, pero es un archivo del disco:
    el que llegue con un salto de línea de más no puede romper el renglón."""
    con_apk.with_name("app.apk.txt").write_text(
        "2026-08-13 (build 42)\n", encoding="utf-8"
    )

    assert cliente.get("/api/instalacion").json()["version"] == "2026-08-13 (build 42)"
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_api.py -q --rootdir .\servidor -k instalacion`
Expected: FAIL — `KeyError: 'version'`

- [ ] **Step 3: Agregar `desde_epoch` al reloj**

En `servidor/app/reloj.py`:

```python
def desde_epoch(segundos):
    """El mismo formato, para una fecha que ya existe: la de un archivo.

    Vive acá y no en quien la usa porque el formato de fecha del sistema
    tiene una sola fuente, y una fecha de archivo que saliera en otro
    formato se leería como si fuera de otro sistema.
    """
    return datetime.fromtimestamp(segundos, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Informar la versión y la fecha**

En `servidor/app/api/panel.py`, reemplazar `estado_de_instalacion` por:

```python
def _version_publicada():
    """Qué versión dice ser el APK que hay, o vacío si nadie lo dijo.

    Lo escribe la publicación, en el mismo movimiento en que copia el APK: la
    versión vive adentro del APK, en un formato binario que solo saben leer
    las herramientas del SDK de Android, y en la PC del cliente no están.

    La ruta se arma acá adentro y no como constante del módulo: los tests
    reemplazan `RUTA_APK` para apuntarlo a un archivo temporal, y una
    constante calculada al importar seguiría mirando la carpeta de verdad.
    """
    archivo = RUTA_APK.parent / "app.apk.txt"
    if not archivo.exists():
        return ""
    return archivo.read_text(encoding="utf-8").strip()


@router.get("/instalacion")
def estado_de_instalacion(request: Request):
    """Si hay APK para instalar, desde qué dirección se baja y cuál es.

    La fecha sale del archivo y no de un dato aparte: no la escribe nadie,
    así que no puede quedar desactualizada. La versión sí la escribe la
    publicación, y si falta se informa vacía en vez de inventarla.
    """
    if not RUTA_APK.exists():
        return {"disponible": False, "url": "", "version": "", "publicado": ""}

    return {
        "disponible": True,
        "url": _url_de_instalacion(request),
        "version": _version_publicada(),
        "publicado": reloj.desde_epoch(RUTA_APK.stat().st_mtime),
    }
```

Verificar que `reloj` ya esté importado en el archivo; si no, agregar
`from app import reloj`.

- [ ] **Step 5: Correr y verificar que pasan**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS, 5 tests nuevos sobre los 352

- [ ] **Step 6: Commit**

```bash
git add servidor/app/reloj.py servidor/app/api/panel.py servidor/tests/test_api.py
git commit -m "Informa que version de la app esta ofreciendo el panel

Al entregar una actualizacion hay que poder mirar el panel del cliente y
saber si tiene la vieja o la nueva. Sin esto, la unica forma de averiguarlo
es desinstalar la app de un celular y reinstalarla para comparar.

La fecha sale del archivo y no de un dato aparte: no la escribe nadie, asi
que no puede quedar desactualizada. La version la escribe la publicacion, y
si falta se informa vacia en vez de inventarla.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: El panel muestra la versión al lado del QR

**Files:**
- Modify: `servidor/panel/index.html`
- Modify: `servidor/panel/app.js`
- Test: `servidor/tests/test_panel_estatico.py`

**Interfaces:**
- Consumes: `GET /api/instalacion` con `version` y `publicado`

- [ ] **Step 1: Escribir el test**

Agregar a `servidor/tests/test_panel_estatico.py`:

```python
def test_la_version_del_apk_se_escribe_como_texto_y_no_como_marcado():
    """Sale de un archivo del disco, así que es dato como cualquier otro.

    Por `textContent` no interpreta HTML y no hace falta escaparlo; armado
    como marcado, un archivo con `<b>` adentro entraría al panel.
    """
    contenido = _cuerpo_de(
        (RUTA_PANEL / "app.js").read_text(encoding="utf-8"), "cargarInstalacion"
    )

    assert "version-apk" in contenido
    assert "textContent" in contenido
    assert "innerHTML" not in contenido
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_panel_estatico.py -q --rootdir .\servidor`
Expected: FAIL — `assert 'version-apk' in ...`

- [ ] **Step 3: Agregar el renglón al HTML**

En `servidor/panel/index.html`, adentro del bloque `#instalacion`, después del
párrafo con el enlace al APK:

```html
          <p class="ayuda" id="version-apk"></p>
```

- [ ] **Step 4: Completarlo desde el JavaScript**

En `servidor/panel/app.js`, reemplazar `cargarInstalacion` por:

```js
async function cargarInstalacion() {
  const estado = await pedir("/api/instalacion");
  $("#instalacion").classList.toggle("oculta", !estado.disponible);
  // El `src` va acá y no en el HTML. Un `src` fijo se descarga aunque el
  // bloque esté escondido, y el navegador no reintenta: si el APK se copia
  // con el panel abierto, el bloque se desesconde con el QR roto y hay que
  // apretar F5. Poniéndolo recién cuando hay APK, aparece siempre entero.
  if (estado.disponible) {
    $("#qr-instalacion").src = "/api/instalacion/qr";
    // Por textContent: la versión sale de un archivo del disco, y un
    // archivo es dato como cualquier otro.
    $("#version-apk").textContent = descripcionDeLaVersion(estado);
  }
}

/** Qué versión está ofreciendo el panel, en una línea legible. */
function descripcionDeLaVersion(estado) {
  // Mismo formato de fecha que el tablero: sin la T ni la Z, que no le dicen
  // nada a quien lo lee.
  const cuando = (estado.publicado || "").replace("T", " ").replace("Z", "");
  if (!estado.version) return `Publicada el ${cuando}`;
  return `Versión ${estado.version} · publicada el ${cuando}`;
}
```

- [ ] **Step 5: Correr la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS

- [ ] **Step 6: Verificarlo en el navegador**

Levantar el servidor, dejar un archivo cualquiera como `app.apk` en la raíz
del proyecto junto a un `app.apk.txt` que diga `2026-08-13 (build 42)`, abrir
el panel en la pestaña de Operarios y confirmar que aparecen el QR y el
renglón con la versión y la fecha. Después borrar los dos archivos de prueba.

```powershell
.\"Iniciar servidor.bat"
```

- [ ] **Step 7: Commit**

```bash
git add servidor/panel/index.html servidor/panel/app.js servidor/tests/test_panel_estatico.py
git commit -m "Muestra en el panel que version de la app se esta ofreciendo

El QR ya estaba; lo que faltaba era saber cual es el APK que se baja. Va por
textContent y no armando marcado: la version sale de un archivo del disco, y
un archivo es dato como cualquier otro.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: El APK se compila firmado y con un número que sube solo

**Files:**
- Modify: `celular/app/build.gradle.kts`
- Create: `celular/claves-de-ejemplo.properties`

**Interfaces:**
- Produces:
  - la tarea de Gradle `:app:publicar`, que deja `app.apk` y `app.apk.txt` en
    la raíz del proyecto
  - la variable de entorno `CONTROL_DE_STOCK_FIRMA`, opcional, con la ruta al
    archivo de contraseñas

- [ ] **Step 1: Crear la clave, una vez**

Este paso lo hace una persona y no se repite. Desde la raíz del proyecto:

```powershell
mkdir C:\clientes\claves -Force
& "C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot\bin\keytool.exe" -genkeypair -v `
  -keystore C:\clientes\claves\control-de-stock.jks `
  -alias control-de-stock -keyalg RSA -keysize 2048 -validity 10000
```

Pide una contraseña y algunos datos; el nombre puede ser `Control de Stock`.
Después, crear `C:\clientes\claves\control-de-stock.properties` con:

```properties
almacen=C:/clientes/claves/control-de-stock.jks
clave=LA_QUE_PUSISTE
alias=control-de-stock
claveDelAlias=LA_QUE_PUSISTE
```

**Respaldar esa carpeta.** Si se pierde, ningún celular con la app instalada
puede volver a actualizarse sin desinstalar, y desinstalar borra los conteos
que todavía no subieron.

- [ ] **Step 2: Dejar el ejemplo en el repositorio**

Crear `celular/claves-de-ejemplo.properties`, que sí se versiona porque no
tiene secretos, para que el formato quede documentado:

```properties
# Copiá este archivo a C:\clientes\claves\control-de-stock.properties
# —fuera del proyecto, porque esta carpeta se copia a la PC del cliente— y
# completá las contraseñas que pusiste al crear el almacén de claves.
#
# Si preferís otra ubicación, poné la ruta en la variable de entorno
# CONTROL_DE_STOCK_FIRMA.
almacen=C:/clientes/claves/control-de-stock.jks
clave=
alias=control-de-stock
claveDelAlias=
```

- [ ] **Step 3: Configurar la firma y el número de versión**

En `celular/app/build.gradle.kts`, arriba del bloque `android { }`:

```kotlin
import java.util.Properties

/**
 * La firma vive fuera del proyecto: esta carpeta se copia a la PC del
 * cliente, y la firma es lo único que impide que un tercero publique una
 * actualización que los celulares acepten como nuestra.
 */
val archivoDeFirma = File(
    System.getenv("CONTROL_DE_STOCK_FIRMA")
        ?: "C:/clientes/claves/control-de-stock.properties",
)

/**
 * Solo el release necesita la clave y el número de versión de verdad.
 *
 * Sin esta distinción, cualquier compilación de debug —o sea todas las de
 * todos los días— exigiría la clave y el historial de git.
 */
val esRelease = gradle.startParameter.taskNames.any { it.contains("elease") }

fun exigirLaFirma(): Properties {
    if (!archivoDeFirma.exists()) {
        throw GradleException(
            "Falta el archivo con la clave para firmar la app:\n" +
                "  ${archivoDeFirma.absolutePath}\n\n" +
                "Copiá celular/claves-de-ejemplo.properties a esa ruta y completá " +
                "las contraseñas, o poné otra ruta en la variable de entorno " +
                "CONTROL_DE_STOCK_FIRMA.\n\n" +
                "Sin firma, Android no instala la app.",
        )
    }
    return Properties().apply { archivoDeFirma.inputStream().use { load(it) } }
}

/**
 * El número de versión sale de cuántos commits lleva el repositorio.
 *
 * Sube solo, así que no hay forma de olvidarse ni de publicar dos veces el
 * mismo número — y Android rechaza una actualización cuyo número no sea
 * mayor que el instalado, con un error que no explica nada.
 */
fun contarCommits(): Int {
    val proceso = ProcessBuilder("git", "rev-list", "--count", "HEAD")
        .directory(rootDir)
        .redirectErrorStream(true)
        .start()
    val salida = proceso.inputStream.bufferedReader().readText().trim()
    val numero = salida.toIntOrNull()

    if (proceso.waitFor() != 0 || numero == null) {
        throw GradleException(
            "No se pudo averiguar el número de versión con git:\n  $salida\n\n" +
                "La app se publica desde una copia del repositorio, con git " +
                "disponible. Un número inventado produce un APK que no se " +
                "instala encima del anterior, y eso se descubre recién en el " +
                "celular del operario.",
        )
    }
    return numero
}

val versionPublicada: String by lazy {
    java.time.LocalDate.now().toString()
}
```

Dentro de `android { }`, reemplazar el `versionCode`/`versionName` de
`defaultConfig` por:

```kotlin
        // En debug queda el 1 de siempre: el número solo importa al publicar,
        // y pedirle git a cada compilación del día a día es un estorbo.
        versionCode = if (esRelease) contarCommits() else 1
        versionName = if (esRelease) versionPublicada else "desarrollo"
```

Y agregar, después de `defaultConfig`:

```kotlin
    signingConfigs {
        create("publicacion") {
            if (esRelease) {
                val claves = exigirLaFirma()
                storeFile = File(claves.getProperty("almacen"))
                storePassword = claves.getProperty("clave")
                keyAlias = claves.getProperty("alias")
                keyPassword = claves.getProperty("claveDelAlias")
            }
        }
    }

    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.getByName("publicacion")
        }
    }
```

- [ ] **Step 4: Agregar la tarea que publica**

Al final de `celular/app/build.gradle.kts`, fuera de `android { }`:

```kotlin
/**
 * Deja el APK donde el panel lo busca, con su versión al lado.
 *
 * El panel sirve `<raíz>/app.apk`, y la versión va en un archivo aparte
 * porque adentro del APK está en un formato binario que solo saben leer las
 * herramientas del SDK, que en la PC del cliente no están. Los dos los
 * escribe esta tarea, en el mismo movimiento, así no pueden separarse.
 */
tasks.register("publicar") {
    dependsOn("assembleRelease")

    doLast {
        val compilado = layout.buildDirectory
            .file("outputs/apk/release/app-release.apk").get().asFile
        val destino = File(rootDir.parentFile, "app.apk")
        val version = "$versionPublicada (build ${contarCommits()})"

        compilado.copyTo(destino, overwrite = true)
        File(rootDir.parentFile, "app.apk.txt").writeText(version, Charsets.UTF_8)

        println("")
        println("Publicada la version $version")
        println("Queda en ${destino.absolutePath}")
        println("El panel ya la ofrece en la pestania de Operarios.")
    }
}
```

- [ ] **Step 5: Verificar que falla sin la clave**

Con la variable apuntando a un archivo que no existe:

```powershell
cd "C:\clientes\Control de Stock\celular"
$env:CONTROL_DE_STOCK_FIRMA = "C:\no\existe.properties"
C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleRelease --no-daemon
```

Expected: FALLA con el mensaje que dice qué falta y cómo crearlo. **No tiene
que producir ningún APK.**

Después, `Remove-Item Env:\CONTROL_DE_STOCK_FIRMA` para seguir.

- [ ] **Step 6: Verificar que el debug sigue andando sin la clave**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon`
Expected: BUILD SUCCESSFUL. Es el que se usa todos los días: si exigiera la
clave, cada prueba por USB dependería de ella.

- [ ] **Step 7: Publicar y verificar la firma**

```powershell
cd "C:\clientes\Control de Stock\celular"
C:\Gradle\gradle-8.7\bin\gradle.bat :app:publicar --no-daemon
```

Expected: imprime la versión, y en la raíz del proyecto quedan `app.apk` y
`app.apk.txt`.

Confirmar que quedó firmado de verdad:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\build-tools\34.0.0\apksigner.bat" verify --print-certs "C:\clientes\Control de Stock\app.apk"
```

Expected: informa el certificado, y **no** dice que no está firmado.

- [ ] **Step 8: Correr las dos suites**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: las dos PASS. Este cambio no toca código de la app ni del servidor,
así que los totales tienen que quedar iguales.

- [ ] **Step 9: Commit**

```bash
git add celular/app/build.gradle.kts celular/claves-de-ejemplo.properties
git commit -m "Compila la app firmada y con un numero de version que sube solo

Sin firma Android no instala nada, y con una firma distinta a la instalada
tampoco: la unica salida seria desinstalar, que borra los conteos que el
operario todavia no subio.

La clave se lee de una carpeta fuera del proyecto, porque esta carpeta se
copia a la PC del cliente y la firma es lo unico que impide que un tercero
publique una actualizacion que los celulares acepten como nuestra. Si falta,
la compilacion de release falla diciendo que falta: sin eso saldria un APK
sin firmar, que se descubre recien en el celular del operario.

El numero sale de cuantos commits lleva el repositorio, asi que sube solo.
El debug sigue sin necesitar ni la clave ni git, que es lo que se compila
todos los dias.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Publicar de un doble clic, y probarlo en el celular

**Files:**
- Create: `Publicar app.bat`

**Interfaces:**
- Consumes: la tarea `:app:publicar` de la Task 3

- [ ] **Step 1: Escribir el `.bat`**

Crear `Publicar app.bat` en la raíz del proyecto, con el mismo molde que
`Iniciar servidor.bat`:

```bat
@echo off
chcp 65001 > nul
cd /d "%~dp0celular"

set GRADLE=C:\Gradle\gradle-8.7\bin\gradle.bat

if not exist "%GRADLE%" (
    echo.
    echo No se encontro Gradle en %GRADLE%
    echo.
    echo La app se compila en la maquina de desarrollo, no en la del cliente.
    echo.
    pause
    exit /b 1
)

echo Compilando la app firmada. La primera vez tarda unos minutos...
echo.

call "%GRADLE%" :app:publicar --no-daemon

if errorlevel 1 (
    echo.
    echo No se pudo publicar. El motivo esta unas lineas mas arriba.
    echo.
    pause
    exit /b 1
)

echo.
pause
```

- [ ] **Step 2: Probarlo tal como se usa**

Borrar el `app.apk` y el `app.apk.txt` que dejó la Task 3, y hacer doble clic
en `Publicar app.bat` desde el Explorador —no desde una terminal, que es como
se va a usar—.

Expected: compila, imprime la versión publicada, y los dos archivos vuelven a
aparecer en la raíz.

- [ ] **Step 3: El panel lo ofrece**

Levantar el servidor con `Iniciar servidor.bat`, abrir el panel, ir a
**Operarios**. Tienen que verse el QR de instalación y el renglón con la
versión y la fecha.

**Y el QR de vinculación de cada operario tiene que seguir en su fila**: son
dos cosas distintas y las dos conviven.

- [ ] **Step 4: Instalar en el celular desde el QR, sin cable**

Es la prueba que justifica todo el plan.

1. Desinstalar la app del celular: `adb uninstall com.controldestock`.
2. Con el celular en la misma WiFi, escanear el **QR de instalación** con la
   cámara del celular. Android va a pedir permiso para instalar desde esa
   fuente la primera vez.
3. Abrir la app y vincularla escaneando el QR de un operario.
4. Cortar la WiFi (`adb shell svc wifi disable`) y contar dos artículos, para
   que queden sin subir.

- [ ] **Step 5: Actualizar encima, que es lo que la firma protege**

1. Hacer un commit cualquiera en el repositorio, para que el número de
   versión suba.
2. Doble clic en `Publicar app.bat`.
3. Confirmar que el panel muestra la versión nueva.
4. Escanear otra vez el QR de instalación desde el celular e instalar
   **encima**, sin desinstalar.
5. Abrir la app: tiene que arrancar sin cerrarse y **los dos conteos sin
   subir tienen que seguir ahí**.

Verificarlo también en la base del celular:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb exec-out run-as com.controldestock cat databases/control-de-stock.db > celular.db
.\servidor\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('celular.db'); print([r for r in c.execute('select codigo,cantidad,estadoSync from conteo')])"
```

Si este paso falla, la firma o el número de versión están mal, y no sirve de
nada seguir: es exactamente lo que el plan viene a resolver.

- [ ] **Step 6: Commit**

```bash
git add "Publicar app.bat"
git commit -m "Publica la app con un doble clic

Al lado de Iniciar servidor.bat y con la misma idea: lo que hay que hacer
seguido no puede depender de acordarse de un comando ni de estar parado en la
carpeta correcta.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Verificación final del plan

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
```

Las dos en verde, y sobre todo: **un celular que se suma al inventario
escaneando el QR del panel, y una actualización que se instala encima sin que
el operario pierda lo que no subió.**

Antes de entregar, agregar a `docs/superpowers/deuda-conocida.md` que el
respaldo de `C:\clientes\claves\` es parte de la entrega, y quién lo guarda.

**Lo que queda para después**, ya en la deuda conocida: que la app avise sola
cuando hay una versión nueva, en vez de que alguien tenga que ir a escanear
el QR otra vez.
