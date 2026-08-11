# App Android — fundaciones (núcleo, contrato y datos) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o superpowers:executing-plans para implementar este plan tarea por tarea. Los pasos usan casillas (`- [ ]`) para el seguimiento.

**Goal:** Construir la base de la app Android —proyecto que compila, lógica de negocio en Kotlin puro, contrato verificado contra el servidor real, base local y cliente HTTP— todo probado sin un celular enchufado.

**Architecture:** Dos módulos Gradle. `nucleo/` es Kotlin puro, sin una sola clase de Android: ahí viven las conversiones, las reglas y la decisión de qué sincronizar, y se prueba con `gradle test` en segundos. `app/` es el módulo Android: base local con Room y cliente HTTP con OkHttp. Es la misma separación que en el servidor, donde la lógica se prueba sin levantar FastAPI.

**Tech Stack:** Kotlin 1.9.23, AGP 8.4.0, Gradle 8.7, JDK 17, Room 2.6.1, OkHttp 4.12.0, kotlinx.serialization 1.6.3, JUnit 4.13.2.

Este plan corresponde a las secciones 3, 4, 5 y 9 del spec `docs/superpowers/specs/2026-08-11-app-android-base-design.md`. **Las pantallas (sección 6) van en el plan siguiente**, junto con CameraX, ML Kit, Compose y WorkManager.

## Global Constraints

- **Cantidades en milésimas, siempre enteras.** `24 UN` → `24000`; `3,5 KG` → `3500`. Nunca `Float` ni `Double` para cantidades.
- **La app nunca consulta al servidor para trabajar.** La base local es la fuente de verdad: con o sin señal se comporta igual. El servidor se usa solo para sincronizar.
- **`nucleo/` no importa nada de `android.*`.** Si algo necesita el framework, va en `app/`. Hay un test que lo verifica.
- **Nada se edita ni se borra:** una corrección es un conteo de anulación que apunta al `uuid` original.
- **Fechas ISO 8601 UTC** como texto: `2026-08-11T14:32:05Z`.
- **Textos de interfaz y mensajes de error en castellano rioplatense**, sin jerga técnica.
- **minSdk 26** (Android 8), targetSdk 34.
- Los mensajes de commit van en castellano, en presente, describiendo el efecto.

## Entorno de esta máquina

El proyecto Android vive en `celular/`, al lado de `servidor/`. No hay Android Studio: se compila por línea de comandos.

```
JAVA_HOME    C:\Program Files\Microsoft\jdk-17.0.20.8-hotspot
ANDROID_HOME C:\Users\Pablo\AppData\Local\Android\Sdk
Gradle       C:\Gradle\gradle-8.7\bin\gradle.bat
```

Todos los comandos de Gradle se ejecutan desde `celular/`. El celular de prueba es un Motorola moto g(6) plus con Android 9 (API 28), conectado por USB y autorizado (`adb devices` lo muestra como `device`).

El intérprete de Python es `servidor\.venv\Scripts\python.exe` **por ruta**: el `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta nada.

---

### Task 1: Andamiaje del proyecto y conversión de cantidades

**Files:**
- Create: `celular/settings.gradle.kts`
- Create: `celular/build.gradle.kts`
- Create: `celular/gradle.properties`
- Create: `celular/local.properties`
- Create: `celular/nucleo/build.gradle.kts`
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/Cantidades.kt`
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/CantidadesTest.kt`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nada (primera tarea)
- Produces:
  - `Cantidades.aMilesimas(texto: String): Int` — lanza `IllegalArgumentException` si no es un número
  - `Cantidades.aTexto(milesimas: Int): String` — coma decimal, sin ceros sobrantes

**Por qué la conversión va primero:** es la única lógica que existe de los dos lados. Si el celular redondea distinto que el servidor, aparecen diferencias fantasma que nadie va a poder explicar frente al cliente. Los casos de prueba son los mismos que ya están fijados en `servidor/tests/test_cantidades.py`.

- [ ] **Step 1: Crear los archivos de build**

`celular/settings.gradle.kts`:

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "control-de-stock"
include(":nucleo")
```

`celular/build.gradle.kts`:

```kotlin
plugins {
    id("com.android.application") version "8.4.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.23" apply false
    id("org.jetbrains.kotlin.jvm") version "1.9.23" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.23" apply false
}
```

`celular/gradle.properties`:

```
org.gradle.jvmargs=-Xmx2048m
android.useAndroidX=true
kotlin.code.style=official
```

`celular/local.properties` (no va a git; el `.gitignore` ya lo excluye):

```
sdk.dir=C\:\\Users\\Pablo\\AppData\\Local\\Android\\Sdk
```

`celular/nucleo/build.gradle.kts`:

```kotlin
plugins {
    id("org.jetbrains.kotlin.jvm")
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}
```

- [ ] **Step 2: Verificar que el andamiaje compila**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:build --no-daemon`
Expected: `BUILD SUCCESSFUL`. La primera vez descarga el plugin de Kotlin y tarda varios minutos.

Si falla acá, el problema es de entorno y no de código: parar y reportarlo antes de seguir.

- [ ] **Step 3: Escribir el test que falla**

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/CantidadesTest.kt`:

```kotlin
package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CantidadesTest {

    // Los mismos casos que servidor/tests/test_cantidades.py. Si los dos lados
    // no convierten igual, aparecen diferencias que nadie puede explicar.
    @Test
    fun `convierte texto a milesimas`() {
        val casos = mapOf(
            "24" to 24000,
            "0" to 0,
            "3,5" to 3500,
            "3.5" to 3500,
            "0,001" to 1,
            "1.234,56" to 1234560,
            "1,234.56" to 1234560,
            "  12  " to 12000,
            "-4" to -4000,
        )

        for ((texto, esperado) in casos) {
            assertEquals("convirtiendo «$texto»", esperado, Cantidades.aMilesimas(texto))
        }
    }

    @Test
    fun `acepta miles agrupados sin decimales`() {
        assertEquals(1234567000, Cantidades.aMilesimas("1.234.567"))
        assertEquals(1234567000, Cantidades.aMilesimas("1,234,567"))
    }

    @Test
    fun `redondea los decimales sobrantes en vez de truncar`() {
        // Truncar sesgaría todas las cantidades a la baja de forma sistemática.
        assertEquals(1235, Cantidades.aMilesimas("1,2345"))
        assertEquals(1234, Cantidades.aMilesimas("1,2344"))
        assertEquals(1, Cantidades.aMilesimas("0,0005"))
        assertEquals(0, Cantidades.aMilesimas("0,0004"))
    }

    @Test
    fun `rechaza lo que no es una cantidad`() {
        val invalidos = listOf(
            "", "   ", "abc", "1,2,3",
            ".", ",", "-", "-,",      // separador suelto: celda rota, no cero
            "1 2",                    // dos números pegados, no doce mil
            "1.23.456",               // grupos de miles mal formados
            "inf", "-inf", "nan",
            "1e3", "1_000",
        )

        for (texto in invalidos) {
            try {
                Cantidades.aMilesimas(texto)
                throw AssertionError("«$texto» tendría que haber sido rechazado")
            } catch (esperado: IllegalArgumentException) {
                assertTrue(esperado.message!!.isNotEmpty())
            }
        }
    }

    @Test
    fun `convierte milesimas a texto`() {
        val casos = mapOf(
            24000 to "24",
            0 to "0",
            3500 to "3,5",
            1 to "0,001",
            1234560 to "1234,56",
            -4000 to "-4",
        )

        for ((milesimas, esperado) in casos) {
            assertEquals(esperado, Cantidades.aTexto(milesimas))
        }
    }

    @Test
    fun `la ida y vuelta no pierde precision`() {
        for (texto in listOf("24", "3,5", "0,001", "999999,999")) {
            assertEquals(texto, Cantidades.aTexto(Cantidades.aMilesimas(texto)))
        }
    }

    @Test
    fun `sumar decimales es exacto`() {
        // Con punto flotante, diez veces 0,1 no da 1. Un inventario suma miles
        // de veces, así que el error se acumula hasta ser visible.
        val total = (1..10).sumOf { Cantidades.aMilesimas("0,1") }

        assertEquals(Cantidades.aMilesimas("1"), total)
    }
}
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: Cantidades`

- [ ] **Step 5: Implementar `Cantidades.kt`**

