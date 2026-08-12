# App Android — escanear y contar — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Goal:** Que un operario escanee un código de barras con el celular, cargue la cantidad, y el conteo aparezca en el tablero del panel.

**Architecture:** Pantallas en Compose sobre las fundaciones ya construidas (`nucleo/` con la lógica, `app/` con la base local y el cliente HTTP). La cámara es CameraX con el lector de códigos de ML Kit, con el modelo incluido en el APK porque en el depósito no hay internet. La navegación es un `when` sobre un estado, sin librería: son pocas pantallas y una dependencia menos es una cosa menos que puede fallar. La sincronización corre en segundo plano con WorkManager.

**Tech Stack:** Kotlin 1.9.23, Compose BOM 2024.05.00, CameraX 1.3.3, ML Kit barcode-scanning 17.2.0, WorkManager 2.9.0, Room 2.6.1, OkHttp 4.12.0.

Este plan corresponde a la sección 6 del spec `docs/superpowers/specs/2026-08-11-app-android-base-design.md`, salvo alta rápida, «Mis conteos» y «Buscar», que van en el plan siguiente.

## Global Constraints

- **Cantidades en milésimas, siempre enteras** (`Int`). Nunca `Float` ni `Double`.
- **La app nunca consulta al servidor para trabajar.** La base local es la fuente de verdad: con o sin señal se comporta igual. La pantalla confirma contra la base local, nunca contra la red.
- **`nucleo/` no importa nada de `android.*`.** Hay un test que lo verifica.
- **Nada se edita ni se borra:** una corrección es un evento de anulación.
- **Fechas ISO 8601 UTC**; la única fuente es `RelojDelSistema`.
- **Textos en castellano rioplatense**, sin jerga técnica. Los errores dicen qué hacer.
- **Una sola acción principal por pantalla**, controles en la mitad inferior, objetivos táctiles de 48 dp como mínimo y bastante más en el teclado numérico.
- **Feedback por tres vías a la vez** —sonido, vibración y color— con timbres distintos para *leído*, *desconocido* y *error*. En un depósito ruidoso no se escucha; con el celular en movimiento no se ve.
- **El estado de sincronización nunca interrumpe.** Es un indicador discreto; jamás bloquea el escaneo ni abre diálogos.
- minSdk 26, targetSdk 34.
- Los mensajes de commit van en castellano, en presente, describiendo el efecto.

## Entorno

Desde `celular/`, con `--no-daemon`. **Definí `JAVA_HOME` en la sesión antes de correr Gradle**, no está en el entorno del shell:

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon
```

El celular de prueba es un Motorola moto g(6) plus con Android 9 (API 28), conectado por USB y autorizado. `adb` está en `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`.

El intérprete de Python es `servidor\.venv\Scripts\python.exe` **por ruta**: el `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta nada.

## Lo que ya existe y se consume

En `nucleo/` (paquete `com.controldestock.nucleo`):

- `Cantidades.aMilesimas(texto): Int` / `Cantidades.aTexto(milesimas): String`
- `Reloj`, `RelojDelSistema(clock)` y `RelojDelSistema.DEL_SISTEMA`
- `EventoConteo` con `nuevo(...)` y `anulacionDe(...)`
- `ReglasDeCarga.validar(texto, admiteDecimales): ResultadoDeCarga` — `Valida`, `PideConfirmacion`, `Invalida`
- `EstadoSync`, `ConteoLocal`, `PlanDeSincronizacion.aEnviar/aplicar/pendientes/anulacionesSinDestino`
- Tipos del contrato y `jsonDelContrato`

En `app/`:

- `BaseLocal` con `vinculacionDao()`, `maestroDao()`, `conteoDao()` y `vincularA(vinculacion)`
- Entidades `VinculacionEntidad`, `ArticuloEntidad`, `CodigoEntidad`, `UnidadEntidad`, `ConteoEntidad`, más `textoDeBusqueda(...)` y `plegar(...)`
- `ClienteServidor(url, token)` con `vincular()`, `maestro()`, `enviarConteos(...)`, `altaRapida(...)` y `ErrorDeServidor(mensaje, reintentable)`

---

### Task 1: Andamiaje de la interfaz

**Files:**
- Modify: `celular/app/build.gradle.kts`
- Modify: `celular/app/src/main/AndroidManifest.xml`
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/Tema.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`

**Interfaces:**
- Consumes: `BaseLocal` (fundaciones)
- Produces:
  - `Pantalla` — sealed class: `Cargando`, `Vinculando`, `Escaneando`
  - `pantallaSegun(vinculacion: VinculacionEntidad?): Pantalla` — a qué pantalla corresponde ir
  - `MainActivity` — la única Activity, con el `LAUNCHER`
  - `Tema` — colores y tipografía, con los mismos estados que el panel

**Por qué la navegación es un `when` y no una librería:** son tres pantallas y el estado que decide entre ellas es una sola pregunta —si el celular está vinculado—. Una librería de navegación agrega una dependencia, un grafo y un ciclo de vida propio para resolver un `if`.

- [ ] **Step 1: Agregar las dependencias de Compose**

En `celular/app/build.gradle.kts`, dentro de `android { }`, agregar:

```kotlin
    buildFeatures {
        compose = true
    }

    composeOptions {
        // Atada a Kotlin 1.9.23: una combinación distinta no compila.
        kotlinCompilerExtensionVersion = "1.5.11"
    }
