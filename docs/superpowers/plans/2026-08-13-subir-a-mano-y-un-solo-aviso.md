# Subir a mano y un solo aviso por código — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** que el timbre del código desconocido suene una vez y no una por
cuadro, y que el operario pueda subir lo que falta tocando el indicador de
pendientes, sin tener que inventarse un escaneo.

**Arquitectura:** la decisión de anunciar una lectura sale a una función pura
que se prueba sin Android, al lado de `pantallaSegun`. El indicador del
encabezado sale a un componente propio con cuatro estados, que se prueba sin
montar la cámara, igual que la franja del desconocido.

**Herramientas:** Kotlin, Jetpack Compose, JUnit4, Robolectric, Compose UI
Test.

**Especificación:**
`docs/superpowers/specs/2026-08-13-subir-a-mano-y-un-solo-aviso-design.md`

## Global Constraints

- **Cantidades en milésimas, siempre `Int`.**
- **Textos en castellano rioplatense**, sin jerga técnica. Leer cada frase
  que ve el operario como si se dijera en voz alta: en el plan anterior se
  coló «de este producto **en sin ubicación** a las 10:32», que compilaba
  perfecto.
- **Nada bloquea al operario.** La sincronización nunca puede hacerlo
  esperar: mientras sube, tiene que poder seguir escaneando y contando.
- **Nada se edita ni se borra.**
- **Mensajes de commit en castellano, en presente, describiendo el efecto**;
  el cuerpo explica *por qué*, no *qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- **Los comentarios explican por qué, no qué.**
- **TDD sin excepciones**: test que falla, implementación, test que pasa,
  commit. Y **mutar cada rama nueva** confirmando con `git diff` que el
  archivo cambió de verdad: varios archivos de este repo están en disco con
  finales de línea CRLF, así que un patrón escrito con `\n` no engancha, la
  mutación nunca se aplica y el build pasa como si el test no discriminara.

## Entorno

El `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta
nada: siempre el intérprete del venv por ruta.

```powershell
cd "C:\clientes\Control de Stock\celular"
C:\Gradle\gradle-8.7\bin\gradle.bat test --rerun-tasks --no-daemon
C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.PantallaTest" --no-daemon
```

Los tests de pantalla van en `celular/app/src/testDebug/kotlin/...`, **no** en
`src/test/`: necesitan una actividad que aporta `ui-test-manifest`, que es
dependencia de debug, y desde `src/test` el archivo corre también contra
release, donde esa actividad no existe. Los tests de lógica pura sí van en
`src/test/`.

## Lo que ya existe y se consume

- `Hallazgo.Encontrado(articulo, admiteDecimales, codigo)` y
  `Hallazgo.Desconocido(codigo)`, en `com.controldestock`.
- `pantallaSegun(vinculacion): Pantalla`, en `ui/Pantalla.kt`, con sus tests
  en `src/test/.../ui/PantallaTest.kt` — el molde a seguir para la función
  nueva.
- `FranjaDeDesconocido(aviso, alDarDeAlta, modifier)`, en
  `ui/PantallaEscaneo.kt`, con sus tests en `testDebug` — el molde a seguir
  para el componente nuevo.
- `Sincronizador.sincronizar(): ResultadoDeSync`, con `enviados`,
  `rechazados`, `huboError` y `yaExistian`.
- `Verde` y `Ambar` en `ui/Tema.kt`.
- En `MainActivity`, el patrón de guarda de reentrada:
  `val leyendo = remember { AtomicBoolean(false) }` tomada sincrónicamente
  antes del `launch` y liberada en un `finally` que **no** envuelve la espera
  de la red.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `ui/Pantalla.kt` | Suma `hayQueAnunciar`, la decisión pura de si una lectura se anuncia. |
| `ui/PantallaEscaneo.kt` | Suma `EstadoDeSubida` y el componente `IndicadorDePendientes`. |
| `MainActivity.kt` | Cablea las dos cosas. |
| `src/test/.../ui/PantallaTest.kt` | Los tests de `hayQueAnunciar`. |
| `src/testDebug/.../ui/IndicadorDePendientesTest.kt` *(nuevo)* | Los estados del indicador. |

---

### Task 1: El código desconocido se anuncia una vez

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`