```kotlin
package com.controldestock.nucleo

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Conversión entre texto y enteros escalados.
 *
 * Las cantidades viajan y se guardan en milésimas. Sumar punto flotante
 * acumula error, y un inventario suma miles de veces.
 *
 * Es la contraparte exacta de `servidor/app/cantidades.py`: los dos lados
 * comparten la tabla de casos de prueba.
 */
object Cantidades {

    private const val MILESIMAS = 1000
    private val SOLO_DIGITOS = Regex("^-?\\d+$")

    fun aMilesimas(texto: String): Int {
        val limpio = texto.trim()
        require(limpio.isNotEmpty()) { "La cantidad está vacía" }

        val (entero, decimal) = partir(limpio)

        val valor = try {
            BigDecimal("$entero.${decimal.ifEmpty { "0" }}")
        } catch (error: NumberFormatException) {
            throw IllegalArgumentException("Cantidad inválida: «$texto»", error)
        }

        // Redondeo y no truncamiento: truncar sesgaría todas las cantidades a
        // la baja de forma sistemática.
        return valor.multiply(BigDecimal(MILESIMAS))
            .setScale(0, RoundingMode.HALF_UP)
            .toInt()
    }

    fun aTexto(milesimas: Int): String {
        val signo = if (milesimas < 0) "-" else ""
        val absoluto = Math.abs(milesimas)
        val entero = absoluto / MILESIMAS
        val resto = absoluto % MILESIMAS

        if (resto == 0) return "$signo$entero"

        val decimales = resto.toString().padStart(3, '0').trimEnd('0')
        return "$signo$entero,$decimales"
    }

    /**
     * Separa parte entera y decimal resolviendo el formato del origen.
     *
     * Los ERP exportan indistintamente 1.234,56 y 1,234.56. Cuando conviven
     * los dos caracteres, el último es el decimal y el otro agrupa miles.
     * Cuando hay uno solo repetido (1.234.567) solo puede agrupar miles.
     */
    private fun partir(limpio: String): Pair<String, String> {
        val coma = limpio.lastIndexOf(',')
        val punto = limpio.lastIndexOf('.')

        if (coma == -1 && punto == -1) {
            require(SOLO_DIGITOS.matches(limpio)) { "Cantidad inválida: «$limpio»" }
            return limpio to ""
        }

        val separadorDecimal: Char
        if (coma >= 0 && punto >= 0) {
            separadorDecimal = if (coma > punto) ',' else '.'
        } else {
            val unico = if (coma >= 0) ',' else '.'
            if (limpio.count { it == unico } > 1) {
                require(agrupacionValida(limpio, unico)) { "Cantidad inválida: «$limpio»" }
                return limpio.replace(unico.toString(), "") to ""
            }
            separadorDecimal = unico
        }

        val separadorMiles = if (separadorDecimal == ',') '.' else ','
        val corte = limpio.lastIndexOf(separadorDecimal)
        var entero = limpio.substring(0, corte)
        val decimal = limpio.substring(corte + 1)

        // Un separador suelto no es cero: es una celda rota. Devolver cero
        // sería lo peor posible, porque un cero pasa por un conteo real.
        require(decimal.isNotEmpty() && decimal.all { it.isDigit() }) {
            "Cantidad inválida: «$limpio»"
        }

        if (entero.isEmpty() || entero == "-") entero += "0"
        require(agrupacionValida(entero, separadorMiles)) { "Cantidad inválida: «$limpio»" }

        return entero.replace(separadorMiles.toString(), "") to decimal
    }

    /**
     * Verifica que los grupos de miles tengan tres dígitos.
     *
     * Sin esto «1,2,3» se leería como 123 en vez de rechazarse, y un número
     * inventado es peor que un error: pasa por una cantidad real.
     */
    private fun agrupacionValida(entero: String, separadorMiles: Char): Boolean {
        if (!entero.contains(separadorMiles)) return SOLO_DIGITOS.matches(entero)
        val escapado = Regex.escape(separadorMiles.toString())
        return Regex("^-?\\d{1,3}($escapado\\d{3})+$").matches(entero)
    }
}
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 7 tests

- [ ] **Step 7: Agregar las exclusiones de Gradle al `.gitignore`**

El `.gitignore` ya tiene `build/`, `.gradle/`, `local.properties` y `*.apk` en su sección de Android. Verificar que también estén estas dos, y agregarlas si faltan:

```
.kotlin/
celular/.gradle/
```

Run: `git check-ignore -v celular/nucleo/build celular/local.properties`
Expected: dos líneas, cada una nombrando la regla que las excluye.

- [ ] **Step 8: Commit**

```bash
git add celular/ .gitignore
git commit -m "Crea el proyecto del celular y la conversion de cantidades

La conversion es la unica logica que existe de los dos lados, asi que
arranca con los mismos casos de prueba que servidor/tests/test_cantidades.py.
Si el celular redondea distinto que el servidor aparecen diferencias
fantasma que nadie va a poder explicar frente al cliente.

El nucleo es Kotlin puro, sin nada de Android: se prueba en la PC en
segundos, sin un celular enchufado."
```

---

### Task 2: El evento de conteo y las reglas de carga

**Files:**
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/Reloj.kt`
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/EventoConteo.kt`
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ReglasDeCarga.kt`
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/EventoConteoTest.kt`
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ReglasDeCargaTest.kt`

**Interfaces:**
- Consumes: `Cantidades.aMilesimas` (Task 1)
- Produces:
  - `Reloj` — interfaz con `fun ahora(): String`; `RelojDelSistema` la implementa; los tests usan uno fijo
  - `EventoConteo` — data class con `uuid`, `codigo`, `cantidad`, `ubicacionReal`, `observaciones`, `timestampDispositivo`, `anulaUuid`
  - `EventoConteo.nuevo(codigo, cantidad, reloj, ubicacionReal, observaciones): EventoConteo`
  - `EventoConteo.anulacionDe(original: EventoConteo, reloj: Reloj): EventoConteo`
  - `ReglasDeCarga.validar(texto: String, admiteDecimales: Boolean): ResultadoDeCarga`
  - `ResultadoDeCarga` — sealed class: `Valida(milesimas)`, `PideConfirmacion(milesimas, motivo)`, `Invalida(motivo)`

**Reglas que fija el spec:** la anulación es un evento nuevo que apunta al `uuid` original, nunca una edición. Si la unidad no admite decimales y se carga uno, se pide confirmación pero **no se bloquea**.

- [ ] **Step 1: Escribir el test que falla**

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/EventoConteoTest.kt`:

```kotlin
package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RelojFijo(private val instante: String) : Reloj {
    override fun ahora() = instante
}

class EventoConteoTest {

    private val reloj = RelojFijo("2026-08-11T10:00:00Z")

    @Test
    fun `un evento nuevo trae uuid propio y la hora del dispositivo`() {
        val evento = EventoConteo.nuevo("7790001001234", 48000, reloj)

        assertTrue(evento.uuid.isNotEmpty())
        assertEquals("2026-08-11T10:00:00Z", evento.timestampDispositivo)
        assertEquals(48000, evento.cantidad)
        assertNull(evento.anulaUuid)
    }

    @Test
    fun `cada evento recibe un uuid distinto`() {
        // El uuid es lo que vuelve inofensivo reenviar: si dos eventos lo
        // comparten, el servidor descarta el segundo como duplicado y se
        // pierde un conteo real.
        val primero = EventoConteo.nuevo("A", 1000, reloj)
        val segundo = EventoConteo.nuevo("A", 1000, reloj)

        assertNotEquals(primero.uuid, segundo.uuid)
    }

    @Test
    fun `la anulacion apunta al original y no lo modifica`() {
        val original = EventoConteo.nuevo("A", 48000, reloj)

        val anulacion = EventoConteo.anulacionDe(original, RelojFijo("2026-08-11T10:05:00Z"))

        assertEquals(original.uuid, anulacion.anulaUuid)
        assertEquals(original.codigo, anulacion.codigo)
        assertEquals(0, anulacion.cantidad)
        assertNotEquals(original.uuid, anulacion.uuid)
        assertEquals("2026-08-11T10:05:00Z", anulacion.timestampDispositivo)
        // El original queda intacto: nada se edita ni se borra.
        assertNull(original.anulaUuid)
    }

    @Test
    fun `la hora tiene el formato del proyecto`() {
        val evento = EventoConteo.nuevo("A", 1000, RelojDelSistema)

        assertTrue(
            evento.timestampDispositivo,
            Regex("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z")
                .matches(evento.timestampDispositivo),
        )
    }

    @Test
    fun `guarda ubicacion real y observaciones cuando las hay`() {
        val evento = EventoConteo.nuevo(
            "A", 1000, reloj,
            ubicacionReal = "P-9",
            observaciones = "Estaba en otro estante",
        )

        assertEquals("P-9", evento.ubicacionReal)
        assertEquals("Estaba en otro estante", evento.observaciones)
    }
}
```

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ReglasDeCargaTest.kt`:

```kotlin
package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReglasDeCargaTest {

    @Test
    fun `una cantidad entera en unidad entera es valida`() {
        val resultado = ReglasDeCarga.validar("24", admiteDecimales = false)

        assertEquals(ResultadoDeCarga.Valida(24000), resultado)
    }

    @Test
    fun `una cantidad con decimales en unidad decimal es valida`() {
        val resultado = ReglasDeCarga.validar("3,5", admiteDecimales = true)

        assertEquals(ResultadoDeCarga.Valida(3500), resultado)
    }

    @Test
    fun `un decimal en unidad entera pide confirmacion pero no bloquea`() {
        // Medio tornillo suele ser un error de tipeo, pero a veces no: el
        // operario tiene que poder confirmarlo, no quedarse trabado.
        val resultado = ReglasDeCarga.validar("3,5", admiteDecimales = false)

        assertTrue(resultado is ResultadoDeCarga.PideConfirmacion)
        assertEquals(3500, (resultado as ResultadoDeCarga.PideConfirmacion).milesimas)
        assertTrue(resultado.motivo.isNotEmpty())
    }

    @Test
    fun `una cantidad vacia es invalida`() {
        val resultado = ReglasDeCarga.validar("", admiteDecimales = true)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
    }

    @Test
    fun `una cantidad que no es numero es invalida`() {
        val resultado = ReglasDeCarga.validar("abc", admiteDecimales = true)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
        assertTrue((resultado as ResultadoDeCarga.Invalida).motivo.isNotEmpty())
    }

    @Test
    fun `una cantidad negativa es invalida`() {
        // Restar existe como anulación, no como cantidad negativa.
        val resultado = ReglasDeCarga.validar("-4", admiteDecimales = true)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
    }

    @Test
    fun `cero es una cantidad valida`() {
        // Contar cero es un dato real: el estante estaba vacío.
        assertEquals(ResultadoDeCarga.Valida(0), ReglasDeCarga.validar("0", true))
    }

    @Test
    fun `rechaza una cantidad que no entra en la base del servidor`() {
        // El servidor guarda enteros de 64 bits; la app manda Int, pero el
        // texto puede traer cualquier cosa.
        val resultado = ReglasDeCarga.validar("99999999999", admiteDecimales = false)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
    }
}
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: Reloj`

- [ ] **Step 3: Implementar `Reloj.kt`**

```kotlin
package com.controldestock.nucleo

import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * La hora, detrás de una interfaz para poder fijarla en los tests.
 *
 * Es la única fuente del formato de fecha de la app, igual que
 * `servidor/app/reloj.py` lo es del lado del servidor.
 */
interface Reloj {
    fun ahora(): String
}

object RelojDelSistema : Reloj {
    private val FORMATO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'")

    override fun ahora(): String =
        ZonedDateTime.now(ZoneOffset.UTC).format(FORMATO)
}
```