```

Y al bloque `dependencies`:

```kotlin
    implementation(platform("androidx.compose:compose-bom:2024.05.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.0")
```

- [ ] **Step 2: Verificar que compila antes de escribir código**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon`
Expected: `BUILD SUCCESSFUL`

Si falla la resolución de una dependencia o la versión del compilador de Compose, **parar y reportarlo** con la salida completa. Adivinar versiones rompe la reproducibilidad.

- [ ] **Step 3: Escribir el test que falla**

Crear `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`:

```kotlin
package com.controldestock.ui

import com.controldestock.datos.VinculacionEntidad
import org.junit.Assert.assertEquals
import org.junit.Test

class PantallaTest {

    private val vinculacion = VinculacionEntidad(
        url = "http://172.16.11.12:8000", token = "abc",
        operarioId = 1, operarioNombre = "Juan",
        sesionId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
    )

    @Test
    fun `sin vincular va a la pantalla de vinculacion`() {
        assertEquals(Pantalla.Vinculando, pantallaSegun(null))
    }

    @Test
    fun `vinculado va derecho a escanear`() {
        // El operario abre la app para contar, no para ver un menú: la cámara
        // tiene que estar lista sin tocar nada.
        assertEquals(Pantalla.Escaneando, pantallaSegun(vinculacion))
    }
}
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: FAIL con `Unresolved reference: Pantalla`

- [ ] **Step 5: Implementar `Pantalla.kt`**

```kotlin
package com.controldestock.ui

import com.controldestock.datos.VinculacionEntidad

/**
 * En qué pantalla está la app.
 *
 * Son tres y la decisión entre ellas es una sola pregunta —si el celular
 * está vinculado—, así que la navegación es un `when` y no una librería con
 * su propio grafo y su propio ciclo de vida.
 */
sealed class Pantalla {
    /** Todavía no se leyó la base local. */
    object Cargando : Pantalla()

    /** Falta escanear el QR del panel. */
    object Vinculando : Pantalla()

    /** La cámara, lista para contar. */
    object Escaneando : Pantalla()
}

/**
 * El operario abre la app para contar, no para ver un menú: si ya está
 * vinculado, la cámara arranca sin que tenga que tocar nada.
 */
fun pantallaSegun(vinculacion: VinculacionEntidad?): Pantalla =
    if (vinculacion == null) Pantalla.Vinculando else Pantalla.Escaneando
```

- [ ] **Step 6: Implementar `Tema.kt`**

Los estados usan los mismos colores que el panel, para que un color signifique lo mismo en las dos interfaces.

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Los mismos que panel/estilos.css: un color significa lo mismo en las dos
// interfaces, que es lo que pide el diseño general.
val Acento = Color(0xFF1F5FA9)
val Verde = Color(0xFF1B7A3D)
val Rojo = Color(0xFFB3261E)
val Ambar = Color(0xFF9A5B12)

private val Claro = lightColorScheme(
    primary = Acento,
    error = Rojo,
)

private val Oscuro = darkColorScheme(
    primary = Color(0xFF7FB0E6),
    error = Color(0xFFE08B84),
)

@Composable
fun Tema(contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) Oscuro else Claro,
        content = contenido,
    )
}
```

- [ ] **Step 7: Implementar `MainActivity.kt`**

```kotlin
package com.controldestock

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.controldestock.datos.BaseLocal
import com.controldestock.ui.Pantalla
import com.controldestock.ui.Tema
import com.controldestock.ui.pantallaSegun

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val base = BaseLocal.de(this)

        setContent {
            Tema {
                Surface(modifier = Modifier.fillMaxSize()) {
                    App(base)
                }
            }
        }
    }
}

@Composable
private fun App(base: BaseLocal) {
    var pantalla by remember { mutableStateOf<Pantalla>(Pantalla.Cargando) }

    LaunchedEffect(Unit) {
        pantalla = pantallaSegun(base.vinculacionDao().actual())
    }

    when (pantalla) {
        Pantalla.Cargando -> Aviso("Un momento…")
        Pantalla.Vinculando -> Aviso("Escaneá el QR del panel para vincular este celular.")
        Pantalla.Escaneando -> Aviso("Listo para contar.")
    }
}

@Composable
private fun Aviso(texto: String) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(texto, style = androidx.compose.material3.MaterialTheme.typography.headlineSmall)
    }
}
```

Las tres pantallas son textos por ahora: las tareas siguientes las reemplazan una por una. Lo que esta tarea entrega es una app que **arranca y decide bien a dónde ir**.

- [ ] **Step 8: Declarar la Activity en el manifiesto**

En `celular/app/src/main/AndroidManifest.xml`, dentro de `<application>` (que hoy es una etiqueta que se cierra sola, así que hay que abrirla):

```xml
    <application
        android:label="Control de Stock"
        android:supportsRtl="false"
        android:allowBackup="false"
        android:networkSecurityConfig="@xml/red">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

    </application>
```

`screenOrientation="portrait"`: el operario cuenta con una mano, y una rotación en el medio del escaneo reinicia la cámara.

- [ ] **Step 9: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, los 33 previos más los 2 nuevos

- [ ] **Step 10: Instalar en el celular y ver que abre**

```powershell
cd celular
C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb install -r app\build\outputs\apk\debug\app-debug.apk
& $adb shell am start -n com.controldestock/.MainActivity
```

Verificar en la pantalla del celular que dice «Escaneá el QR del panel para vincular este celular.». Es la primera vez que la app existe como algo que se abre.

Si `adb devices` no muestra el celular como `device`, **parar y reportarlo**: sin dispositivo no se puede verificar nada de lo que sigue.

- [ ] **Step 11: Commit**

```bash
git add celular/
git commit -m "Agrega la pantalla inicial de la app

La app ya se puede abrir. Decide sola a donde ir: si el celular todavia no
esta vinculado pide el QR, y si ya lo esta va derecho a contar, porque el
operario abre la app para contar y no para ver un menu.

La navegacion es un when sobre el estado y no una libreria: son tres
pantallas y la decision entre ellas es una sola pregunta.

Queda fija en vertical: el operario cuenta con una mano y una rotacion en
medio del escaneo reinicia la camara."
```

---

### Task 2: Vinculación escaneando el QR

**Files:**
- Modify: `celular/app/build.gradle.kts`
- Modify: `celular/app/src/main/AndroidManifest.xml`
- Create: `celular/app/src/main/kotlin/com/controldestock/nucleo/DatosDelQr.kt` *(en `nucleo/`, ver abajo)*
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/DatosDelQrTest.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/camara/Escaner.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaVinculacion.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/Vinculador.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/VinculadorTest.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Aclaración sobre la primera ruta:** `DatosDelQr` va en **`celular/nucleo/src/main/kotlin/com/controldestock/nucleo/DatosDelQr.kt`**, no en `app/`. Es parseo puro y se prueba sin celular.

**Interfaces:**
- Consumes: `ClienteServidor`, `BaseLocal.vincularA`, `jsonDelContrato`
- Produces:
  - `DatosDelQr(url: String, token: String)` y `leerQr(texto: String): DatosDelQr?`
  - `Escaner` — envuelve CameraX + ML Kit; `@Composable fun VistaDeCamara(alLeer: (String) -> Unit, activo: Boolean)`
  - `Vinculador(base, crearCliente)` con `suspend fun vincular(datos: DatosDelQr): ResultadoDeVinculacion`
  - `ResultadoDeVinculacion` — `Vinculado(nombre, sesion)` o `Fallo(mensaje)`

- [ ] **Step 1: Agregar cámara y lector de códigos**

En `celular/app/build.gradle.kts`, al bloque `dependencies`:

```kotlin
    implementation("androidx.camera:camera-core:1.3.3")
    implementation("androidx.camera:camera-camera2:1.3.3")
    implementation("androidx.camera:camera-lifecycle:1.3.3")
    implementation("androidx.camera:camera-view:1.3.3")
    // La variante con el modelo adentro del APK. La otra lo descarga de Play
    // Services la primera vez, y en el depósito no hay internet.
    implementation("com.google.mlkit:barcode-scanning:17.2.0")
```

En `celular/app/src/main/AndroidManifest.xml`, arriba de `<application>`:

```xml
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-feature android:name="android.hardware.camera.any" android:required="true" />
```

- [ ] **Step 2: Verificar que compila**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon`
Expected: `BUILD SUCCESSFUL`. ML Kit agrega varios MB al APK; es esperado.

- [ ] **Step 3: Escribir el test del parseo del QR**

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/DatosDelQrTest.kt`:

```kotlin
package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DatosDelQrTest {

    @Test
    fun `lee el QR que genera el panel`() {
        val texto = """{"u":"http://172.16.11.12:8000","t":"abc123"}"""

        val datos = leerQr(texto)

        assertEquals("http://172.16.11.12:8000", datos?.url)
        assertEquals("abc123", datos?.token)
    }

    @Test
    fun `un QR de otra cosa no vincula nada`() {
        // El operario puede apuntar sin querer a la etiqueta de un producto,
        // o a un QR de wifi. Tiene que decirlo, no romperse.
        assertNull(leerQr("https://www.google.com"))
        assertNull(leerQr("7790001001234"))
        assertNull(leerQr(""))
    }

    @Test
    fun `un JSON sin los campos que hacen falta no vincula`() {
        assertNull(leerQr("""{"u":"http://a"}"""))
        assertNull(leerQr("""{"t":"abc"}"""))
        assertNull(leerQr("""{"u":"","t":"abc"}"""))
        assertNull(leerQr("""{"u":"http://a","t":""}"""))
    }

    @Test
    fun `un JSON con campos de mas igual se lee`() {
        // El panel puede agregar un campo sin coordinar una versión de la app.
        val texto = """{"u":"http://a:8000","t":"abc","v":2}"""

        assertEquals("abc", leerQr(texto)?.token)
    }
}
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: leerQr`

- [ ] **Step 5: Implementar `DatosDelQr.kt` en `nucleo/`**

Crear `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/DatosDelQr.kt`:

```kotlin
package com.controldestock.nucleo

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Lo que el panel mete adentro del QR de vinculación. */
@Serializable
data class DatosDelQr(
    @SerialName("u") val url: String,
    @SerialName("t") val token: String,
)

/**
 * Lee el QR del panel, o devuelve null si es cualquier otra cosa.
 *
 * La cámara está siempre activa, así que va a leer etiquetas de productos,
 * QR de wifi y lo que haya en la pared. Nada de eso puede vincular ni
 * romper la app: solo se acepta lo que tiene las dos cosas que hacen falta.
 */
fun leerQr(texto: String): DatosDelQr? = try {
    jsonDelContrato.decodeFromString<DatosDelQr>(texto)
        .takeIf { it.url.isNotBlank() && it.token.isNotBlank() }
} catch (error: Exception) {
    null
}
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 4 tests nuevos

- [ ] **Step 7: Escribir el test del vinculador**

Crear `celular/app/src/test/kotlin/com/controldestock/VinculadorTest.kt`:

```kotlin
package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.BaseLocal
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor
import java.io.File
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class VinculadorTest {

    private lateinit var base: BaseLocal
    private lateinit var servidor: MockWebServer

    @Before
    fun preparar() {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
        servidor = MockWebServer()
        servidor.start()
    }

    @After
    fun terminar() {
        base.close()
        servidor.shutdown()
    }

    private fun contrato(nombre: String) = File("../contrato/$nombre.json").readText()

    private fun responder(cuerpo: String, codigo: Int = 200) {
        servidor.enqueue(
            MockResponse().setResponseCode(codigo)
                .setHeader("Content-Type", "application/json").setBody(cuerpo),
        )
    }

    private fun vinculador() = Vinculador(base) { url, token -> ClienteServidor(url, token) }

    private fun datos() = DatosDelQr(servidor.url("/").toString().trimEnd('/'), "token")

    @Test
    fun `vincular guarda la sesion y descarga el maestro`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        val resultado = vinculador().vincular(datos())

        assertTrue(resultado is ResultadoDeVinculacion.Vinculado)
        assertEquals("Contrato", (resultado as ResultadoDeVinculacion.Vinculado).operario)
        assertNotNull(base.vinculacionDao().actual())
        assertEquals(2, base.maestroDao().articulos().size)
    }

    @Test
    fun `el maestro descargado se puede buscar por codigo`() = runTest {
        // Es lo único que importa del maestro para contar: que el escaneo
        // encuentre el artículo, sin señal.
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertNotNull(base.maestroDao().porCodigo("7790001001234"))
    }

    @Test
    fun `el maestro descargado guarda el texto de busqueda`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertTrue(base.maestroDao().buscar("fideos").isNotEmpty())
    }

    @Test
    fun `las unidades quedan guardadas para saber si admiten decimales`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertEquals(1, base.maestroDao().unidad("KG")?.admiteDecimales)
    }

    @Test
    fun `si el servidor no contesta no queda vinculado a medias`() = runTest {
        // Quedar vinculado sin maestro es peor que no vincular: la app abre
        // la cámara y rechaza todo lo que se escanee.
        servidor.shutdown()

        val resultado = vinculador().vincular(datos())

        assertTrue(resultado is ResultadoDeVinculacion.Fallo)
        assertNull(base.vinculacionDao().actual())
    }

    @Test
    fun `si falla la descarga del maestro tampoco queda vinculado`() = runTest {
        responder(contrato("vinculacion"))
        responder("""{"detail":"algo"}""", 500)

        val resultado = vinculador().vincular(datos())

        assertTrue(resultado is ResultadoDeVinculacion.Fallo)
        assertNull(base.vinculacionDao().actual())
    }

    @Test
    fun `un token invalido lo explica en castellano`() = runTest {
        responder("""{"detail":"Token de operario inválido"}""", 401)

        val resultado = vinculador().vincular(datos())

        val mensaje = (resultado as ResultadoDeVinculacion.Fallo).mensaje
        assertTrue(mensaje.contains("QR") || mensaje.contains("vinculado"))
    }
}
```

- [ ] **Step 8: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: FAIL con `Unresolved reference: Vinculador`

- [ ] **Step 9: Implementar `Vinculador.kt`**

```kotlin
package com.controldestock