**Interfaces:**
- Consumes: `Hallazgo.Encontrado`, `Hallazgo.Desconocido`
- Produces: `hayQueAnunciar(hallazgo: Hallazgo, codigoEnLaFranja: String?): Boolean`

- [ ] **Step 1: Escribir los tests**

Agregar a `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`:

```kotlin
    private val tornillos = ArticuloEntidad(
        id = 1, idOrden = 1, sku = "A-1", descripcion = "Tornillos",
        unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
        busqueda = textoDeBusqueda("Tornillos", "A-1", "P-1"),
    )

    @Test
    fun `un codigo desconocido nuevo se anuncia`() {
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = null))
    }

    @Test
    fun `el desconocido que ya esta en la franja no se vuelve a anunciar`() {
        // La cámara avisa una lectura por cuadro: sin esto, una etiqueta
        // quieta frente al celular suena varias veces por segundo hasta que
        // el operario la saca de encima.
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertFalse(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }

    @Test
    fun `otro desconocido distinto si se anuncia`() {
        // Cambió el producto: es información nueva y el operario tiene que
        // enterarse.
        val hallazgo = Hallazgo.Desconocido("7790111")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }

    @Test
    fun `un codigo que esta en el maestro se anuncia siempre`() {
        // No necesita la excepción: al abrirse su ficha el escaneo se pausa
        // solo, así que no hay repetición que evitar.
        val hallazgo = Hallazgo.Encontrado(tornillos, admiteDecimales = false, codigo = "7790999")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }
```

Imports nuevos: `com.controldestock.Hallazgo`,
`com.controldestock.datos.ArticuloEntidad`,
`com.controldestock.datos.textoDeBusqueda`, `org.junit.Assert.assertTrue`,
`org.junit.Assert.assertFalse`.

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.PantallaTest" --no-daemon`
Expected: FAIL con `Unresolved reference: hayQueAnunciar`

- [ ] **Step 3: Implementar la función**

Al final de `ui/Pantalla.kt`, con el import `com.controldestock.Hallazgo`:

```kotlin
/**
 * Si esta lectura hay que anunciarla con sonido y vibración.
 *
 * La cámara avisa una lectura por cuadro. Con un código que está en el
 * maestro eso no molesta: al abrirse su ficha el escaneo se pausa solo. Con
 * uno desconocido no se pausa nada, y la misma etiqueta quieta frente al
 * celular vuelve a sonar en cada cuadro. Un timbre repetido veinte veces
 * deja de avisar y pasa a estorbar, que es la forma más rápida de enseñarle
 * al operario a ignorarlo.
 *
 * No se pierde información al callarlo: la franja sigue mostrando el código.
 *
 * @param codigoEnLaFranja el desconocido que ya está en pantalla, si hay uno.
 */
fun hayQueAnunciar(hallazgo: Hallazgo, codigoEnLaFranja: String?): Boolean =
    when (hallazgo) {
        is Hallazgo.Encontrado -> true
        is Hallazgo.Desconocido -> hallazgo.codigo != codigoEnLaFranja
    }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.PantallaTest" --no-daemon`
Expected: PASS, 4 tests nuevos

- [ ] **Step 5: Usarla en la pantalla**

En `MainActivity.kt`, dentro del `alcance.launch` de `alLeer`, reemplazar el
bloque `when (h) { ... }` por este. El cálculo va **antes** del `when` para
que las dos ramas de la función queden vivas, y **después** del revalidado,
donde ya no hay ninguna suspensión:

```kotlin
                                // El mismo desconocido, cuadro tras cuadro,
                                // no se vuelve a anunciar: la franja ya lo
                                // está mostrando.
                                val anunciar = hayQueAnunciar(h, codigoDesconocido)

                                when (h) {
                                    is Hallazgo.Encontrado -> {
                                        if (anunciar) avisos.leido()
                                        avisoDesconocido = null
                                        codigoDesconocido = null
                                        previos = previosDelArticulo.orEmpty()
                                        hallazgo = h
                                    }
                                    is Hallazgo.Desconocido -> {
                                        if (anunciar) avisos.desconocido()
                                        codigoDesconocido = h.codigo
                                        avisoDesconocido =
                                            "Este código no está en el conteo: ${h.codigo}"
                                    }
                                }
```

Import nuevo: `com.controldestock.ui.hayQueAnunciar`.

- [ ] **Step 6: Mutar para confirmar que los tests muerden**

Cambiar el cuerpo de `hayQueAnunciar` por `true` a secas y correr los tests
de `PantallaTest`. Tiene que caer `el desconocido que ya esta en la franja no
se vuelve a anunciar` y **solo** ese.

Confirmar con `git diff` que el archivo cambió antes de creerle a la salida
de Gradle, y revertir después.

- [ ] **Step 7: Correr la suite completa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --rerun-tasks --no-daemon`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt celular/app/src/main/kotlin/com/controldestock/MainActivity.kt celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt
git commit -m "Anuncia una sola vez el codigo que no esta en el conteo

La camara avisa una lectura por cuadro, y con un desconocido no se pausa
nada: la misma etiqueta quieta frente al celular volvia a sonar varias veces
por segundo hasta que el operario la sacaba de encima.

Un timbre repetido veinte veces deja de avisar y pasa a estorbar, que es la
forma mas rapida de ensenarle a ignorarlo. No se pierde informacion al
callarlo: la franja sigue mostrando el codigo.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: El indicador de pendientes es el botón para subir

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`
- Create: `celular/app/src/testDebug/kotlin/com/controldestock/ui/IndicadorDePendientesTest.kt`
- Modify: `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Interfaces:**
- Consumes: `Sincronizador.sincronizar(): ResultadoDeSync`, `Verde`, `Ambar`
- Produces:
  - `EstadoDeSubida` — `Quieto`, `Subiendo`, `NoPudo`
  - `IndicadorDePendientes(pendientes: Int, estado: EstadoDeSubida, alSubir: () -> Unit)`
  - `PantallaEscaneo` suma los parámetros `estadoDeSubida: EstadoDeSubida` y
    `alSubir: () -> Unit`, los dos **antes** de `camara`

- [ ] **Step 1: Escribir los tests del indicador**

Crear `celular/app/src/testDebug/kotlin/com/controldestock/ui/IndicadorDePendientesTest.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertHasNoClickAction
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * El indicador del encabezado, que además de informar resuelve.
 *
 * Vive en `testDebug` por lo mismo que las otras pruebas de pantalla:
 * necesitan una actividad que aporta `ui-test-manifest`, que es dependencia
 * de debug, y desde `src/test` el archivo correría también contra release,
 * donde esa actividad no existe.
 */
@RunWith(RobolectricTestRunner::class)
class IndicadorDePendientesTest {

    @get:Rule
    val compose = createComposeRule()

    private var subio = false

    private fun montar(pendientes: Int, estado: EstadoDeSubida) {
        compose.setContent {
            IndicadorDePendientes(
                pendientes = pendientes,
                estado = estado,
                alSubir = { subio = true },
            )
        }
    }

    @Test
    fun `sin nada pendiente avisa que esta al dia y no se toca`() {
        montar(pendientes = 0, estado = EstadoDeSubida.Quieto)

        compose.onNodeWithText("Todo al día").assertIsDisplayed()
        compose.onNodeWithText("Todo al día").assertHasNoClickAction()
    }