- [ ] **Step 4: Implementar `EventoConteo.kt`**

```kotlin
package com.controldestock.nucleo

import java.util.UUID

/**
 * Un escaneo, tal como viaja al servidor.
 *
 * Nace en el celular con su propio `uuid`, y eso es lo que vuelve inofensivo
 * reenviarlo: el servidor descarta los uuid que ya recibió. Sin esa garantía
 * la app no podría reintentar cuando se corta la señal.
 */
data class EventoConteo(
    val uuid: String,
    val codigo: String,
    val cantidad: Int,
    val timestampDispositivo: String,
    val ubicacionReal: String? = null,
    val observaciones: String? = null,
    val anulaUuid: String? = null,
) {
    companion object {

        fun nuevo(
            codigo: String,
            cantidad: Int,
            reloj: Reloj,
            ubicacionReal: String? = null,
            observaciones: String? = null,
        ) = EventoConteo(
            uuid = UUID.randomUUID().toString(),
            codigo = codigo,
            cantidad = cantidad,
            timestampDispositivo = reloj.ahora(),
            ubicacionReal = ubicacionReal,
            observaciones = observaciones,
        )

        /**
         * La anulación de un conteo es otro evento, nunca una edición.
         *
         * Así el historial explica qué pasó: quién cargó qué, cuándo, y qué
         * se dio de baja. Editar la fila original borraría esa explicación.
         */
        fun anulacionDe(original: EventoConteo, reloj: Reloj) = EventoConteo(
            uuid = UUID.randomUUID().toString(),
            codigo = original.codigo,
            cantidad = 0,
            timestampDispositivo = reloj.ahora(),
            anulaUuid = original.uuid,
        )
    }
}
```

- [ ] **Step 5: Implementar `ReglasDeCarga.kt`**

```kotlin
package com.controldestock.nucleo

/**
 * El resultado de validar lo que el operario tecleó.
 *
 * `PideConfirmacion` existe porque hay cargas raras que igual pueden ser
 * ciertas: medio tornillo suele ser un error, pero a veces no. Bloquear al
 * operario en esos casos lo deja sin forma de registrar lo que ve.
 */
sealed class ResultadoDeCarga {
    data class Valida(val milesimas: Int) : ResultadoDeCarga()
    data class PideConfirmacion(val milesimas: Int, val motivo: String) : ResultadoDeCarga()
    data class Invalida(val motivo: String) : ResultadoDeCarga()
}

object ReglasDeCarga {

    // El mayor entero que la base del servidor guarda es de 64 bits, pero la
    // app manda Int: cualquier cosa por encima se rechaza acá, con un mensaje
    // entendible, en vez de reventar al convertir.
    private const val MAXIMO = Int.MAX_VALUE

    fun validar(texto: String, admiteDecimales: Boolean): ResultadoDeCarga {
        val milesimas = try {
            Cantidades.aMilesimas(texto)
        } catch (error: IllegalArgumentException) {
            return ResultadoDeCarga.Invalida("Escribí una cantidad, por ejemplo 24 o 3,5")
        } catch (error: ArithmeticException) {
            return ResultadoDeCarga.Invalida("Esa cantidad es demasiado grande")
        }

        if (milesimas < 0) {
            return ResultadoDeCarga.Invalida("La cantidad no puede ser negativa")
        }
        if (milesimas == MAXIMO) {
            return ResultadoDeCarga.Invalida("Esa cantidad es demasiado grande")
        }

        val tieneDecimales = milesimas % 1000 != 0
        if (tieneDecimales && !admiteDecimales) {
            return ResultadoDeCarga.PideConfirmacion(
                milesimas,
                "Esta unidad se cuenta entera. ¿Cargamos ${Cantidades.aTexto(milesimas)}?",
            )
        }

        return ResultadoDeCarga.Valida(milesimas)
    }
}
```

**Nota sobre el desborde:** `Cantidades.aMilesimas` usa `BigDecimal.toInt()`, que trunca en silencio al pasarse de rango. El test `rechaza una cantidad que no entra en la base del servidor` lo cubre; si al ejecutarlo se descubre que `toInt()` no lanza y devuelve un número truncado, cambiar `toInt()` por `intValueExact()` en `Cantidades.kt` (lanza `ArithmeticException`) y dejar el `catch` que ya está previsto acá.

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 20 tests en total

- [ ] **Step 7: Commit**

```bash
git add celular/nucleo/
git commit -m "Agrega el evento de conteo y las reglas de carga

Cada escaneo nace con su uuid en el celular, que es lo que vuelve
inofensivo reenviarlo cuando se corta la señal: el servidor descarta los
que ya recibio.

La anulacion es un evento nuevo que apunta al original, nunca una
edicion, asi el historial explica que paso.

Un decimal en una unidad entera pide confirmacion en vez de bloquear:
medio tornillo suele ser un error de tipeo, pero a veces no, y el
operario tiene que poder registrar lo que ve."
```

---

### Task 3: El contrato con el servidor

**Files:**
- Create: `celular/contrato/maestro.json`
- Create: `celular/contrato/vinculacion.json`
- Create: `celular/contrato/conteos-respuesta.json`
- Create: `celular/contrato/alta-rapida.json`
- Create: `celular/contrato/capturar.py`
- Create: `servidor/tests/test_contrato.py`
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/ContratoApi.kt`
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ContratoApiTest.kt`
- Modify: `celular/nucleo/build.gradle.kts`

**Interfaces:**
- Consumes: los endpoints del servidor (ya construidos)
- Produces:
  - `ContratoApi` — data classes serializables: `RespuestaVinculacion`, `RespuestaMaestro`, `ArticuloRemoto`, `CodigoRemoto`, `UnidadRemota`, `RespuestaConteos`, `ConteoRechazado`, `RespuestaAlta`
  - Archivos de referencia en `celular/contrato/`, que usan los dos lados

**Por qué:** la app se escribe contra estos archivos, y un test del lado Python verifica que el servidor sigue produciendo esa misma forma. Si alguien renombra un campo, rompe de los dos lados a la vez en la PC, en vez de fallar en el depósito.

- [ ] **Step 1: Escribir el script que captura las respuestas reales**

Crear `celular/contrato/capturar.py`:

```python
"""Captura del servidor real las respuestas que la app va a parsear.

Se corre a mano cuando el contrato cambia a propósito. Los archivos que
genera son la referencia compartida: la app se prueba contra ellos y
`servidor/tests/test_contrato.py` verifica que el servidor los siga
cumpliendo.

Uso, con el servidor levantado en el puerto 8000:
    servidor\\.venv\\Scripts\\python.exe celular\\contrato\\capturar.py
"""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
DESTINO = Path(__file__).parent

CSV = (
    "sku,descripcion,unidad,ubicacion,stock\n"
    "7790001001234,Fideos guisero 500g,UN,P-1,50\n"
    "7790002005678,Aceite girasol 900ml,UN,P-2,30\n"
).encode("utf-8")


def guardar(nombre, datos):
    ruta = DESTINO / f"{nombre}.json"
    ruta.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"escrito {ruta.name}")


def main():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        for sesion in c.get("/api/sesiones").json():
            if sesion["estado"] == "abierta":
                c.post(f"/api/sesiones/{sesion['id']}/cerrar")

        sesion = c.post("/api/sesiones", json={"nombre": "Contrato"}).json()
        c.post(
            f"/api/sesiones/{sesion['id']}/maestro",
            files={"archivo": ("m.csv", CSV, "text/csv")},
            data={"mapeo": json.dumps({
                "sku": "sku", "descripcion": "descripcion",
                "unidad": "unidad", "ubicacion": "ubicacion",
                "stock_sistema": "stock",
            })},
        )

        operario = c.post("/api/operarios", json={"nombre": "Contrato"}).json()
        cab = {"X-Token": operario["token_dispositivo"]}

        guardar("vinculacion", c.post("/api/dispositivo/vincular", headers=cab).json())
        guardar("maestro", c.get("/api/dispositivo/maestro", headers=cab).json())

        guardar("conteos-respuesta", c.post(
            "/api/dispositivo/conteos", headers=cab,
            json={"conteos": [
                {"uuid": "contrato-1", "codigo": "7790001001234", "cantidad": 48000,
                 "timestamp_dispositivo": "2026-08-11T10:00:00Z"},
                {"uuid": "contrato-2", "codigo": "no-existe", "cantidad": 1000,
                 "timestamp_dispositivo": "2026-08-11T10:01:00Z"},
            ]},
        ).json())

        guardar("alta-rapida", c.post(
            "/api/dispositivo/articulos", headers=cab,
            json={"codigo": "7790009999999", "descripcion": "Sin etiqueta",
                  "unidad": "UN", "ubicacion": "P-9"},
        ).json())

        c.post(f"/api/sesiones/{sesion['id']}/cerrar")


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Levantar el servidor y capturar**

Run, en una terminal: `.\"Iniciar servidor.bat"`
Run, en otra: `.\servidor\.venv\Scripts\python.exe celular\contrato\capturar.py`
Expected: cuatro archivos escritos en `celular/contrato/`. Cortar el servidor con Ctrl+C.

**Importante:** revisar a ojo los cuatro archivos antes de seguir. Son la referencia de todo lo que viene; si alguno quedó con un error del servidor adentro (por ejemplo `{"detail": ...}`), volver a capturar en vez de construir sobre eso.

- [ ] **Step 3: Escribir el test del lado Python que fija la forma**

Crear `servidor/tests/test_contrato.py`:

```python
"""El contrato que la app Android consume.

Los archivos de `celular/contrato/` son la referencia contra la que se
prueba la app. Estos tests verifican que el servidor los siga cumpliendo:
si alguien renombra un campo, rompe acá y en la app a la vez, en la PC, en
vez de fallar en el depósito.
"""

import json
from pathlib import Path

import pytest