import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor

sealed class ResultadoDeVinculacion {
    data class Vinculado(val operario: String, val sesion: String) : ResultadoDeVinculacion()
    data class Fallo(val mensaje: String) : ResultadoDeVinculacion()
}

/**
 * Vincula el celular y le deja el maestro listo para contar sin señal.
 *
 * Las dos cosas van juntas a propósito: un celular vinculado sin maestro
 * abre la cámara y rechaza todo lo que se escanee, que es peor que no estar
 * vinculado, porque parece que funciona.
 */
class Vinculador(
    private val base: BaseLocal,
    private val crearCliente: (String, String) -> ClienteServidor,
) {

    suspend fun vincular(datos: DatosDelQr): ResultadoDeVinculacion {
        val cliente = crearCliente(datos.url, datos.token)

        return try {
            val quien = cliente.vincular()
            val maestro = cliente.maestro()

            base.vincularA(
                VinculacionEntidad(
                    url = datos.url,
                    token = datos.token,
                    operarioId = quien.operario.id,
                    operarioNombre = quien.operario.nombre,
                    sesionId = quien.sesion.id,
                    pasadaId = quien.pasada.id,
                    pasadaNumero = quien.pasada.numero,
                    pasadaEtiqueta = quien.pasada.etiqueta,
                ),
            )

            base.maestroDao().reemplazarMaestro(
                articulos = maestro.articulos.map {
                    ArticuloEntidad(
                        id = it.id, idOrden = it.idOrden, tipo = it.tipo,
                        material = it.material, sku = it.sku,
                        descripcion = it.descripcion, grupo = it.grupo,
                        ubicacion = it.ubicacion, unidad = it.unidad,
                        pasadaNumero = quien.pasada.numero,
                        sesionId = quien.sesion.id,
                        busqueda = textoDeBusqueda(it.descripcion, it.sku, it.ubicacion),
                    )
                },
                codigos = maestro.codigos.map { CodigoEntidad(it.codigo, it.articuloId) },
                unidades = maestro.unidades.map {
                    UnidadEntidad(it.codigo, it.nombre, it.admiteDecimales)
                },
            )

            ResultadoDeVinculacion.Vinculado(quien.operario.nombre, quien.sesion.nombre)
        } catch (error: ErrorDeServidor) {
            ResultadoDeVinculacion.Fallo(error.message.orEmpty())
        }
    }
}
```

**Ojo con el orden:** `vincularA` se llama antes de guardar el maestro, y las dos llamadas al servidor van antes que cualquier escritura. Si el servidor no contesta, no se escribió nada y el celular sigue sin vincular, que es lo que fija el test.

- [ ] **Step 10: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, 7 tests nuevos

- [ ] **Step 11: Implementar `Escaner.kt`**

```kotlin
package com.controldestock.camara

import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors

/**
 * La cámara, siempre activa, leyendo códigos.
 *
 * El operario apunta y lee: no hay botón de disparo. Cuando `activo` es
 * falso la cámara sigue prendida pero no avisa lecturas — es lo que pausa
 * el escaneo mientras hay una ficha abierta, sin el parpadeo de reiniciar
 * la cámara.
 */
@Composable
fun VistaDeCamara(
    activo: Boolean,
    alLeer: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val contexto = LocalContext.current
    val duenio = LocalLifecycleOwner.current
    val hilo = remember { Executors.newSingleThreadExecutor() }
    val lector = remember { BarcodeScanning.getClient() }
    val estaActivo = rememberUpdatedState(activo)
    val avisar = rememberUpdatedState(alLeer)

    DisposableEffect(Unit) {
        onDispose {
            hilo.shutdown()
            lector.close()
        }
    }

    AndroidView(
        modifier = modifier,
        factory = { ctx ->
            val vista = PreviewView(ctx)
            val futuro = ProcessCameraProvider.getInstance(ctx)

            futuro.addListener({
                val proveedor = futuro.get()

                val vistaPrevia = Preview.Builder().build().also {
                    it.setSurfaceProvider(vista.surfaceProvider)
                }

                val analisis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()

                analisis.setAnalyzer(hilo) { imagen ->
                    procesar(imagen, lector, estaActivo.value) { codigo ->
                        avisar.value(codigo)
                    }
                }

                proveedor.unbindAll()
                proveedor.bindToLifecycle(
                    duenio, CameraSelector.DEFAULT_BACK_CAMERA, vistaPrevia, analisis,
                )
            }, androidx.core.content.ContextCompat.getMainExecutor(ctx))

            vista
        },
    )
}