    @Test
    fun `con pendientes dice cuantos y sube al tocarlo`() {
        // Es el lugar donde el operario ya mira para saber si le falta algo:
        // que sea también donde toca para resolverlo le ahorra una pantalla.
        montar(pendientes = 3, estado = EstadoDeSubida.Quieto)

        compose.onNodeWithText("3 sin subir").assertHasClickAction()
        compose.onNodeWithText("3 sin subir").performClick()

        assertTrue(subio)
    }

    @Test
    fun `mientras sube lo dice y no se puede volver a tocar`() {
        montar(pendientes = 3, estado = EstadoDeSubida.Subiendo)

        compose.onNodeWithText("Subiendo…").assertIsDisplayed()
        compose.onNodeWithText("Subiendo…").assertHasNoClickAction()
    }

    @Test
    fun `si no pudo lo dice y se puede reintentar`() {
        // Sin esto el operario no tiene forma de saber que su intento falló,
        // ni de volver a intentarlo sin inventarse un escaneo.
        montar(pendientes = 3, estado = EstadoDeSubida.NoPudo)

        compose.onNodeWithText("No se pudo subir").assertHasClickAction()
        compose.onNodeWithText("No se pudo subir").performClick()

        assertTrue(subio)
    }

    @Test
    fun `no pudo se muestra aunque el contador quede en cero`() {
        // Puede pasar: sube todo menos un alta rechazada. Decir «Todo al día»
        // ahí sería mentirle.
        montar(pendientes = 0, estado = EstadoDeSubida.NoPudo)

        compose.onNodeWithText("No se pudo subir").assertIsDisplayed()
    }
}
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.IndicadorDePendientesTest" --no-daemon`
Expected: FAIL con `Unresolved reference: IndicadorDePendientes` y `EstadoDeSubida`

- [ ] **Step 3: Implementar el estado y el componente**

En `ui/PantallaEscaneo.kt`, antes de `PantallaEscaneo`:

```kotlin
/** En qué anda la subida de lo que todavía no viajó. */
sealed class EstadoDeSubida {
    /** Nada en curso: el indicador dice cuántos faltan. */
    object Quieto : EstadoDeSubida()

    object Subiendo : EstadoDeSubida()

    /** El último intento no pudo. Se toca para reintentar. */
    object NoPudo : EstadoDeSubida()
}

/**
 * Cuántos conteos faltan subir, y el botón para subirlos.
 *
 * Informa y resuelve en el mismo lugar a propósito: es donde el operario ya
 * mira para saber si le falta algo, así que es donde tiene que poder tocar
 * para resolverlo. Antes de esto, la única forma de que subiera lo pendiente
 * era confirmar un conteo: el que terminaba de contar y volvía a la zona con
 * señal tenía que inventarse un escaneo, o esperar sin saber cuánto.
 *
 * Vive aparte de `PantallaEscaneo` para poder probarse: la pantalla monta la
 * cámara y CameraX no arranca sin celular.
 */
@Composable
internal fun IndicadorDePendientes(
    pendientes: Int,
    estado: EstadoDeSubida,
    alSubir: () -> Unit,
) {
    val texto = when {
        estado is EstadoDeSubida.Subiendo -> "Subiendo…"
        estado is EstadoDeSubida.NoPudo -> "No se pudo subir"
        pendientes == 0 -> "Todo al día"
        else -> "$pendientes sin subir"
    }

    val color = when {
        estado is EstadoDeSubida.NoPudo -> MaterialTheme.colorScheme.error
        estado is EstadoDeSubida.Subiendo -> Ambar
        pendientes == 0 -> Verde
        else -> Ambar
    }

    // Tocar mientras ya está subiendo no haría nada, y un botón que no hace
    // nada enseña a desconfiar del botón.
    val tocable = when (estado) {
        is EstadoDeSubida.Subiendo -> false
        is EstadoDeSubida.NoPudo -> true
        is EstadoDeSubida.Quieto -> pendientes > 0
    }

    if (tocable) {
        // Con forma de botón: un texto suelto en el encabezado no parece
        // tocable, y este es el único lugar donde el operario puede pedir
        // que suba lo que falta.
        OutlinedButton(
            onClick = alSubir,
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
        ) {
            Text(texto, style = MaterialTheme.typography.bodySmall, color = color)
        }
    } else {
        Text(texto, style = MaterialTheme.typography.bodySmall, color = color)
    }
}
```