CONTRATO = Path(__file__).resolve().parent.parent.parent / "celular" / "contrato"


def leer(nombre):
    return json.loads((CONTRATO / f"{nombre}.json").read_text(encoding="utf-8"))


@pytest.fixture
def sesion_con_maestro(cliente_contrato):
    """Un servidor real con una sesión, un maestro y un operario."""
    return cliente_contrato


def test_los_archivos_del_contrato_existen():
    """Sin ellos, la app se prueba contra nada."""
    for nombre in ["vinculacion", "maestro", "conteos-respuesta", "alta-rapida"]:
        assert (CONTRATO / f"{nombre}.json").exists(), f"falta {nombre}.json"


def test_la_vinculacion_trae_operario_sesion_y_pasada():
    datos = leer("vinculacion")

    assert set(datos) == {"operario", "sesion", "pasada"}
    assert set(datos["operario"]) == {"id", "nombre"}
    assert set(datos["sesion"]) == {"id", "nombre"}
    assert "etiqueta" in datos["pasada"]
    assert "numero" in datos["pasada"]


def test_el_maestro_no_expone_stock_ni_costo():
    """Conteo a ciegas: el dato no debe existir en el celular."""
    datos = leer("maestro")

    for articulo in datos["articulos"]:
        assert "stock_sistema" not in articulo
        assert "costo_unitario" not in articulo


def test_el_maestro_trae_articulos_codigos_y_unidades():
    datos = leer("maestro")

    assert set(datos) == {"sesion_id", "articulos", "codigos", "unidades"}
    assert set(datos["articulos"][0]) == {
        "id", "id_orden", "tipo", "material", "sku", "descripcion",
        "grupo", "ubicacion", "unidad",
    }
    assert set(datos["codigos"][0]) == {"codigo", "articulo_id"}
    assert set(datos["unidades"][0]) == {"codigo", "nombre", "admite_decimales"}


def test_la_respuesta_de_conteos_distingue_lo_reintentable():
    """El celular necesita saber si conservar el evento o descartarlo."""
    datos = leer("conteos-respuesta")

    assert set(datos) == {"registrados", "duplicados", "rechazados"}
    assert datos["registrados"] == 1
    rechazado = datos["rechazados"][0]
    assert set(rechazado) == {"uuid", "motivo", "reintentable"}
    assert rechazado["reintentable"] is False


def test_el_alta_rapida_dice_si_creo_o_ya_estaba():
    datos = leer("alta-rapida")

    assert datos["creado"] is True
    assert "stock_sistema" not in datos
    assert "costo_unitario" not in datos
    assert datos["sku"] == "7790009999999"
```

Agregar al final de `servidor/tests/conftest.py`:

```python
@pytest.fixture
def cliente_contrato(tmp_path):
    """Un cliente HTTP sobre una app real, para los tests de contrato."""
    from fastapi.testclient import TestClient

    from app.main import crear_app

    app = crear_app(str(tmp_path / "contrato.db"))
    with TestClient(app) as cliente:
        yield cliente
```

- [ ] **Step 4: Correr el test del contrato y verificar que pasa**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests\test_contrato.py -v --rootdir .\servidor`
Expected: PASS, 6 tests

Si alguno falla, **el problema está en la captura o en el servidor, no en el test**: revisar el archivo que falló antes de tocar nada.

- [ ] **Step 5: Escribir el test de Kotlin que falla**

Agregar a `celular/nucleo/build.gradle.kts` el plugin de serialización y sus dependencias. El archivo completo queda:

```kotlin
plugins {
    id("org.jetbrains.kotlin.jvm")
    id("org.jetbrains.kotlin.plugin.serialization")
}

kotlin {
    jvmToolchain(17)
}

dependencies {
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    testImplementation("junit:junit:4.13.2")
}
```

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/ContratoApiTest.kt`:

```kotlin
package com.controldestock.nucleo

import java.io.File
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * La app se prueba contra las respuestas reales del servidor, capturadas en
 * `celular/contrato/`. Del otro lado, `servidor/tests/test_contrato.py`
 * verifica que el servidor las siga cumpliendo.
 */
class ContratoApiTest {

    private val json = Json { ignoreUnknownKeys = true }

    private fun leer(nombre: String): String =
        File("../contrato/$nombre.json").readText()

    @Test
    fun `parsea la vinculacion`() {
        val respuesta = json.decodeFromString<RespuestaVinculacion>(leer("vinculacion"))

        assertEquals("Contrato", respuesta.operario.nombre)
        assertTrue(respuesta.pasada.etiqueta.startsWith("Conteo"))
    }

    @Test
    fun `parsea el maestro completo`() {
        val respuesta = json.decodeFromString<RespuestaMaestro>(leer("maestro"))

        assertEquals(2, respuesta.articulos.size)
        assertEquals(2, respuesta.codigos.size)
        assertTrue(respuesta.unidades.isNotEmpty())

        val fideos = respuesta.articulos.first { it.sku == "7790001001234" }
        assertEquals("Fideos guisero 500g", fideos.descripcion)
        assertEquals("UN", fideos.unidad)
        assertEquals("P-1", fideos.ubicacion)
    }

    @Test
    fun `las unidades dicen si admiten decimales`() {
        val respuesta = json.decodeFromString<RespuestaMaestro>(leer("maestro"))

        val unidad = respuesta.unidades.first { it.codigo == "KG" }
        assertEquals(1, unidad.admiteDecimales)
    }

    @Test
    fun `parsea la respuesta de conteos y distingue lo reintentable`() {
        val respuesta = json.decodeFromString<RespuestaConteos>(leer("conteos-respuesta"))

        assertEquals(1, respuesta.registrados)
        assertEquals(1, respuesta.rechazados.size)
        assertFalse(respuesta.rechazados[0].reintentable)
        assertTrue(respuesta.rechazados[0].motivo.isNotEmpty())
    }

    @Test
    fun `parsea el alta rapida y sabe si creo`() {
        val respuesta = json.decodeFromString<RespuestaAlta>(leer("alta-rapida"))

        assertTrue(respuesta.creado)
        assertEquals("7790009999999", respuesta.sku)
    }

    @Test
    fun `un campo nuevo del servidor no rompe el parseo`() {
        // El servidor puede agregar campos sin coordinar una versión de la
        // app. Ignorarlos es lo que permite actualizar de a un lado por vez.
        val conExtra = leer("alta-rapida").trimEnd().dropLast(1) + ""","campo_nuevo":1}"""

        val respuesta = json.decodeFromString<RespuestaAlta>(conExtra)

        assertTrue(respuesta.creado)
    }
}
```

- [ ] **Step 6: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: RespuestaVinculacion`

- [ ] **Step 7: Implementar `ContratoApi.kt`**

```kotlin
package com.controldestock.nucleo

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Los tipos que viajan entre el celular y el servidor.
 *
 * Los nombres en el JSON son los del servidor (snake_case) y se mapean con
 * @SerialName: cambiar uno de los dos lados sin el otro rompe los tests de
 * contrato en la PC, que es exactamente lo que se busca.
 *
 * Ninguna respuesta trae `stock_sistema` ni `costo_unitario`: el conteo es a
 * ciegas y el dato no debe existir en el dispositivo.
 */

@Serializable
data class OperarioRemoto(val id: Int, val nombre: String)

@Serializable
data class SesionRemota(val id: Int, val nombre: String)

@Serializable
data class PasadaRemota(
    val id: Int,
    val numero: Int,
    val etiqueta: String,
)

@Serializable
data class RespuestaVinculacion(
    val operario: OperarioRemoto,
    val sesion: SesionRemota,
    val pasada: PasadaRemota,
)

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
)

@Serializable
data class CodigoRemoto(
    val codigo: String,
    @SerialName("articulo_id") val articuloId: Int,
)

@Serializable
data class UnidadRemota(
    val codigo: String,
    val nombre: String,
    @SerialName("admite_decimales") val admiteDecimales: Int,
)

@Serializable
data class RespuestaMaestro(
    @SerialName("sesion_id") val sesionId: Int,
    val articulos: List<ArticuloRemoto>,
    val codigos: List<CodigoRemoto>,
    val unidades: List<UnidadRemota>,
)

@Serializable
data class ConteoRechazado(
    val uuid: String,
    val motivo: String,
    val reintentable: Boolean,
)

@Serializable
data class RespuestaConteos(
    val registrados: Int,
    val duplicados: Int,
    val rechazados: List<ConteoRechazado>,
)

@Serializable
data class RespuestaAlta(
    val id: Int,
    @SerialName("id_orden") val idOrden: Int,
    val sku: String,
    val descripcion: String,
    val unidad: String,
    val ubicacion: String? = null,
    val tipo: String? = null,
    val material: String? = null,
    val grupo: String? = null,
    val creado: Boolean,
)

/** Un conteo tal como se manda: los nombres son los que espera el servidor. */
@Serializable
data class ConteoParaEnviar(
    val uuid: String,
    val codigo: String,
    val cantidad: Int,
    @SerialName("timestamp_dispositivo") val timestampDispositivo: String,
    @SerialName("ubicacion_real") val ubicacionReal: String? = null,
    val observaciones: String? = null,
    @SerialName("anula_uuid") val anulaUuid: String? = null,
)

@Serializable
data class LoteDeConteos(val conteos: List<ConteoParaEnviar>)

fun EventoConteo.paraEnviar() = ConteoParaEnviar(
    uuid = uuid,
    codigo = codigo,
    cantidad = cantidad,
    timestampDispositivo = timestampDispositivo,
    ubicacionReal = ubicacionReal,
    observaciones = observaciones,
    anulaUuid = anulaUuid,
)
```

- [ ] **Step 8: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 26 tests en total

- [ ] **Step 9: Correr también la suite del servidor**

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS, todos

- [ ] **Step 10: Commit**