@androidx.camera.core.ExperimentalGetImage
private fun procesar(
    imagen: ImageProxy,
    lector: com.google.mlkit.vision.barcode.BarcodeScanner,
    activo: Boolean,
    alLeer: (String) -> Unit,
) {
    val cruda = imagen.image
    if (cruda == null || !activo) {
        imagen.close()
        return
    }

    val entrada = InputImage.fromMediaImage(cruda, imagen.imageInfo.rotationDegrees)
    lector.process(entrada)
        .addOnSuccessListener { codigos ->
            codigos.firstOrNull { it.rawValue != null }?.let { alLeer(it.rawValue!!) }
        }
        .addOnCompleteListener { imagen.close() }
}
```

Agregar `implementation("androidx.core:core-ktx:1.13.1")` a `dependencies` si `ContextCompat` no resuelve.

- [ ] **Step 12: Implementar `PantallaVinculacion.kt`**

```kotlin
package com.controldestock.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.compose.ui.platform.LocalContext
import com.controldestock.camara.VistaDeCamara
import com.controldestock.nucleo.leerQr

/**
 * La primera pantalla: escanear el QR del panel.
 *
 * Solo se ve una vez por celular. Si el QR no es el del panel lo dice y
 * sigue escaneando, en vez de trabarse: el operario va a apuntar sin querer
 * a media docena de cosas antes de dar con el código.
 */
@Composable
fun PantallaVinculacion(
    vinculando: Boolean,
    error: String?,
    alLeerQr: (String, String) -> Unit,
) {
    val contexto = LocalContext.current
    var hayPermiso by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(contexto, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED,
        )
    }
    var avisoDeQr by remember { mutableStateOf<String?>(null) }

    val pedirPermiso = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { concedido -> hayPermiso = concedido }

    LaunchedEffect(hayPermiso) {
        if (!hayPermiso) pedirPermiso.launch(Manifest.permission.CAMERA)
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            "Escaneá el QR de tu nombre en el panel",
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )

        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            when {
                vinculando -> Centrado { CircularProgressIndicator() }
                hayPermiso -> VistaDeCamara(
                    activo = true,
                    modifier = Modifier.fillMaxSize(),
                    alLeer = { texto ->
                        val datos = leerQr(texto)
                        if (datos == null) {
                            avisoDeQr = "Ese código no es el del panel. Buscá el QR " +
                                "que está al lado de tu nombre, en Operarios."
                        } else {
                            avisoDeQr = null
                            alLeerQr(datos.url, datos.token)
                        }
                    },
                )
                else -> Centrado {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "La app necesita la cámara para escanear.",
                            textAlign = TextAlign.Center,
                        )
                        Button(onClick = { pedirPermiso.launch(Manifest.permission.CAMERA) }) {
                            Text("Permitir")
                        }
                    }
                }
            }
        }

        (error ?: avisoDeQr)?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun Centrado(contenido: @Composable () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        contenido()
    }
}
```

- [ ] **Step 13: Conectar la pantalla en `MainActivity`**

Reemplazar la función `App` de `MainActivity.kt` por esta:

```kotlin
@Composable
private fun App(base: BaseLocal) {
    val alcance = rememberCoroutineScope()
    var pantalla by remember { mutableStateOf<Pantalla>(Pantalla.Cargando) }
    var vinculando by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        pantalla = pantallaSegun(base.vinculacionDao().actual())
    }

    when (pantalla) {
        Pantalla.Cargando -> Aviso("Un momento…")

        Pantalla.Vinculando -> PantallaVinculacion(
            vinculando = vinculando,
            error = error,
        ) { url, token ->
            if (!vinculando) {
                vinculando = true
                error = null
                alcance.launch {
                    val vinculador = Vinculador(base) { u, t -> ClienteServidor(u, t) }
                    when (val r = vinculador.vincular(DatosDelQr(url, token))) {
                        is ResultadoDeVinculacion.Vinculado -> pantalla = Pantalla.Escaneando
                        is ResultadoDeVinculacion.Fallo -> error = r.mensaje
                    }
                    vinculando = false
                }
            }
        }

        Pantalla.Escaneando -> Aviso("Listo para contar.")
    }
}
```

Y agregar los imports: `androidx.compose.runtime.rememberCoroutineScope`, `kotlinx.coroutines.launch`, `com.controldestock.nucleo.DatosDelQr`, `com.controldestock.red.ClienteServidor`, `com.controldestock.ui.PantallaVinculacion`, `com.controldestock.Vinculador`, `com.controldestock.ResultadoDeVinculacion`.

**La guarda `if (!vinculando)` importa:** la cámara avisa una lectura por cuadro, así que sin ella el mismo QR dispara veinte vinculaciones en un segundo.

- [ ] **Step 14: Correr toda la suite**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS

- [ ] **Step 15: Probar la vinculación de verdad**

1. Levantar el servidor: `.\"Iniciar servidor.bat"`.
2. En el panel, crear una sesión, importar un maestro y dar de alta un operario.
3. Instalar la app: `gradle :app:assembleDebug` y `adb install -r app\build\outputs\apk\debug\app-debug.apk`.
4. Abrir la app en el celular, dar permiso de cámara, y escanear el QR del operario desde la pantalla del panel.
5. Verificar que pasa a «Listo para contar».

**Esto no se puede automatizar**: la lectura de un QR en una pantalla, con la cámara real, es exactamente lo que ningún test cubre. Si el QR no se lee, probar acercando o alejando el celular y con más luz, y reportarlo.

- [ ] **Step 16: Commit**

```bash
git add celular/
git commit -m "Vincula el celular escaneando el QR del panel

El QR lleva la direccion del servidor y el token, asi que el operario no
tipea nada: ni la IP, que cambia en cada lugar, ni 43 caracteres al azar.

Vincular y descargar el maestro van juntos. Un celular vinculado sin
maestro abre la camara y rechaza todo lo que se escanee, que es peor que
no estar vinculado, porque parece que funciona.

Un QR que no es el del panel lo dice y sigue escaneando: el operario va a
apuntar sin querer a media docena de cosas antes de dar con el correcto."
```

---

### Task 3: Escanear y cargar la cantidad

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/Contador.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/FichaDelArticulo.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/Aviso.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Interfaces:**
- Consumes: `BaseLocal`, `ReglasDeCarga`, `EventoConteo`, `VistaDeCamara`
- Produces:
  - `Contador(base, reloj)` con:
    - `suspend fun buscar(codigo: String): Hallazgo`
    - `suspend fun registrar(articulo: ArticuloEntidad, milesimas: Int, ubicacionReal: String?, observaciones: String?)`
  - `Hallazgo` — `Encontrado(articulo, unidad)` o `Desconocido(codigo)`
  - `AvisoSonoro` — los tres timbres: `leido()`, `desconocido()`, `error()`

- [ ] **Step 1: Escribir el test del contador**

Crear `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`:

```kotlin
package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.Reloj
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