Imports nuevos en el archivo: `androidx.compose.foundation.layout.PaddingValues`,
`androidx.compose.material3.OutlinedButton`.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.IndicadorDePendientesTest" --no-daemon`
Expected: PASS, 5 tests nuevos

- [ ] **Step 5: Usar el componente en la pantalla**

En `PantallaEscaneo`, agregar los dos parámetros **antes** de `camara` —el
orden importa: `camara` tiene valor por defecto y `ficha` es la lambda final:

```kotlin
    estadoDeSubida: EstadoDeSubida,
    alSubir: () -> Unit,
```

Y reemplazar el `Text` del indicador en el encabezado por:

```kotlin
            IndicadorDePendientes(
                pendientes = pendientes,
                estado = estadoDeSubida,
                alSubir = alSubir,
            )
```

En `PantallaEscaneoTest.kt` hay **tres** llamadas a `PantallaEscaneo` (una en
`el boton de la franja lleva al alta`, dos por el ayudante `montarConFicha`).
Agregar a cada una `estadoDeSubida = EstadoDeSubida.Quieto` y
`alSubir = {}`.

- [ ] **Step 6: Cablear en `MainActivity`**

Estado nuevo, junto al que ya está:

```kotlin
    var estadoDeSubida by remember {
        mutableStateOf<EstadoDeSubida>(EstadoDeSubida.Quieto)
    }
    // Bandera común y no estado de Compose, igual que `leyendo` y
    // `guardando`: tiene que valer en el instante del toque y no en el
    // próximo cuadro.
    val subiendo = remember { AtomicBoolean(false) }
```

Y una función local, antes del `when (pantalla)`, que envuelve **todas** las
sincronizaciones:

```kotlin
    /**
     * Sube lo pendiente y deja el indicador contando lo que pasó.
     *
     * La usan las tres sincronizaciones —la del conteo, la del alta y la que
     * pide el operario— a propósito: con un estado por cada una, el operario
     * vería «3 sin subir» mientras esos tres están viajando.
     */
    suspend fun subir(): ResultadoDeSync {
        estadoDeSubida = EstadoDeSubida.Subiendo
        val resultado = sincronizador.sincronizar()
        pendientes = base.conteoDao().cantidadPendientes()
        estadoDeSubida =
            if (resultado.huboError) EstadoDeSubida.NoPudo else EstadoDeSubida.Quieto
        return resultado
    }
```

En la llamada a `PantallaEscaneo`, los dos parámetros nuevos:

```kotlin
                estadoDeSubida = estadoDeSubida,
                alSubir = {
                    // La bandera se toma en el toque, sincrónicamente: entre
                    // el toque y el cambio de estado hay un cuadro, y el
                    // input se reparte antes de recomponer.
                    if (subiendo.compareAndSet(false, true)) {
                        alcance.launch {
                            try {
                                subir()
                            } finally {
                                subiendo.set(false)
                            }
                        }
                    }
                },
```

Y reemplazar las **dos** llamadas que hoy dicen `sincronizador.sincronizar()`
por `subir()`, sacando el `pendientes = base.conteoDao().cantidadPendientes()`
que viene inmediatamente después, porque ahora lo hace `subir()`. La del alta
guarda el resultado, que ya lo usaba:

```kotlin
                                val resultado = subir()
```

Imports nuevos: `com.controldestock.ui.EstadoDeSubida`.