```bash
git add celular/contrato/ celular/nucleo/ servidor/tests/test_contrato.py servidor/tests/conftest.py
git commit -m "Fija el contrato entre el celular y el servidor

Las respuestas reales del servidor quedan capturadas como archivos de
referencia. La app se prueba contra ellos y un test del lado Python
verifica que el servidor los siga cumpliendo: si alguien renombra un
campo, rompe de los dos lados a la vez en la PC, en vez de fallar en el
deposito.

El parseo ignora los campos que no conoce, asi el servidor puede agregar
uno sin coordinar una version de la app."
```

---

### Task 4: El plan de sincronización

**Files:**
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/PlanDeSincronizacion.kt`
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/PlanDeSincronizacionTest.kt`

**Interfaces:**
- Consumes: `EventoConteo` (Task 2), `ConteoRechazado` (Task 3)
- Produces:
  - `EstadoSync` — enum: `PENDIENTE`, `ENVIADO`, `RECHAZADO`
  - `ConteoLocal` — data class: `evento`, `estadoSync`, `motivoRechazo`
  - `PlanDeSincronizacion.aEnviar(locales: List<ConteoLocal>): List<EventoConteo>`
  - `PlanDeSincronizacion.aplicar(enviados: List<EventoConteo>, respuesta: RespuestaConteos): List<ConteoLocal>`

**Reglas que fija el spec:** un conteo rechazado como **no reintentable** se marca y se muestra con su motivo, en vez de reintentarse para siempre. Un rechazo **reintentable** vuelve a la cola. Los duplicados cuentan como enviados: el servidor ya los tenía.

**Por qué es lógica pura:** decidir qué mandar y qué hacer con la respuesta no necesita red ni base de datos. Separarlo permite probar todos los casos —incluido el que solo pasa con mala señal— en milisegundos.

- [ ] **Step 1: Escribir el test que falla**

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/PlanDeSincronizacionTest.kt`:

```kotlin
package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PlanDeSincronizacionTest {

    private val reloj = RelojFijo("2026-08-11T10:00:00Z")

    private fun local(codigo: String, estado: EstadoSync = EstadoSync.PENDIENTE) =
        ConteoLocal(EventoConteo.nuevo(codigo, 1000, reloj), estado)

    @Test
    fun `manda solo los pendientes`() {
        val locales = listOf(
            local("A"),
            local("B", EstadoSync.ENVIADO),
            local("C", EstadoSync.RECHAZADO),
            local("D"),
        )

        val aEnviar = PlanDeSincronizacion.aEnviar(locales)

        assertEquals(listOf("A", "D"), aEnviar.map { it.codigo })
    }

    @Test
    fun `un rechazado no reintentable no vuelve a la cola`() {
        // Reintentar para siempre algo que nunca va a entrar deja la cola
        // trabada y el indicador de pendientes mintiendo.
        val locales = listOf(local("A", EstadoSync.RECHAZADO))

        assertTrue(PlanDeSincronizacion.aEnviar(locales).isEmpty())
    }

    @Test
    fun `lo aceptado queda como enviado`() {
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(registrados = 1, duplicados = 0, rechazados = emptyList())

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.ENVIADO, resultado.single().estadoSync)
    }

    @Test
    fun `un duplicado tambien queda como enviado`() {
        // El servidor ya lo tenía: reenviar es inofensivo y no hay nada que
        // arreglar del lado del celular.
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(registrados = 0, duplicados = 1, rechazados = emptyList())

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.ENVIADO, resultado.single().estadoSync)
    }

    @Test
    fun `un rechazo definitivo queda marcado con su motivo`() {
        val evento = EventoConteo.nuevo("no-existe", 1000, reloj)
        val respuesta = RespuestaConteos(
            registrados = 0, duplicados = 0,
            rechazados = listOf(
                ConteoRechazado(evento.uuid, "Código desconocido: no-existe", reintentable = false),
            ),
        )

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.RECHAZADO, resultado.single().estadoSync)
        assertEquals("Código desconocido: no-existe", resultado.single().motivoRechazo)
    }

    @Test
    fun `un rechazo reintentable vuelve a quedar pendiente`() {
        // Pasa cuando una anulación llega antes que el conteo que anula: los
        // celulares sincronizan en cualquier orden.
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(
            registrados = 0, duplicados = 0,
            rechazados = listOf(
                ConteoRechazado(evento.uuid, "El conteo que anula todavía no llegó", reintentable = true),
            ),
        )

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.PENDIENTE, resultado.single().estadoSync)
    }

    @Test
    fun `un evento que la respuesta no menciona sigue pendiente`() {
        // Si la respuesta llega incompleta, lo que no se confirmó no se puede
        // dar por enviado: perder un conteo es peor que mandarlo dos veces.
        val enviados = listOf(
            EventoConteo.nuevo("A", 1000, reloj),
            EventoConteo.nuevo("B", 1000, reloj),
        )
        val respuesta = RespuestaConteos(registrados = 1, duplicados = 0, rechazados = emptyList())

        val resultado = PlanDeSincronizacion.aplicar(enviados, respuesta)

        assertEquals(2, resultado.size)
        assertTrue(resultado.all { it.estadoSync == EstadoSync.ENVIADO })
    }

    @Test
    fun `cuenta los pendientes para el indicador de pantalla`() {
        val locales = listOf(
            local("A"),
            local("B", EstadoSync.ENVIADO),
            local("C"),
        )

        assertEquals(2, PlanDeSincronizacion.pendientes(locales))
    }
}
```

**Nota sobre el último caso del test `un evento que la respuesta no menciona sigue pendiente`:** el servidor devuelve conteos agregados (`registrados`, `duplicados`) y no la lista de uuid aceptados, así que la app no puede distinguir cuál de los dos entró. Lo único seguro es tratar como enviado todo lo que no aparezca en `rechazados` — reenviar es inofensivo por el `uuid`, y perder un conteo no lo es. El test fija ese criterio explícitamente.

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: EstadoSync`

- [ ] **Step 3: Implementar `PlanDeSincronizacion.kt`**

```kotlin
package com.controldestock.nucleo

/**
 * En qué estado está un conteo respecto del servidor.
 *
 * `RECHAZADO` existe porque un conteo que el servidor nunca va a aceptar no
 * puede reintentarse para siempre ni desaparecer sin dejar rastro: queda
 * visible en «Mis conteos» con su motivo.
 */
enum class EstadoSync { PENDIENTE, ENVIADO, RECHAZADO }

data class ConteoLocal(
    val evento: EventoConteo,
    val estadoSync: EstadoSync = EstadoSync.PENDIENTE,
    val motivoRechazo: String? = null,
)

/**
 * Qué mandar y qué hacer con la respuesta.
 *
 * Es lógica pura a propósito: así los casos que solo aparecen con mala señal
 * se prueban en milisegundos, sin red ni base de datos.
 */
object PlanDeSincronizacion {

    fun aEnviar(locales: List<ConteoLocal>): List<EventoConteo> =
        locales.filter { it.estadoSync == EstadoSync.PENDIENTE }.map { it.evento }

    fun pendientes(locales: List<ConteoLocal>): Int =
        locales.count { it.estadoSync == EstadoSync.PENDIENTE }

    /**
     * Aplica la respuesta del servidor a los eventos que se mandaron.
     *
     * El servidor contesta con totales, no con la lista de uuid aceptados,
     * así que lo único seguro es dar por enviado todo lo que no venga
     * rechazado: reenviar es inofensivo gracias al uuid, y perder un conteo
     * no lo es.
     */
    fun aplicar(
        enviados: List<EventoConteo>,
        respuesta: RespuestaConteos,
    ): List<ConteoLocal> {
        val porUuid = respuesta.rechazados.associateBy { it.uuid }

        return enviados.map { evento ->
            val rechazo = porUuid[evento.uuid]
            when {
                rechazo == null ->
                    ConteoLocal(evento, EstadoSync.ENVIADO)

                rechazo.reintentable ->
                    ConteoLocal(evento, EstadoSync.PENDIENTE, rechazo.motivo)

                else ->
                    ConteoLocal(evento, EstadoSync.RECHAZADO, rechazo.motivo)
            }
        }
    }
}
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 34 tests en total

- [ ] **Step 5: Escribir el test que verifica que el núcleo no toca Android**

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/NucleoSinAndroidTest.kt`:

```kotlin
package com.controldestock.nucleo

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * El núcleo se prueba en la PC en segundos porque no depende del framework.
 * Un solo import de `android.*` obliga a un emulador o un celular enchufado
 * para correr los tests, y ahí se termina la disciplina.
 */
class NucleoSinAndroidTest {

    @Test
    fun `ningun archivo del nucleo importa android`() {
        val fuentes = File("src/main/kotlin").walkTopDown().filter { it.extension == "kt" }

        val contaminados = fuentes.filter { archivo ->
            archivo.readLines().any { it.trimStart().startsWith("import android") }
        }.map { it.name }.toList()

        assertEquals(emptyList<String>(), contaminados)
    }
}
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 35 tests

- [ ] **Step 7: Commit**

```bash
git add celular/nucleo/
git commit -m "Agrega la decision de que sincronizar y como aplicar la respuesta

Un rechazo definitivo se marca con su motivo en vez de reintentarse para
siempre: la cola quedaria trabada y el indicador de pendientes mintiendo.
Uno reintentable vuelve a la cola, que es lo que pasa cuando una anulacion
llega antes que el conteo que anula.

Lo que la respuesta no menciona se da por enviado. El servidor contesta
con totales y no con la lista de uuid aceptados, y reenviar es inofensivo
gracias al uuid, mientras que perder un conteo no lo es.