class RelojDeContador(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class ContadorTest {

    private lateinit var base: BaseLocal
    private val reloj = RelojDeContador("2026-08-12T10:00:00Z")

    @Before
    fun preparar() = runTest {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()

        base.maestroDao().reemplazarMaestro(
            articulos = listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", "P-1"),
                ),
                ArticuloEntidad(
                    id = 2, idOrden = 2, sku = "A-2", descripcion = "Harina",
                    unidad = "KG", ubicacion = "P-2", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Harina", "A-2", "P-2"),
                ),
            ),
            codigos = listOf(CodigoEntidad("7790001", 1), CodigoEntidad("7790002", 2)),
            unidades = listOf(
                UnidadEntidad("UN", "Unidad", 0),
                UnidadEntidad("KG", "Kilogramo", 1),
            ),
        )
    }

    @After
    fun terminar() = base.close()

    private fun contador() = Contador(base, reloj)

    @Test
    fun `encuentra el articulo por el codigo escaneado`() = runTest {
        val hallazgo = contador().buscar("7790001")

        assertTrue(hallazgo is Hallazgo.Encontrado)
        assertEquals("Fideos", (hallazgo as Hallazgo.Encontrado).articulo.descripcion)
    }

    @Test
    fun `dice si la unidad admite decimales`() = runTest {
        // Es lo que decide si medio kilo se carga sin preguntar o pide
        // confirmación.
        val fideos = contador().buscar("7790001") as Hallazgo.Encontrado
        val harina = contador().buscar("7790002") as Hallazgo.Encontrado

        assertEquals(false, fideos.admiteDecimales)
        assertEquals(true, harina.admiteDecimales)
    }

    @Test
    fun `un codigo que no esta en el maestro se reporta como desconocido`() = runTest {
        val hallazgo = contador().buscar("no-existe")

        assertEquals(Hallazgo.Desconocido("no-existe"), hallazgo)
    }

    @Test
    fun `una unidad que no esta en el catalogo no rompe el escaneo`() = runTest {
        // El maestro puede traer una unidad que no bajó: no se puede dejar al
        // operario sin poder contar por eso.
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = 3, idOrden = 3, sku = "A-3", descripcion = "Raro",
                    unidad = "XX", ubicacion = null, pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Raro", "A-3", null),
                ),
            ),
        )
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad("7790003", 3)))

        val hallazgo = contador().buscar("7790003") as Hallazgo.Encontrado

        assertEquals(false, hallazgo.admiteDecimales)
    }

    @Test
    fun `registrar guarda el conteo pendiente en la base local`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 48000, null, null)

        val guardado = base.conteoDao().todos().single()
        assertEquals(48000, guardado.cantidad)
        assertEquals("7790001", guardado.codigo)
        assertEquals(EstadoSync.PENDIENTE, guardado.estadoSync)
        assertEquals("2026-08-12T10:00:00Z", guardado.timestampDispositivo)
    }

    @Test
    fun `el conteo viaja con un codigo de barras real y no con el sku`() = runTest {
        // El servidor resuelve solo por código de barras. Mandar el SKU falla
        // en los artículos que tienen un código propio distinto.
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, null, null)

        assertEquals("7790001", base.conteoDao().todos().single().codigo)
    }

    @Test
    fun `guarda la ubicacion real y las observaciones cuando las hay`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, "P-9", "Estaba en otro estante")

        val guardado = base.conteoDao().todos().single()
        assertEquals("P-9", guardado.ubicacionReal)
        assertEquals("Estaba en otro estante", guardado.observaciones)
    }

    @Test
    fun `el conteo queda atado a la sesion del maestro`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, null, null)

        assertEquals(1, base.conteoDao().todos().single().sesionId)
    }

    @Test
    fun `dos escaneos del mismo articulo son dos conteos`() = runTest {
        // Dentro de una pasada los conteos suman: el mismo producto puede
        // estar en dos estantes.
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, null, null)
        contador().registrar(articulo, 2000, null, null)

        assertEquals(2, base.conteoDao().todos().size)
    }

    @Test
    fun `las ubicaciones del maestro estan disponibles para corregir`() = runTest {
        assertEquals(listOf("P-1", "P-2"), contador().ubicaciones())
    }
}
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: FAIL con `Unresolved reference: Contador`

- [ ] **Step 3: Implementar `Contador.kt`**

```kotlin
package com.controldestock

import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.ConteoEntidad
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj

sealed class Hallazgo {
    data class Encontrado(
        val articulo: ArticuloEntidad,
        val admiteDecimales: Boolean,
        val codigo: String,
    ) : Hallazgo()

    data class Desconocido(val codigo: String) : Hallazgo()
}

/**
 * Resuelve un código escaneado y guarda el conteo.
 *
 * Todo contra la base local: la pantalla confirma sin pedirle nada al
 * servidor, así el operario cuenta igual sin señal.
 */
class Contador(
    private val base: BaseLocal,
    private val reloj: Reloj,
) {

    suspend fun buscar(codigo: String): Hallazgo {
        val articulo = base.maestroDao().porCodigo(codigo)
            ?: return Hallazgo.Desconocido(codigo)

        // Una unidad que no bajó en el maestro no puede dejar al operario sin
        // contar: se asume entera, que es el caso conservador.
        val admite = base.maestroDao().unidad(articulo.unidad)?.admiteDecimales == 1

        return Hallazgo.Encontrado(articulo, admite, codigo)
    }

    suspend fun ubicaciones(): List<String> = base.maestroDao().ubicaciones()

    suspend fun registrar(
        articulo: ArticuloEntidad,
        milesimas: Int,
        ubicacionReal: String?,
        observaciones: String?,
    ) {
        // El conteo viaja con el código de barras y no con el SKU: el
        // servidor resuelve solo por código, y un artículo con código propio
        // no tiene una fila donde el código sea su SKU.
        val codigo = base.maestroDao().codigoDe(articulo.id) ?: articulo.sku

        val evento = EventoConteo.nuevo(
            codigo = codigo,
            cantidad = milesimas,
            reloj = reloj,
            ubicacionReal = ubicacionReal,
            observaciones = observaciones,
        )

        base.conteoDao().guardar(
            ConteoEntidad.de(evento, articulo.id, articulo.sesionId),
        )
    }
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, 10 tests nuevos

- [ ] **Step 5: Implementar `Aviso.kt` — los tres timbres**

```kotlin
package com.controldestock.ui

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

/**
 * Los tres avisos, cada uno por sonido y por vibración a la vez.
 *
 * En un depósito ruidoso no se escucha; con el celular en movimiento no se
 * ve. Al menos uno de los dos siempre llega, y el color de la pantalla es
 * el tercero.
 */
class AvisoSonoro(contexto: Context) {

    private val tonos = ToneGenerator(AudioManager.STREAM_MUSIC, 100)

    private val vibrador: Vibrator? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (contexto.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)
                ?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            contexto.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }

    /** Leído: corto y agudo. */
    fun leido() {
        tonos.startTone(ToneGenerator.TONE_PROP_BEEP, 120)
        vibrar(60)
    }

    /** Código que no está en el maestro: distinto, para no confundirlo. */
    fun desconocido() {
        tonos.startTone(ToneGenerator.TONE_PROP_BEEP2, 300)
        vibrar(200)
    }

    /** Error: el más largo. */
    fun error() {
        tonos.startTone(ToneGenerator.TONE_SUP_ERROR, 400)
        vibrar(400)
    }

    /** Confirmación de carga: apenas un golpecito. */
    fun cargado() {
        tonos.startTone(ToneGenerator.TONE_PROP_ACK, 100)
        vibrar(40)
    }

    private fun vibrar(milisegundos: Long) {
        val v = vibrador ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            v.vibrate(VibrationEffect.createOneShot(milisegundos, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            v.vibrate(milisegundos)
        }
    }

    fun cerrar() = tonos.release()
}
```

Agregar al manifiesto, con los demás permisos:

```xml
    <uses-permission android:name="android.permission.VIBRATE" />