- [ ] **Step 7: Mutar para confirmar que los tests muerden**

Dos mutaciones, una por vez, cada una revertida y verificada con `git diff`:

1. En `tocable`, cambiar la rama `Quieto` por `false`. Tiene que caer `con
   pendientes dice cuantos y sube al tocarlo` y solo ese.
2. En `texto`, sacar la rama de `NoPudo`. Tienen que caer los dos tests de
   `No se pudo subir` y ninguno más.

- [ ] **Step 8: Correr la suite completa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --rerun-tasks --no-daemon`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt celular/app/src/main/kotlin/com/controldestock/MainActivity.kt celular/app/src/testDebug
git commit -m "Deja subir lo pendiente tocando el indicador

Hasta ahora la unica forma de que subiera lo que falta era confirmar un
conteo: el operario que terminaba y volvia a la zona con senial tenia que
inventarse un escaneo, o esperar los quince minutos del trabajo de fondo sin
saber cuanto le faltaba.

El indicador es el lugar donde ya mira para saber si le falta algo, asi que
es donde tiene que poder tocar para resolverlo. Toma forma de boton porque un
texto suelto en el encabezado no parece tocable.

El mismo indicador refleja tambien las sincronizaciones automaticas: con un
estado por cada una, el operario veria «3 sin subir» mientras esos tres estan
viajando.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Probarlo en el celular

**Files:** ninguno. Es la verificación que ningún test puede dar.

- [ ] **Step 1: Instalar**

```powershell
cd "C:\clientes\Control de Stock\celular"
C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb install -r "C:\clientes\Control de Stock\celular\app\build\outputs\apk\debug\app-debug.apk"
```

- [ ] **Step 2: El timbre suena una vez**

Apuntar a un código que **no** esté en el maestro y **dejarlo quieto en
cuadro varios segundos**. Tiene que sonar **una vez** y quedarse callado, con
la franja roja mostrando el código.

Después mover el celular a otro código desconocido: tiene que sonar de nuevo,
porque es información nueva. Y volver al primero: suena, porque la franja ya
cambió.

Es lo que motivó el cambio, así que si acá suena repetido, nada de lo demás
importa.

- [ ] **Step 3: El botón sube lo que falta**

1. Con la WiFi cortada (`adb shell svc wifi disable`), contar dos artículos.
   El indicador tiene que decir **«2 sin subir»** y verse como un botón.
2. Tocarlo: tiene que decir **«Subiendo…»** y terminar en **«No se pudo
   subir»**, en rojo.
3. Prender la WiFi (`adb shell svc wifi enable`) y tocarlo de nuevo: tiene
   que terminar en **«Todo al día»**, en verde.
4. Confirmar que los conteos llegaron al servidor:

```powershell
cd "C:\clientes\Control de Stock"
.\servidor\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'servidor\inventario.db'); print(c.execute('SELECT COUNT(*) FROM conteo').fetchone())"
```

- [ ] **Step 4: No bloquea al operario**

Con varios pendientes y la WiFi cortada, tocar el indicador y **seguir
escaneando y contando mientras dice «Subiendo…»**. Tiene que dejar: la cámara
sigue leyendo, las fichas abren y los conteos entran. Lo que se cargue en el
medio queda para la vuelta siguiente.

- [ ] **Step 5: Commit de lo que haga falta**

Si los pasos anteriores no encontraron nada, no hay nada que commitear y la
tarea cierra acá. Si encontraron algo, se arregla con su test primero.

---

## Verificación final del plan

```powershell
cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --rerun-tasks --no-daemon
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Los dos en verde —el servidor no se toca en este plan, así que sus 352 tienen
que seguir igual— y los cinco pasos del celular hechos.

**Lo que queda para después**, ya anotado en `docs/superpowers/deuda-conocida.md`:
que suba solo al volver la señal, y que los conteos que el servidor rechaza
dejen de desaparecer del contador sin que nadie los muestre.