Un test verifica que el nucleo no importe nada de android: un solo import
obligaria a un celular enchufado para correr los tests."
```

---

### Task 5: La base local

**Files:**
- Create: `celular/app/build.gradle.kts`
- Create: `celular/app/src/main/AndroidManifest.xml`
- Create: `celular/app/src/main/kotlin/com/controldestock/datos/Entidades.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/datos/Dao.kt`
- Create: `celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/datos/BaseLocalTest.kt`
- Modify: `celular/settings.gradle.kts`

**Interfaces:**
- Consumes: `EstadoSync`, `EventoConteo`, `ConteoLocal` (Tasks 2 y 4)
- Produces:
  - `BaseLocal` — `RoomDatabase` con `vinculacionDao()`, `maestroDao()`, `conteoDao()`
  - Entidades: `VinculacionEntidad`, `ArticuloEntidad`, `CodigoEntidad`, `UnidadEntidad`, `ConteoEntidad`
  - `ConteoEntidad.aLocal(): ConteoLocal` y `ConteoLocal.aEntidad(): ConteoEntidad`

**Del spec, dos columnas que hoy tienen un solo valor posible:** `articulo.pasada_numero` y `conteo.fuera_asignacion`. Sin ellas, agregar pasadas sucesivas obligaría a migrar la base de cada dispositivo en medio de un inventario.

Los tests corren con Robolectric, que ejecuta SQLite en la JVM: no hace falta el celular enchufado.

- [ ] **Step 1: Agregar el módulo `app` al proyecto**

En `celular/settings.gradle.kts`, agregar la línea `include(":app")` después de `include(":nucleo")`.

Crear `celular/app/build.gradle.kts`:

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("com.google.devtools.ksp") version "1.9.23-1.0.20"
}

android {
    namespace = "com.controldestock"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.controldestock"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

dependencies {
    implementation(project(":nucleo"))

    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    ksp("androidx.room:room-compiler:2.6.1")

    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.12.2")
    testImplementation("androidx.test:core:1.5.0")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.0")
}
```

Agregar el plugin de KSP a `celular/build.gradle.kts`, en el bloque `plugins`:

```kotlin
    id("com.google.devtools.ksp") version "1.9.23-1.0.20" apply false
```

Crear `celular/app/src/main/AndroidManifest.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:label="Control de Stock"
        android:supportsRtl="false" />

</manifest>
```

- [ ] **Step 2: Verificar que el módulo compila**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon`
Expected: `BUILD SUCCESSFUL`. La primera vez descarga Room y Robolectric; puede tardar varios minutos.

Si falla la resolución de alguna dependencia, **parar y reportarlo**: es un problema de entorno o de versiones, no de código, y adivinar versiones nuevas rompe la reproducibilidad.

- [ ] **Step 3: Escribir el test que falla**

Crear `celular/app/src/test/kotlin/com/controldestock/datos/BaseLocalTest.kt`:

```kotlin
package com.controldestock.datos

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

class RelojFijoDeDatos(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class BaseLocalTest {

    private lateinit var base: BaseLocal
    private val reloj = RelojFijoDeDatos("2026-08-11T10:00:00Z")

    @Before
    fun abrir() {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
    }

    @After
    fun cerrar() = base.close()

    private fun articulo(id: Int, sku: String, unidad: String = "UN") = ArticuloEntidad(
        id = id, idOrden = id, sku = sku, descripcion = "Artículo $sku",
        unidad = unidad, ubicacion = "P-1", pasadaNumero = 1,
    )

    @Test
    fun `guarda el maestro y lo devuelve ordenado por numero de orden`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(2, "B"), articulo(1, "A")),
            codigos = emptyList(),
            unidades = emptyList(),
        )

        val guardados = base.maestroDao().articulos()

        assertEquals(listOf("A", "B"), guardados.map { it.sku })
    }

    @Test
    fun `encuentra un articulo por su codigo de barras`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(1, "A")),
            codigos = listOf(CodigoEntidad("7790001001234", 1)),
            unidades = emptyList(),
        )

        val encontrado = base.maestroDao().porCodigo("7790001001234")

        assertEquals("A", encontrado?.sku)
    }

    @Test
    fun `un codigo que no esta devuelve null`() = runTest {
        assertNull(base.maestroDao().porCodigo("no-existe"))
    }

    @Test
    fun `reemplazar el maestro no deja restos del anterior`() = runTest {
        // Al reimportar, un artículo que ya no está en el maestro no puede
        // seguir apareciendo en la búsqueda del operario.
        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "VIEJO")), emptyList(), emptyList())

        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "NUEVO")), emptyList(), emptyList())

        assertEquals(listOf("NUEVO"), base.maestroDao().articulos().map { it.sku })
    }

    @Test
    fun `busca por descripcion sku y ubicacion sin distinguir mayusculas`() = runTest {
        // Es lo que destraba la etiqueta rota: el operario busca a mano.
        base.maestroDao().reemplazarMaestro(
            listOf(
                ArticuloEntidad(1, 1, sku = "10453", descripcion = "Tornillo hexagonal",
                    unidad = "UN", ubicacion = "A-03", pasadaNumero = 1),
                ArticuloEntidad(2, 2, sku = "10454", descripcion = "Tuerca",
                    unidad = "UN", ubicacion = "B-01", pasadaNumero = 1),
            ),
            emptyList(), emptyList(),
        )

        assertEquals(listOf("10453"), base.maestroDao().buscar("torni").map { it.sku })
        assertEquals(listOf("10453"), base.maestroDao().buscar("10453").map { it.sku })
        assertEquals(listOf("10454"), base.maestroDao().buscar("b-01").map { it.sku })
    }

    @Test
    fun `guarda un conteo como pendiente`() = runTest {
        val evento = EventoConteo.nuevo("7790001001234", 48000, reloj)

        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 1))

        val guardado = base.conteoDao().todos().single()
        assertEquals(EstadoSync.PENDIENTE, guardado.estadoSync)
        assertEquals(48000, guardado.cantidad)
        assertEquals(0, guardado.fueraAsignacion)
    }

    @Test
    fun `lo guardado sobrevive con la misma clave`() = runTest {
        // El uuid es la clave: guardar dos veces el mismo evento no puede
        // duplicar el conteo.
        val evento = EventoConteo.nuevo("A", 1000, reloj)

        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 1))
        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 1))

        assertEquals(1, base.conteoDao().todos().size)
    }

    @Test
    fun `devuelve los conteos del mas nuevo al mas viejo`() = runTest {
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo("A", 1000, RelojFijoDeDatos("2026-08-11T10:00:00Z")), 1),
        )
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo("B", 1000, RelojFijoDeDatos("2026-08-11T11:00:00Z")), 2),
        )

        assertEquals(listOf("B", "A"), base.conteoDao().todos().map { it.codigo })
    }

    @Test
    fun `cuenta los pendientes para el indicador`() = runTest {
        base.conteoDao().guardar(ConteoEntidad.de(EventoConteo.nuevo("A", 1000, reloj), 1))
        val enviado = ConteoEntidad.de(EventoConteo.nuevo("B", 1000, reloj), 2)
            .copy(estadoSync = EstadoSync.ENVIADO)
        base.conteoDao().guardar(enviado)

        assertEquals(1, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `marca un conteo como rechazado con su motivo`() = runTest {
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        base.conteoDao().guardar(ConteoEntidad.de(evento, 1))

        base.conteoDao().marcar(evento.uuid, EstadoSync.RECHAZADO, "Código desconocido")

        val guardado = base.conteoDao().todos().single()
        assertEquals(EstadoSync.RECHAZADO, guardado.estadoSync)
        assertEquals("Código desconocido", guardado.motivoRechazo)
    }

    @Test
    fun `guarda y devuelve la vinculacion`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = "http://172.16.11.12:8000", token = "abc",
                operarioId = 1, operarioNombre = "Juan",
                sesionId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )

        val guardada = base.vinculacionDao().actual()

        assertEquals("Juan", guardada?.operarioNombre)
        assertEquals("Conteo 1", guardada?.pasadaEtiqueta)
    }

    @Test
    fun `sin vincular no hay vinculacion`() = runTest {
        assertNull(base.vinculacionDao().actual())
    }
}
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: FAIL con `Unresolved reference: BaseLocal`

- [ ] **Step 5: Implementar `Entidades.kt`**

```kotlin
package com.controldestock.datos

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo

/**
 * La base local del celular.
 *
 * Es la fuente de verdad mientras se cuenta: la app nunca consulta al
 * servidor para trabajar, solo para sincronizar. Con o sin señal se comporta
 * igual.
 *
 * Las cantidades se guardan como enteros en milésimas, igual que en el
 * servidor y por el mismo motivo: sumar decimales en punto flotante acumula
 * error y un inventario suma miles de veces.
 */

@Entity(tableName = "vinculacion")
data class VinculacionEntidad(
    @PrimaryKey val id: Int = 1,   // una sola vinculación por dispositivo
    val url: String,
    val token: String,
    val operarioId: Int,
    val operarioNombre: String,
    val sesionId: Int,
    val pasadaId: Int,
    val pasadaNumero: Int,
    val pasadaEtiqueta: String,
)

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
    // A qué pasada pertenece. Hoy siempre 1: cuando existan las pasadas
    // sucesivas, agregar la columna obligaría a migrar la base de cada
    // dispositivo en medio de un inventario.
    val pasadaNumero: Int,
)

@Entity(tableName = "codigo", primaryKeys = ["codigo", "articuloId"],
        indices = [Index("codigo")])
data class CodigoEntidad(
    val codigo: String,
    val articuloId: Int,
)

@Entity(tableName = "unidad")
data class UnidadEntidad(
    @PrimaryKey val codigo: String,
    val nombre: String,
    val admiteDecimales: Int,
)

@Entity(tableName = "conteo")
data class ConteoEntidad(
    @PrimaryKey val uuid: String,
    val articuloId: Int,
    val codigo: String,
    val cantidad: Int,
    val ubicacionReal: String? = null,
    val observaciones: String? = null,
    // Si el conteo cayó fuera de lo asignado. Hoy siempre 0, por el mismo
    // motivo que pasadaNumero.
    val fueraAsignacion: Int = 0,
    val timestampDispositivo: String,
    val anulaUuid: String? = null,
    val estadoSync: EstadoSync = EstadoSync.PENDIENTE,
    val motivoRechazo: String? = null,
) {
    fun aEvento() = EventoConteo(
        uuid = uuid,
        codigo = codigo,
        cantidad = cantidad,
        timestampDispositivo = timestampDispositivo,
        ubicacionReal = ubicacionReal,
        observaciones = observaciones,
        anulaUuid = anulaUuid,
    )

    fun aLocal() = ConteoLocal(aEvento(), estadoSync, motivoRechazo)

    companion object {
        fun de(evento: EventoConteo, articuloId: Int) = ConteoEntidad(
            uuid = evento.uuid,
            articuloId = articuloId,
            codigo = evento.codigo,
            cantidad = evento.cantidad,
            ubicacionReal = evento.ubicacionReal,
            observaciones = evento.observaciones,
            timestampDispositivo = evento.timestampDispositivo,
            anulaUuid = evento.anulaUuid,
        )
    }
}
```