```

- [ ] **Step 6: Implementar `FichaDelArticulo.kt`**

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.nucleo.Cantidades
import com.controldestock.nucleo.ReglasDeCarga
import com.controldestock.nucleo.ResultadoDeCarga

/**
 * La ficha que sube al leer un código.
 *
 * La descripción domina la pantalla: el operario tiene que confirmar de un
 * vistazo que tiene el producto correcto en la mano. El teclado es propio y
 * con teclas grandes, porque se usa con apuro y a veces con guantes.
 */
@Composable
fun FichaDelArticulo(
    articulo: ArticuloEntidad,
    admiteDecimales: Boolean,
    ubicaciones: List<String>,
    alCancelar: () -> Unit,
    // Último para que quede como lambda final en la llamada.
    alConfirmar: (Int, String?, String?) -> Unit,
) {
    var texto by remember { mutableStateOf("") }
    var ubicacionReal by remember { mutableStateOf<String?>(null) }
    var observaciones by remember { mutableStateOf("") }
    var aviso by remember { mutableStateOf<String?>(null) }
    var confirmarDecimal by remember { mutableStateOf<Int?>(null) }
    var eligiendoUbicacion by remember { mutableStateOf(false) }

    fun confirmar() {
        when (val r = ReglasDeCarga.validar(texto, admiteDecimales)) {
            is ResultadoDeCarga.Valida ->
                alConfirmar(r.milesimas, ubicacionReal, observaciones.ifBlank { null })
            is ResultadoDeCarga.PideConfirmacion -> {
                aviso = r.motivo
                confirmarDecimal = r.milesimas
            }
            is ResultadoDeCarga.Invalida -> aviso = r.motivo
        }
    }

    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            articulo.descripcion,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "SKU ${articulo.sku} · #${articulo.idOrden}",
            style = MaterialTheme.typography.bodyMedium,
        )
        listOfNotNull(articulo.grupo, articulo.material).takeIf { it.isNotEmpty() }?.let {
            Text(it.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Ubicación: ${ubicacionReal ?: articulo.ubicacion ?: "sin ubicación"}")
            TextButton(onClick = { eligiendoUbicacion = true }) { Text("Corregir") }
        }

        Text(
            "${texto.ifEmpty { "0" }} ${articulo.unidad}",
            fontSize = 40.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        )

        TecladoNumerico(
            alTocar = { tecla ->
                aviso = null
                texto = when (tecla) {
                    "C" -> ""
                    else -> texto + tecla
                }
            },
            alBorrar = { texto = texto.dropLast(1) },
        )

        OutlinedTextField(
            value = observaciones,
            onValueChange = { observaciones = it },
            label = { Text("Observaciones (opcional)") },
            modifier = Modifier.fillMaxWidth(),
        )

        aviso?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            TextButton(onClick = alCancelar, modifier = Modifier.weight(1f)) {
                Text("Cancelar")
            }
            Button(
                onClick = ::confirmar,
                modifier = Modifier.weight(2f).height(56.dp),
            ) {
                Text("Confirmar", fontSize = 18.sp)
            }
        }
    }

    confirmarDecimal?.let { milesimas ->
        AlertDialog(
            onDismissRequest = { confirmarDecimal = null },
            title = { Text("¿Va con decimales?") },
            text = { Text(aviso.orEmpty()) },
            confirmButton = {
                TextButton(onClick = {
                    confirmarDecimal = null
                    alConfirmar(milesimas, ubicacionReal, observaciones.ifBlank { null })
                }) { Text("Sí, cargar") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarDecimal = null }) { Text("Corregir") }
            },
        )
    }

    if (eligiendoUbicacion) {
        ElegirUbicacion(
            ubicaciones = ubicaciones,
            alElegir = { ubicacionReal = it; eligiendoUbicacion = false },
            alCerrar = { eligiendoUbicacion = false },
        )
    }
}

@Composable
private fun TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit) {
    val filas = listOf(
        listOf("1", "2", "3"),
        listOf("4", "5", "6"),
        listOf("7", "8", "9"),
        listOf("C", "0", ","),
    )

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        filas.forEach { fila ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                fila.forEach { tecla ->
                    Button(
                        onClick = { alTocar(tecla) },
                        modifier = Modifier.weight(1f).height(64.dp),
                    ) {
                        Text(tecla, fontSize = 22.sp)
                    }
                }
                if (fila == filas.last()) {
                    Button(
                        onClick = alBorrar,
                        modifier = Modifier.weight(1f).height(64.dp),
                    ) {
                        Text("←", fontSize = 22.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun ElegirUbicacion(
    ubicaciones: List<String>,
    alElegir: (String) -> Unit,
    alCerrar: () -> Unit,
) {
    var filtro by remember { mutableStateOf("") }
    var otra by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("¿Dónde estaba?") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = filtro,
                    onValueChange = { filtro = it },
                    label = { Text("Buscar ubicación") },
                )
                ubicaciones.filter { it.contains(filtro, ignoreCase = true) }
                    .take(20)
                    .forEach { u ->
                        TextButton(onClick = { alElegir(u) }) { Text(u) }
                    }
                OutlinedTextField(
                    value = otra,
                    onValueChange = { otra = it },
                    label = { Text("Otra…") },
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (otra.isNotBlank()) alElegir(otra.trim()) else alCerrar() },
            ) { Text("Listo") }
        },
        dismissButton = { TextButton(onClick = alCerrar) { Text("Cancelar") } },
    )
}
```

- [ ] **Step 7: Implementar `PantallaEscaneo.kt`**

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.controldestock.camara.VistaDeCamara
import com.controldestock.datos.ArticuloEntidad

/**
 * La pantalla principal: la cámara siempre activa.
 *
 * El operario apunta y lee, no aprieta botones. Mientras la ficha está
 * abierta el escaneo se pausa, que es lo que evita la lectura duplicada
 * cuando el celular sigue apuntando al mismo código.
 */
@Composable
fun PantallaEscaneo(
    operario: String,
    pasada: String,
    pendientes: Int,
    fichaAbierta: Boolean,
    avisoDeDesconocido: String?,
    alLeer: (String) -> Unit,
    ficha: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(pasada, style = MaterialTheme.typography.titleMedium)
            Text(operario, style = MaterialTheme.typography.bodyMedium)
            Text(
                if (pendientes == 0) "Todo al día" else "$pendientes sin subir",
                style = MaterialTheme.typography.bodySmall,
                color = if (pendientes == 0) Verde else Ambar,
            )
        }

        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            VistaDeCamara(
                activo = !fichaAbierta,
                alLeer = alLeer,
                modifier = Modifier.fillMaxSize(),
            )

            avisoDeDesconocido?.let {
                Surface(
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
                ) {
                    Text(
                        it,
                        color = MaterialTheme.colorScheme.onError,
                        modifier = Modifier.padding(12.dp),
                    )
                }
            }
        }

        if (fichaAbierta) {
            Surface(tonalElevation = 4.dp, modifier = Modifier.fillMaxWidth()) {
                ficha()
            }
        }
    }
}
```

- [ ] **Step 8: Conectar todo en `MainActivity`**

Reemplazar la rama `Pantalla.Escaneando` del `when` por esta, y agregar el estado que necesita al principio de `App`:

```kotlin
    var hallazgo by remember { mutableStateOf<Hallazgo?>(null) }
    var avisoDesconocido by remember { mutableStateOf<String?>(null) }
    var pendientes by remember { mutableStateOf(0) }
    var ubicaciones by remember { mutableStateOf<List<String>>(emptyList()) }
    val vinculacion = remember { mutableStateOf<VinculacionEntidad?>(null) }
    val contexto = LocalContext.current
    val avisos = remember { AvisoSonoro(contexto) }
    val contador = remember { Contador(base, RelojDelSistema.DEL_SISTEMA) }

    DisposableEffect(Unit) { onDispose { avisos.cerrar() } }
```

Y en el `LaunchedEffect(Unit)` inicial, además de decidir la pantalla:

```kotlin
        vinculacion.value = base.vinculacionDao().actual()
        pendientes = base.conteoDao().cantidadPendientes()
        ubicaciones = contador.ubicaciones()