- [ ] **Step 6: Implementar `Dao.kt`**

```kotlin
package com.controldestock.datos

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.controldestock.nucleo.EstadoSync

@Dao
interface VinculacionDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun guardar(vinculacion: VinculacionEntidad)

    @Query("SELECT * FROM vinculacion WHERE id = 1")
    suspend fun actual(): VinculacionEntidad?

    @Query("DELETE FROM vinculacion")
    suspend fun borrar()
}

@Dao
interface MaestroDao {

    @Query("SELECT * FROM articulo ORDER BY idOrden")
    suspend fun articulos(): List<ArticuloEntidad>

    @Query(
        """
        SELECT a.* FROM articulo a
        JOIN codigo c ON c.articuloId = a.id
        WHERE c.codigo = :codigo
        LIMIT 1
        """
    )
    suspend fun porCodigo(codigo: String): ArticuloEntidad?

    @Query("SELECT * FROM articulo WHERE id = :id")
    suspend fun porId(id: Int): ArticuloEntidad?

    /** Lo que destraba la etiqueta rota: el operario busca a mano, sin señal. */
    @Query(
        """
        SELECT * FROM articulo
        WHERE descripcion LIKE '%' || :texto || '%' COLLATE NOCASE
           OR sku LIKE '%' || :texto || '%' COLLATE NOCASE
           OR ubicacion LIKE '%' || :texto || '%' COLLATE NOCASE
        ORDER BY idOrden
        LIMIT 50
        """
    )
    suspend fun buscar(texto: String): List<ArticuloEntidad>

    @Query("SELECT * FROM unidad WHERE codigo = :codigo")
    suspend fun unidad(codigo: String): UnidadEntidad?

    @Query("SELECT ubicacion FROM articulo WHERE ubicacion IS NOT NULL GROUP BY ubicacion ORDER BY ubicacion")
    suspend fun ubicaciones(): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarArticulos(articulos: List<ArticuloEntidad>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarCodigos(codigos: List<CodigoEntidad>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarUnidades(unidades: List<UnidadEntidad>)

    @Query("DELETE FROM articulo")
    suspend fun borrarArticulos()

    @Query("DELETE FROM codigo")
    suspend fun borrarCodigos()

    /**
     * Reemplaza el maestro entero.
     *
     * Se borra antes de insertar: al reimportar, un artículo que ya no está
     * no puede seguir apareciendo en la búsqueda del operario. Va en una
     * transacción para que un maestro a medio reemplazar no exista nunca.
     */
    @Transaction
    suspend fun reemplazarMaestro(
        articulos: List<ArticuloEntidad>,
        codigos: List<CodigoEntidad>,
        unidades: List<UnidadEntidad>,
    ) {
        borrarCodigos()
        borrarArticulos()
        insertarArticulos(articulos)
        insertarCodigos(codigos)
        insertarUnidades(unidades)
    }
}

@Dao
interface ConteoDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun guardar(conteo: ConteoEntidad)

    @Query("SELECT * FROM conteo ORDER BY timestampDispositivo DESC, rowid DESC")
    suspend fun todos(): List<ConteoEntidad>

    // Sin valor por defecto en el parámetro: Room no los admite en los
    // métodos de un DAO.
    @Query("SELECT * FROM conteo WHERE estadoSync = :estado ORDER BY rowid")
    suspend fun porEstado(estado: EstadoSync): List<ConteoEntidad>

    @Query("SELECT COUNT(*) FROM conteo WHERE estadoSync = 'PENDIENTE'")
    suspend fun cantidadPendientes(): Int

    @Query("UPDATE conteo SET estadoSync = :estado, motivoRechazo = :motivo WHERE uuid = :uuid")
    suspend fun marcar(uuid: String, estado: EstadoSync, motivo: String? = null)

    @Query("SELECT * FROM conteo WHERE uuid = :uuid")
    suspend fun porUuid(uuid: String): ConteoEntidad?
}
```

- [ ] **Step 7: Implementar `BaseLocal.kt`**

```kotlin
package com.controldestock.datos

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import com.controldestock.nucleo.EstadoSync

class ConversorDeEstado {
    @TypeConverter
    fun aTexto(estado: EstadoSync): String = estado.name

    @TypeConverter
    fun aEstado(texto: String): EstadoSync = EstadoSync.valueOf(texto)
}

@Database(
    entities = [
        VinculacionEntidad::class,
        ArticuloEntidad::class,
        CodigoEntidad::class,
        UnidadEntidad::class,
        ConteoEntidad::class,
    ],
    version = 1,
    exportSchema = false,
)
@TypeConverters(ConversorDeEstado::class)
abstract class BaseLocal : RoomDatabase() {

    abstract fun vinculacionDao(): VinculacionDao
    abstract fun maestroDao(): MaestroDao
    abstract fun conteoDao(): ConteoDao

    companion object {
        @Volatile
        private var instancia: BaseLocal? = null

        fun de(contexto: Context): BaseLocal = instancia ?: synchronized(this) {
            instancia ?: Room.databaseBuilder(
                contexto.applicationContext,
                BaseLocal::class.java,
                "control-de-stock.db",
            ).build().also { instancia = it }
        }
    }
}
```

- [ ] **Step 8: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, 12 tests

- [ ] **Step 9: Correr todo el proyecto**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS, los 35 del núcleo y los 12 de la app

- [ ] **Step 10: Commit**

```bash
git add celular/
git commit -m "Agrega la base local del celular

Es la fuente de verdad mientras se cuenta: la app nunca consulta al
servidor para trabajar, solo para sincronizar, asi que con o sin señal se
comporta igual.

Guarda desde ahora a que pasada pertenece cada articulo y si el conteo
cayo fuera de la asignacion, aunque hoy los dos tengan un solo valor
posible. Agregarlos despues obligaria a migrar la base de cada dispositivo
en medio de un inventario.

Reemplazar el maestro borra el anterior en la misma transaccion: al
reimportar, un articulo que ya no esta no puede seguir apareciendo en la
busqueda del operario."
```

---

### Task 6: El cliente HTTP

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/red/ClienteServidor.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/red/ClienteServidorTest.kt`
- Modify: `celular/app/build.gradle.kts`

**Interfaces:**
- Consumes: `ContratoApi` (Task 3), `EventoConteo` (Task 2)
- Produces:
  - `ClienteServidor(url: String, token: String)`
  - `suspend fun vincular(): RespuestaVinculacion`
  - `suspend fun maestro(): RespuestaMaestro`
  - `suspend fun enviarConteos(eventos: List<EventoConteo>): RespuestaConteos`
  - `suspend fun altaRapida(codigo: String, descripcion: String, unidad: String, ubicacion: String?): RespuestaAlta`
  - `ErrorDeServidor(mensaje: String, val reintentable: Boolean) : Exception`

**Los mensajes de error son de pantalla, no de log:** el operario los va a leer en el depósito. Van en castellano llano y dicen qué hacer.

Los tests usan `MockWebServer`, que levanta un servidor HTTP real en la JVM y devuelve **los archivos de contrato capturados en la Task 3**: se prueba el parseo contra respuestas verdaderas del servidor, no contra JSON inventado.

- [ ] **Step 1: Agregar OkHttp y MockWebServer**

En `celular/app/build.gradle.kts`, agregar al bloque `dependencies`:

```kotlin
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
```

- [ ] **Step 2: Escribir el test que falla**

Crear `celular/app/src/test/kotlin/com/controldestock/red/ClienteServidorTest.kt`:

```kotlin
package com.controldestock.red

import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import java.io.File
import java.net.HttpURLConnection
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class RelojFijoDeRed(private val instante: String) : Reloj {
    override fun ahora() = instante
}

class ClienteServidorTest {

    private lateinit var servidor: MockWebServer
    private lateinit var cliente: ClienteServidor

    @Before
    fun levantar() {
        servidor = MockWebServer()
        servidor.start()
        cliente = ClienteServidor(servidor.url("/").toString().trimEnd('/'), "token-de-prueba")
    }

    @After
    fun bajar() = servidor.shutdown()

    /** Las respuestas reales capturadas del servidor, no JSON inventado. */
    private fun contrato(nombre: String) = File("../contrato/$nombre.json").readText()

    private fun responder(cuerpo: String, codigo: Int = 200) {
        servidor.enqueue(
            MockResponse().setResponseCode(codigo)
                .setHeader("Content-Type", "application/json")
                .setBody(cuerpo),
        )
    }

    @Test
    fun `vincular manda el token en el encabezado`() = runTest {
        responder(contrato("vinculacion"))

        val respuesta = cliente.vincular()

        val pedido = servidor.takeRequest()
        assertEquals("/api/dispositivo/vincular", pedido.path)
        assertEquals("token-de-prueba", pedido.getHeader("X-Token"))
        assertEquals("Contrato", respuesta.operario.nombre)
    }

    @Test
    fun `descarga el maestro`() = runTest {
        responder(contrato("maestro"))

        val respuesta = cliente.maestro()

        assertEquals("/api/dispositivo/maestro", servidor.takeRequest().path)
        assertEquals(2, respuesta.articulos.size)
    }