```

La rama:

```kotlin
        Pantalla.Escaneando -> {
            val quien = vinculacion.value
            PantallaEscaneo(
                operario = quien?.operarioNombre.orEmpty(),
                pasada = quien?.pasadaEtiqueta.orEmpty(),
                pendientes = pendientes,
                fichaAbierta = hallazgo is Hallazgo.Encontrado,
                avisoDeDesconocido = avisoDesconocido,
                alLeer = { codigo ->
                    if (hallazgo == null) {
                        alcance.launch {
                            when (val h = contador.buscar(codigo)) {
                                is Hallazgo.Encontrado -> {
                                    avisos.leido()
                                    avisoDesconocido = null
                                    hallazgo = h
                                }
                                is Hallazgo.Desconocido -> {
                                    avisos.desconocido()
                                    avisoDesconocido =
                                        "Este código no está en el conteo: ${h.codigo}"
                                }
                            }
                        }
                    }
                },
            ) {
                (hallazgo as? Hallazgo.Encontrado)?.let { encontrado ->
                    FichaDelArticulo(
                        articulo = encontrado.articulo,
                        admiteDecimales = encontrado.admiteDecimales,
                        ubicaciones = ubicaciones,
                        alCancelar = { hallazgo = null },
                    ) { milesimas, ubicacionReal, observaciones ->
                        alcance.launch {
                            contador.registrar(
                                encontrado.articulo, milesimas, ubicacionReal, observaciones,
                            )
                            pendientes = base.conteoDao().cantidadPendientes()
                            avisos.cargado()
                            hallazgo = null
                        }
                    }
                }
            }
        }
```

Imports nuevos: `androidx.compose.runtime.DisposableEffect`, `androidx.compose.ui.platform.LocalContext`, `com.controldestock.Contador`, `com.controldestock.Hallazgo`, `com.controldestock.datos.VinculacionEntidad`, `com.controldestock.nucleo.RelojDelSistema`, `com.controldestock.ui.AvisoSonoro`, `com.controldestock.ui.PantallaEscaneo`, `com.controldestock.ui.FichaDelArticulo`.

**La guarda `if (hallazgo == null)`** hace lo mismo que en la vinculación: la cámara avisa una lectura por cuadro y sin ella se abrirían decenas de fichas.

- [ ] **Step 9: Correr toda la suite**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS

- [ ] **Step 10: Probar el escaneo con códigos reales**

Instalar y abrir. Con el maestro ya descargado:

1. Escanear un código de barras de un producto que esté en el maestro: tiene que sonar, vibrar y subir la ficha.
2. Cargar una cantidad con el teclado y confirmar: golpecito corto y vuelta a la cámara.
3. Escanear un código que no esté: sonido distinto y el aviso rojo abajo.
4. Con una unidad decimal (KG), cargar `3,5`: entra sin preguntar. Con una entera (UN), cargar `3,5`: pide confirmación y deja seguir.
5. Verificar que **mientras la ficha está abierta no se leen más códigos**.

Ninguno de estos cinco pasos lo cubre un test: la cámara real, el sonido y la vibración solo se prueban en la mano.

- [ ] **Step 11: Commit**

```bash
git add celular/
git commit -m "Agrega el escaneo y la carga de cantidad

La camara esta siempre activa: el operario apunta y lee, no aprieta
botones. Mientras la ficha esta abierta el escaneo se pausa, que es lo que
evita la lectura duplicada cuando el celular sigue apuntando al mismo
codigo.

Cada aviso suena y vibra distinto: leido, desconocido y error. En un
deposito ruidoso no se escucha y con el celular en movimiento no se ve, asi
que al menos uno de los dos siempre llega.

El conteo viaja con el codigo de barras y no con el SKU: el servidor
resuelve solo por codigo, y un articulo con codigo propio no tiene ninguna
fila donde el codigo sea su SKU.

La ficha confirma contra la base local y nunca contra la red, asi el
operario cuenta igual sin señal."
```

---

### Task 4: Que lo contado llegue al tablero

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/Sincronizador.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/SincronizadorTest.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/TrabajoDeSincronizacion.kt`
- Modify: `celular/app/build.gradle.kts`
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Interfaces:**
- Consumes: `PlanDeSincronizacion`, `ClienteServidor`, `BaseLocal`
- Produces:
  - `Sincronizador(base, crearCliente)` con `suspend fun sincronizar(): ResultadoDeSync`
  - `ResultadoDeSync(enviados: Int, rechazados: Int, huboError: Boolean)`
  - `TrabajoDeSincronizacion` — el `CoroutineWorker` que lo corre en segundo plano

- [ ] **Step 1: Agregar WorkManager**

En `celular/app/build.gradle.kts`:

```kotlin
    implementation("androidx.work:work-runtime-ktx:2.9.0")
```

- [ ] **Step 2: Escribir el test que falla**

Crear `celular/app/src/test/kotlin/com/controldestock/SincronizadorTest.kt`:

```kotlin
package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.ConteoEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import com.controldestock.red.ClienteServidor
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

class RelojDeSync(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class SincronizadorTest {

    private lateinit var base: BaseLocal
    private lateinit var servidor: MockWebServer
    private val reloj = RelojDeSync("2026-08-12T10:00:00Z")

    @Before
    fun preparar() = runTest {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
        servidor = MockWebServer()
        servidor.start()

        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = servidor.url("/").toString().trimEnd('/'), token = "token",
                operarioId = 1, operarioNombre = "Juan", sesionId = 1,
                pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )
        base.maestroDao().reemplazarMaestro(
            listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", "P-1"),
                ),
            ),
            listOf(CodigoEntidad("7790001", 1)),
            emptyList(),
        )
    }

    @After
    fun terminar() {
        base.close()
        servidor.shutdown()
    }

    private fun responder(cuerpo: String, codigo: Int = 200) {
        servidor.enqueue(
            MockResponse().setResponseCode(codigo)
                .setHeader("Content-Type", "application/json").setBody(cuerpo),
        )
    }

    private fun sincronizador() =
        Sincronizador(base) { url, token -> ClienteServidor(url, token) }

    private suspend fun guardarPendiente(codigo: String = "7790001") {
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo(codigo, 1000, reloj), 1, 1),
        )
    }

    @Test
    fun `manda los pendientes y los marca como enviados`() = runTest {
        guardarPendiente()
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(1, resultado.enviados)
        assertEquals(0, base.conteoDao().cantidadPendientes())
        assertEquals(EstadoSync.ENVIADO, base.conteoDao().todos().single().estadoSync)
    }

    @Test
    fun `sin pendientes no molesta al servidor`() = runTest {
        val resultado = sincronizador().sincronizar()

        assertEquals(0, resultado.enviados)
        assertEquals(0, servidor.requestCount)
    }

    @Test
    fun `sin vinculacion no hace nada`() = runTest {
        base.vinculacionDao().borrar()
        guardarPendiente()

        val resultado = sincronizador().sincronizar()

        assertEquals(0, servidor.requestCount)
        assertEquals(1, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `un rechazo definitivo queda marcado con su motivo`() = runTest {
        guardarPendiente("no-existe")
        val uuid = base.conteoDao().todos().single().uuid
        responder(
            """{"registrados":0,"duplicados":0,"rechazados":[
                {"uuid":"$uuid","motivo":"Código desconocido","reintentable":false}]}""",
        )

        val resultado = sincronizador().sincronizar()

        assertEquals(1, resultado.rechazados)
        val guardado = base.conteoDao().todos().single()
        assertEquals(EstadoSync.RECHAZADO, guardado.estadoSync)
        assertEquals("Código desconocido", guardado.motivoRechazo)
    }

    @Test
    fun `si el servidor no contesta el conteo sigue pendiente`() = runTest {
        // Es el caso normal del depósito: nada se pierde, se reintenta.
        guardarPendiente()
        servidor.shutdown()

        val resultado = sincronizador().sincronizar()

        assertTrue(resultado.huboError)
        assertEquals(1, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `un duplicado no vuelve a quedar pendiente`() = runTest {
        // El servidor ya lo tenía: reenviar fue inofensivo y no hay nada que
        // arreglar de este lado.
        guardarPendiente()
        responder("""{"registrados":0,"duplicados":1,"rechazados":[]}""")

        sincronizador().sincronizar()

        assertEquals(0, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `la anulacion de un conteo rechazado no se reintenta para siempre`() = runTest {
        // Sin esto la cola nunca se vacía: el servidor rechaza la anulación
        // como reintentable porque el conteo que anula nunca le llegó.
        guardarPendiente("no-existe")
        val original = base.conteoDao().todos().single()
        base.conteoDao().marcar(original.uuid, EstadoSync.RECHAZADO, "Código desconocido")
        base.conteoDao().guardar(
            ConteoEntidad.de(
                EventoConteo.anulacionDe(original.aEvento(), reloj), 1, 1,
            ),
        )

        val resultado = sincronizador().sincronizar()

        assertEquals(0, servidor.requestCount)
        assertEquals(0, base.conteoDao().cantidadPendientes())
        assertEquals(0, resultado.enviados)
    }
}
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: FAIL con `Unresolved reference: Sincronizador`

- [ ] **Step 4: Implementar `Sincronizador.kt`**

```kotlin
package com.controldestock