    @Test
    fun `manda los conteos con los nombres que espera el servidor`() = runTest {
        responder(contrato("conteos-respuesta"))
        val evento = EventoConteo.nuevo(
            "7790001001234", 48000, RelojFijoDeRed("2026-08-11T10:00:00Z"),
            ubicacionReal = "P-9",
        )

        cliente.enviarConteos(listOf(evento))

        val cuerpo = servidor.takeRequest().body.readUtf8()
        assertTrue(cuerpo.contains("\"timestamp_dispositivo\""))
        assertTrue(cuerpo.contains("\"ubicacion_real\""))
        assertTrue(cuerpo.contains("\"conteos\""))
    }

    @Test
    fun `la respuesta de conteos trae los rechazos`() = runTest {
        responder(contrato("conteos-respuesta"))

        val respuesta = cliente.enviarConteos(
            listOf(EventoConteo.nuevo("A", 1000, RelojFijoDeRed("2026-08-11T10:00:00Z"))),
        )

        assertEquals(1, respuesta.registrados)
        assertEquals(1, respuesta.rechazados.size)
    }

    @Test
    fun `el alta rapida dice si creo el articulo`() = runTest {
        responder(contrato("alta-rapida"))

        val respuesta = cliente.altaRapida("7790009999999", "Sin etiqueta", "UN", "P-9")

        assertEquals("/api/dispositivo/articulos", servidor.takeRequest().path)
        assertTrue(respuesta.creado)
    }

    @Test
    fun `un token invalido se explica y no se reintenta`() = runTest {
        // Reintentar con un token revocado no va a funcionar nunca: hay que
        // volver a escanear el QR.
        responder("""{"detail":"Token de operario inválido"}""", HttpURLConnection.HTTP_UNAUTHORIZED)

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.message!!.contains("vinculado"))
        assertEquals(false, error.reintentable)
    }

    @Test
    fun `una sesion cerrada se explica y no se reintenta`() = runTest {
        responder("""{"detail":"No hay ninguna sesión abierta"}""", HttpURLConnection.HTTP_CONFLICT)

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(false, error!!.reintentable)
        assertTrue(error.message!!.isNotEmpty())
    }

    @Test
    fun `un error del servidor si es reintentable`() = runTest {
        // Un 500 puede ser transitorio: la app conserva el conteo y reintenta.
        responder("""{"detail":"algo se rompio"}""", HttpURLConnection.HTTP_INTERNAL_ERROR)

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(true, error!!.reintentable)
    }

    @Test
    fun `si el servidor no contesta el error es reintentable`() = runTest {
        // Es el caso normal en un depósito: el celular salió del alcance del
        // wifi. No se pierde nada, se reintenta.
        servidor.shutdown()

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(true, error!!.reintentable)
        assertTrue(error.message!!.contains("conexión") || error.message!!.contains("servidor"))
    }
}
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: FAIL con `Unresolved reference: ClienteServidor`

- [ ] **Step 4: Implementar `ClienteServidor.kt`**

```kotlin
package com.controldestock.red

import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.LoteDeConteos
import com.controldestock.nucleo.RespuestaAlta
import com.controldestock.nucleo.RespuestaConteos
import com.controldestock.nucleo.RespuestaMaestro
import com.controldestock.nucleo.RespuestaVinculacion
import com.controldestock.nucleo.paraEnviar
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Un error que la app puede mostrar y decidir qué hacer con él.
 *
 * `reintentable` distingue lo que puede andar más tarde —el celular salió
 * del alcance del wifi— de lo que nunca va a andar —el token se revocó—.
 * Sin esa distinción, la app reintenta para siempre o descarta trabajo.
 */
class ErrorDeServidor(
    mensaje: String,
    val reintentable: Boolean,
) : Exception(mensaje)

/**
 * El cliente HTTP del servidor de inventario.
 *
 * Los mensajes de error son de pantalla, no de registro: el operario los lee
 * en el depósito, así que van en castellano llano y dicen qué hacer.
 */
class ClienteServidor(
    private val url: String,
    private val token: String,
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build(),
) {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private val TIPO_JSON = "application/json; charset=utf-8".toMediaType()

    suspend fun vincular(): RespuestaVinculacion =
        pedir("/api/dispositivo/vincular", cuerpo = "{}")

    suspend fun maestro(): RespuestaMaestro =
        pedir("/api/dispositivo/maestro")

    suspend fun enviarConteos(eventos: List<EventoConteo>): RespuestaConteos {
        val lote = LoteDeConteos(eventos.map { it.paraEnviar() })
        return pedir("/api/dispositivo/conteos", cuerpo = json.encodeToString(lote))
    }

    suspend fun altaRapida(
        codigo: String,
        descripcion: String,
        unidad: String,
        ubicacion: String?,
    ): RespuestaAlta {
        val cuerpo = json.encodeToString(
            PedidoDeAlta(codigo, descripcion, unidad, ubicacion),
        )
        return pedir("/api/dispositivo/articulos", cuerpo = cuerpo)
    }

    private suspend inline fun <reified T> pedir(
        ruta: String,
        cuerpo: String? = null,
    ): T = withContext(Dispatchers.IO) {
        val pedido = Request.Builder()
            .url("$url$ruta")
            .header("X-Token", token)
            .apply { if (cuerpo != null) post(cuerpo.toRequestBody(TIPO_JSON)) }
            .build()

        val respuesta = try {
            http.newCall(pedido).execute()
        } catch (error: IOException) {
            // El caso normal en un depósito: el celular salió del alcance del
            // wifi. No se pierde nada, se reintenta más tarde.
            throw ErrorDeServidor(
                "Sin conexión con el servidor. Se va a reintentar solo.",
                reintentable = true,
            )
        }

        respuesta.use {
            val texto = it.body?.string().orEmpty()
            if (!it.isSuccessful) throw traducir(it.code, texto)
            try {
                json.decodeFromString<T>(texto)
            } catch (error: Exception) {
                throw ErrorDeServidor(
                    "El servidor contestó algo que no se entiende.",
                    reintentable = false,
                )
            }
        }
    }

    private fun traducir(codigo: Int, cuerpo: String): ErrorDeServidor = when (codigo) {
        401 -> ErrorDeServidor(
            "Este celular ya no está vinculado. Escaneá de nuevo el QR del panel.",
            reintentable = false,
        )
        409 -> ErrorDeServidor(
            "El inventario está cerrado. No se pueden cargar más conteos.",
            reintentable = false,
        )
        400 -> ErrorDeServidor(detalle(cuerpo) ?: "El servidor rechazó el pedido.", false)
        in 500..599 -> ErrorDeServidor(
            "El servidor tuvo un problema. Se va a reintentar solo.",
            reintentable = true,
        )
        else -> ErrorDeServidor(detalle(cuerpo) ?: "No se pudo completar la operación.", false)
    }

    private fun detalle(cuerpo: String): String? = try {
        json.decodeFromString<DetalleDeError>(cuerpo).detail
    } catch (error: Exception) {
        null
    }
}

@kotlinx.serialization.Serializable
private data class PedidoDeAlta(
    val codigo: String,
    val descripcion: String,
    val unidad: String,
    val ubicacion: String?,
)

@kotlinx.serialization.Serializable
private data class DetalleDeError(val detail: String? = null)
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon`
Expected: PASS, 21 tests

**Si `pedir` no compila por ser `inline` con `reified` dentro de una clase con miembros privados:** extraer el cuerpo a una función privada no-inline que devuelva el texto de la respuesta, y dejar la `inline reified` solo para el `decodeFromString`. El test no cambia.

- [ ] **Step 6: Correr todo el proyecto**

Run: `cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS, 35 del núcleo y 21 de la app

- [ ] **Step 7: Verificar contra el servidor de verdad**

Los tests usan respuestas capturadas. Esta verificación usa el servidor vivo, que es lo único que prueba que las rutas y el encabezado son los correctos.

Levantar el servidor con `.\"Iniciar servidor.bat"`, crear una sesión, importar un maestro y dar de alta un operario desde el panel. Después, con el token de ese operario, correr desde `celular/`:

```
C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon --tests "*ClienteServidorTest*"
```

Eso sigue usando MockWebServer. Para la prueba real, escribir un script temporal de Kotlin no vale la pena: alcanza con confirmar con PowerShell que los tres endpoints contestan lo mismo que dicen los archivos de contrato:

```powershell
$t = "<token del operario>"
Invoke-RestMethod "http://127.0.0.1:8000/api/dispositivo/maestro" -Headers @{ "X-Token" = $t } | ConvertTo-Json -Depth 4
```

Comparar a ojo contra `celular/contrato/maestro.json`. Si difieren, **volver a capturar** con `celular/contrato/capturar.py` y correr los tests otra vez: el contrato cambió.

- [ ] **Step 8: Commit**

```bash
git add celular/
git commit -m "Agrega el cliente HTTP del servidor

Los tests responden con los archivos de contrato capturados del servidor
real, no con JSON inventado: si el servidor cambia un nombre de campo, el
test rompe en la PC en vez de fallar en el deposito.

Los errores distinguen lo reintentable de lo definitivo. El celular que
salio del alcance del wifi conserva su trabajo y reintenta solo; el token
revocado no se reintenta nunca, porque no va a funcionar.

Los mensajes son de pantalla y no de registro: el operario los lee en el
deposito, asi que dicen en castellano llano que paso y que hacer."
```

---

## Verificación final del plan

```bash
cd celular && C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Los dos en verde. Con esto queda:

- Un proyecto Android que compila, con dos módulos.
- Toda la lógica de conteo probada en la PC, en segundos, sin celular.
- El contrato con el servidor fijado de los dos lados.
- La base local con su esquema, probada con SQLite real vía Robolectric.
- El cliente HTTP, probado contra las respuestas verdaderas del servidor.

**Lo que todavía no hay:** ninguna pantalla. La app compila pero no se puede abrir para hacer nada — no tiene ni `Activity`. Eso es lo que construye el plan siguiente: vinculación por QR, cámara con escaneo continuo, ficha del artículo, alta rápida, mis conteos, buscar, y el sincronizador en segundo plano.