import com.controldestock.datos.BaseLocal
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.PlanDeSincronizacion
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor

data class ResultadoDeSync(
    val enviados: Int = 0,
    val rechazados: Int = 0,
    val huboError: Boolean = false,
)

/**
 * Empuja al servidor los conteos que todavía no subieron.
 *
 * Nunca borra ni edita un conteo local: solo cambia su estado. Si algo sale
 * mal, lo pendiente sigue pendiente y se reintenta más tarde — perder un
 * conteo es peor que mandarlo dos veces, y el `uuid` hace que mandarlo dos
 * veces sea inofensivo.
 */
class Sincronizador(
    private val base: BaseLocal,
    private val crearCliente: (String, String) -> ClienteServidor,
) {

    suspend fun sincronizar(): ResultadoDeSync {
        val vinculacion = base.vinculacionDao().actual() ?: return ResultadoDeSync()

        val locales = base.conteoDao().todos().map { it.aLocal() }

        // Las anulaciones de conteos que el servidor nunca aceptó se cierran
        // acá: mandarlas deja la cola girando para siempre.
        val sinDestino = PlanDeSincronizacion.anulacionesSinDestino(locales)
        sinDestino.forEach {
            base.conteoDao().marcar(
                it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo,
            )
        }

        val aEnviar = PlanDeSincronizacion.aEnviar(locales)
        if (aEnviar.isEmpty()) return ResultadoDeSync()

        val cliente = crearCliente(vinculacion.url, vinculacion.token)

        return try {
            val respuesta = cliente.enviarConteos(aEnviar)
            val resueltos = PlanDeSincronizacion.aplicar(aEnviar, respuesta)

            resueltos.forEach {
                base.conteoDao().marcar(it.evento.uuid, it.estadoSync, it.motivoRechazo)
            }

            ResultadoDeSync(
                enviados = resueltos.count { it.estadoSync == EstadoSync.ENVIADO },
                rechazados = resueltos.count { it.estadoSync == EstadoSync.RECHAZADO },
            )
        } catch (error: ErrorDeServidor) {
            // Lo pendiente sigue pendiente. No se toca nada.
            ResultadoDeSync(huboError = true)
        }
    }
}
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, 7 tests nuevos

- [ ] **Step 6: Implementar `TrabajoDeSincronizacion.kt`**

```kotlin
package com.controldestock

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.controldestock.datos.BaseLocal
import com.controldestock.red.ClienteServidor
import java.util.concurrent.TimeUnit

/**
 * Sube los conteos pendientes cuando hay red.
 *
 * Corre solo, en segundo plano, y nunca interrumpe: el operario cuenta sin
 * enterarse de si hay señal o no.
 */
class TrabajoDeSincronizacion(
    contexto: Context,
    parametros: WorkerParameters,
) : CoroutineWorker(contexto, parametros) {

    override suspend fun doWork(): Result {
        val base = BaseLocal.de(applicationContext)
        val sincronizador = Sincronizador(base) { url, token -> ClienteServidor(url, token) }

        val resultado = sincronizador.sincronizar()

        // Reintentar es responsabilidad de WorkManager: sabe esperar a que
        // haya red en vez de quemar batería probando.
        return if (resultado.huboError) Result.retry() else Result.success()
    }

    companion object {
        private const val NOMBRE = "sincronizar-conteos"

        /**
         * Cada quince minutos es el mínimo que admite WorkManager para un
         * trabajo periódico. Alcanza: el tablero no necesita ser instantáneo,
         * y la app también sincroniza al confirmar cada conteo.
         */
        fun programar(contexto: Context) {
            val pedido = PeriodicWorkRequestBuilder<TrabajoDeSincronizacion>(
                15, TimeUnit.MINUTES,
            ).setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            ).build()

            WorkManager.getInstance(contexto).enqueueUniquePeriodicWork(
                NOMBRE, ExistingPeriodicWorkPolicy.KEEP, pedido,
            )
        }
    }
}
```

- [ ] **Step 7: Sincronizar al confirmar y al arrancar**

En `MainActivity.kt`, dentro de `onCreate`, después de crear la base:

```kotlin
        TrabajoDeSincronizacion.programar(this)
```

Y en la función `App`, agregar el sincronizador y llamarlo después de registrar un conteo. Reemplazar el bloque `alcance.launch { contador.registrar(...) }` de la ficha por:

```kotlin
                        alcance.launch {
                            contador.registrar(
                                encontrado.articulo, milesimas, ubicacionReal, observaciones,
                            )
                            avisos.cargado()
                            hallazgo = null
                            pendientes = base.conteoDao().cantidadPendientes()

                            // Intento inmediato: con señal, el tablero se
                            // entera en el momento. Sin señal no pasa nada y
                            // el trabajo periódico lo sube más tarde.
                            sincronizador.sincronizar()
                            pendientes = base.conteoDao().cantidadPendientes()
                        }
```

Declarando arriba, con los demás `remember`:

```kotlin
    val sincronizador = remember {
        Sincronizador(base) { url, token -> ClienteServidor(url, token) }
    }
```

**El orden importa:** el conteo se guarda y la ficha se cierra **antes** de intentar la sincronización. Si se hiciera al revés, el operario esperaría a la red para poder seguir contando.

- [ ] **Step 8: Correr toda la suite**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS

Y la del servidor, que no debería haberse tocado:

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS

- [ ] **Step 9: El circuito completo, de punta a punta**

Este es el paso que justifica el plan entero:

1. Levantar el servidor, crear sesión, importar maestro, dar de alta un operario.
2. Instalar la app y vincular escaneando el QR.
3. Escanear un producto y cargar una cantidad.
4. **Mirar el tablero del panel**: la fila tiene que cambiar de estado sola, en menos de cinco segundos.
5. Poner el celular en modo avión. Contar tres artículos más: tienen que entrar sin ninguna queja, y el indicador de arriba debe mostrar «3 sin subir».
6. Salir del modo avión y confirmar un conteo más: los cuatro suben y el indicador vuelve a «Todo al día».
7. Exportar el resumen desde el panel y confirmar que las cantidades son las que se cargaron.

- [ ] **Step 10: Commit**

```bash
git add celular/
git commit -m "Sube los conteos al servidor en segundo plano

Al confirmar un conteo se intenta subir en el momento, asi el tablero se
entera enseguida; si no hay señal no pasa nada y el trabajo periodico lo
sube mas tarde. El conteo se guarda y la ficha se cierra antes de intentar
la red: si no, el operario esperaria a la conexion para seguir contando.

Lo que el servidor rechaza definitivamente queda marcado con su motivo en
vez de reintentarse para siempre, y la anulacion de un conteo que nunca
entro se cierra sin mandarse, que es lo que dejaba la cola girando."
```

---

## Verificación final del plan

```bash
cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Los dos en verde, y el circuito del Step 9 de la Task 4 andando en el celular.

Con esto la app **sirve para contar un depósito**: se vincula, descarga el maestro, escanea, carga cantidades con corrección de ubicación y observaciones, funciona sin señal y sube todo cuando hay red.

**Lo que queda para el plan siguiente:** alta rápida de códigos desconocidos, «Mis conteos» con anulación, «Buscar» para las etiquetas ilegibles, la linterna, y el empaquetado del APK firmado para distribuir desde el panel.
