# Ingresar el código a mano — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** que el operario pueda escribir un código de barras a mano
cuando la cámara no puede leerlo, y que ese código entre por el mismo camino
que uno leído por cámara.

**Arquitectura:** un botón nuevo en el encabezado de la pantalla de escaneo
abre un diálogo con el mismo teclado numérico grande que ya se usa para
cargar cantidades. Al confirmar, el código tipeado se pasa a la misma
función que ya recibe los códigos de la cámara — no hay lógica de negocio
nueva ni duplicada.

**Tech Stack:** Kotlin, Jetpack Compose, Robolectric (tests de UI sin
celular).

**Especificación:**
`docs/superpowers/specs/2026-08-15-codigo-a-mano-design.md`

## Global Constraints

- **TDD sin excepciones**: test que falla, implementación, test que pasa,
  commit.
- **Los comentarios explican por qué, no qué.**
- **Textos en castellano rioplatense**, sin jerga técnica.
- **Mensajes de commit en castellano, en presente, describiendo el efecto**;
  el cuerpo explica *por qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

## Entorno

```powershell
cd "C:\clientes\Control de Stock\celular"
C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
# Un archivo puntual:
C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.PantallaTest" --no-daemon
```

`JAVA_HOME`, `ANDROID_HOME` y Gradle ya están instalados en esta máquina
(ver `CLAUDE.md`). Las pruebas en celular real necesitan `adb devices`; no
hay emulador instalado.

## Lo que ya existe y se consume

- `PantallaEscaneo(...)` en
  `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`: la
  pantalla con la cámara siempre activa. Recibe `alLeer: (String) -> Unit` y
  `fichaAbierta: Boolean` (hoy calculado en `MainActivity.kt` como
  `hallazgo is Hallazgo.Encontrado || altaDe != null`), y usa
  `fichaAbierta` para pausar la cámara y para decidir si mostrar la `Surface`
  con la ficha.
- `TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit)` en
  `celular/app/src/main/kotlin/com/controldestock/ui/ControlesDeCarga.kt`:
  el teclado grande y propio, ya compartido por `FichaDelArticulo` y
  `FichaDeAlta`. Sus teclas son `"1".."9"`, `"0"`, `","` y `"C"` (limpia
  todo); `alBorrar` borra el último carácter.
  Sus botones son `Button` de Compose con `Text(tecla)` como contenido, así
  que en los tests se los ubica con `onNodeWithText(tecla)`.
- `Hallazgo` (sealed class con `Encontrado` y `Desconocido`) y
  `Contador.buscar(codigo): Hallazgo` en
  `celular/app/src/main/kotlin/com/controldestock/Contador.kt`.
- `hayQueAnunciar` y `pantallaSegun` en
  `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`: las
  decisiones puras de pantalla que ya existen, probadas sin Android en
  `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`.
- El `alLeer` de hoy vive **inline**, como el valor del parámetro
  `alLeer` en la llamada a `PantallaEscaneo(...)` dentro de
  `MainActivity.kt:201-261`. Hace todo el trabajo de una lectura: guarda
  contra relecturas, busca en el maestro, decide si suena el timbre, y abre
  la ficha o la franja roja.
- Los tests de UI que montan cámara de mentira viven en
  `celular/app/src/testDebug/`, no en `celular/app/src/test/`: necesitan
  `ui-test-manifest`, que es dependencia solo de `debug` — un test ahí
  adentro rompería la variante `release`. `PantallaTest.kt` (funciones
  puras, sin Compose) sí va en `src/test/`.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt` | Suma `fichaAbierta`, la decisión pura de si algo tiene que pausar la cámara. |
| `celular/app/src/main/kotlin/com/controldestock/ui/DialogoCodigoAMano.kt` *(nuevo)* | El diálogo con el teclado para escribir un código a mano. |
| `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt` | El botón "A mano" en el encabezado. |
| `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt` | El estado del diálogo, y que el código escrito a mano entre por el mismo camino que uno de cámara. |

---

### Task 1: La decisión de si algo bloquea la cámara

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`

**Interfaces:**
- Produces: `fun fichaAbierta(hallazgo: Hallazgo?, altaDe: String?, ingresandoAMano: Boolean): Boolean`

- [ ] **Step 1: Escribir los tests**

Agregar a `celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt`,
al final de la clase (antes de la última llave que cierra `PantallaTest`):

```kotlin
    @Test
    fun `sin nada abierto no hay ficha`() {
        assertFalse(fichaAbierta(hallazgo = null, altaDe = null, ingresandoAMano = false))
    }

    @Test
    fun `un articulo encontrado abre la ficha`() {
        val hallazgo = Hallazgo.Encontrado(tornillos, admiteDecimales = false, codigo = "7790999")

        assertTrue(fichaAbierta(hallazgo, altaDe = null, ingresandoAMano = false))
    }

    @Test
    fun `un desconocido no abre ninguna ficha`() {
        // La franja roja no es una ficha: se dibuja al lado de la cámara,
        // no la tapa. Si esto diera true, la cámara se pausaría con cada
        // código desconocido, y no hay forma de que se reanude sola.
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertFalse(fichaAbierta(hallazgo, altaDe = null, ingresandoAMano = false))
    }

    @Test
    fun `el alta de un codigo cuenta como ficha abierta`() {
        assertTrue(fichaAbierta(hallazgo = null, altaDe = "7790999", ingresandoAMano = false))
    }

    @Test
    fun `ingresar el codigo a mano tambien pausa la camara`() {
        // Sin esto, una lectura de cámara en el medio le pisa el código que
        // el operario está tipeando.
        assertTrue(fichaAbierta(hallazgo = null, altaDe = null, ingresandoAMano = true))
    }
```

Esta clase ya usa `Hallazgo`, `assertTrue` y `assertFalse` (ver
`import` al principio del archivo) y ya tiene el fixture `tornillos`
(`ArticuloEntidad`) definido arriba, así que no hace falta agregar
imports nuevos.

- [ ] **Step 2: Correr y verificar que fallan**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.PantallaTest" --no-daemon`
Expected: FALLA en compilación — `fichaAbierta` no existe todavía.

- [ ] **Step 3: Agregar la función**

Al final de
`celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt`, después de
`estadoTrasSubir`:

```kotlin

/**
 * Si hay algo en pantalla que tiene que pausar la cámara.
 *
 * Tres causas compiten por la misma atención: la ficha de un artículo, el
 * alta de uno nuevo, o el código que el operario está escribiendo a mano.
 * Ninguna convive con una lectura de cámara que llegue en el medio. Antes
 * de sumar la tercera esto se armaba en línea en `MainActivity.kt` con dos
 * variables sueltas; agregar una tercera ahí sin una función que la cubra
 * repite el patrón que ya costó tres defectos parecidos (ver
 * `docs/superpowers/deuda-conocida.md`).
 *
 * Un `Hallazgo.Desconocido` no cuenta: la franja roja se dibuja al lado de
 * la cámara, no la tapa.
 */
fun fichaAbierta(hallazgo: Hallazgo?, altaDe: String?, ingresandoAMano: Boolean): Boolean =
    hallazgo is Hallazgo.Encontrado || altaDe != null || ingresandoAMano
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.PantallaTest" --no-daemon`
Expected: PASS, 5 tests nuevos sobre los que ya había en esa clase.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/Pantalla.kt \
        celular/app/src/test/kotlin/com/controldestock/ui/PantallaTest.kt
git commit -m "Agrega la decision pura de si algo bloquea la camara

Hasta ahora la pausa de la camara se armaba en linea en MainActivity con
dos variables sueltas. Sumarle una tercera -si el operario esta escribiendo
un codigo a mano- sin una funcion que la cubra repite el patron que ya
costo tres defectos parecidos.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: El diálogo para escribir el código

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/DialogoCodigoAMano.kt`
- Test: `celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoCodigoAManoTest.kt`

**Interfaces:**
- Consumes: `TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit)`
  de `ControlesDeCarga.kt` (ya existe).
- Produces: `@Composable fun DialogoCodigoAMano(alConfirmar: (String) -> Unit, alCancelar: () -> Unit)`

- [ ] **Step 1: Escribir el test**

Crear `celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoCodigoAManoTest.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Vive en `testDebug` y no en `test`: el `AlertDialog` de Compose necesita
 * `ui-test-manifest`, que es dependencia solo de `debug`. Ver el comentario
 * de la misma clase en `PantallaEscaneoTest.kt`.
 */
@RunWith(RobolectricTestRunner::class)
class DialogoCodigoAManoTest {

    @get:Rule
    val compose = createComposeRule()

    @Test
    fun `tocar digitos arma el texto`() {
        // Tres dígitos distintos y sin volver a tocar ninguno: en cuanto el
        // visor muestra un dígito, ese mismo texto coincide también con su
        // tecla, y `onNodeWithText` no puede elegir entre los dos si se lo
        // vuelve a pedir.
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("1").performClick()
        compose.onNodeWithText("2").performClick()
        compose.onNodeWithText("3").performClick()

        compose.onNodeWithText("123").assertIsDisplayed()
    }

    @Test
    fun `C vacia lo tipeado`() {
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("1").performClick()
        compose.onNodeWithText("C").performClick()

        compose.onNodeWithText("…").assertIsDisplayed()
    }

    @Test
    fun `la coma no hace nada`() {
        // Un código de barras no lleva decimales.
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("1").performClick()
        compose.onNodeWithText("2").performClick()
        compose.onNodeWithText(",").performClick()

        compose.onNodeWithText("12").assertIsDisplayed()
    }

    @Test
    fun `confirmar esta deshabilitado con el campo vacio`() {
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("Confirmar").assertIsNotEnabled()
    }

    @Test
    fun `confirmar con texto avisa con lo tipeado`() {
        var confirmado: String? = null
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = { confirmado = it }, alCancelar = {})
        }

        compose.onNodeWithText("7").performClick()
        compose.onNodeWithText("9").performClick()
        compose.onNodeWithText("Confirmar").performClick()

        assertEquals("79", confirmado)
    }

    @Test
    fun `cancelar avisa sin tipear nada`() {
        var cancelado = false
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = { cancelado = true })
        }

        compose.onNodeWithText("Cancelar").performClick()

        assertTrue(cancelado)
    }
}
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.DialogoCodigoAManoTest" --no-daemon`
Expected: FALLA en compilación — `DialogoCodigoAMano` no existe todavía.

- [ ] **Step 3: Crear el diálogo**

Crear `celular/app/src/main/kotlin/com/controldestock/ui/DialogoCodigoAMano.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * El código escrito a mano, para cuando la cámara no puede leer la
 * etiqueta —rota, tapada, mal impresa—.
 *
 * El mismo teclado grande que ya se usa para cargar cantidades: se usa con
 * apuro y a veces con guantes, así que el teclado chico del sistema no
 * sirve acá tampoco.
 *
 * No entrega el código por un camino propio: quien lo use lo pasa por el
 * mismo `alLeer` que ya recibe los códigos de la cámara, para heredar sin
 * duplicar el timbre, el aviso de repetido y el alta rápida.
 */
@Composable
fun DialogoCodigoAMano(alConfirmar: (String) -> Unit, alCancelar: () -> Unit) {
    var texto by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCancelar,
        title = { Text("Código a mano") },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    // No es "0" como en el visor de cantidad: un código
                    // vacío no es un código de valor cero, es que todavía
                    // no se escribió nada.
                    texto.ifEmpty { "…" },
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                )
                TecladoNumerico(
                    alTocar = { tecla ->
                        texto = when (tecla) {
                            "C" -> ""
                            "," -> texto
                            else -> texto + tecla
                        }
                    },
                    alBorrar = { texto = texto.dropLast(1) },
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { alConfirmar(texto) }, enabled = texto.isNotEmpty()) {
                Text("Confirmar")
            }
        },
        dismissButton = {
            TextButton(onClick = alCancelar) { Text("Cancelar") }
        },
    )
}
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.DialogoCodigoAManoTest" --no-daemon`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/DialogoCodigoAMano.kt \
        celular/app/src/testDebug/kotlin/com/controldestock/ui/DialogoCodigoAManoTest.kt
git commit -m "Agrega el dialogo para escribir el codigo a mano

Mismo teclado grande que ya se usa para cargar cantidades: se usa con
apuro y a veces con guantes, y el teclado chico del sistema no sirve acá
tampoco. No entrega el codigo por un camino propio, para heredarlo en la
tarea siguiente sin duplicar logica de negocio.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Conectar el botón, el diálogo y la pantalla

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`
- Modify: `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Interfaces:**
- Consumes: `fichaAbierta(hallazgo, altaDe, ingresandoAMano)` (Task 1),
  `DialogoCodigoAMano(alConfirmar, alCancelar)` (Task 2).
- Produces: `PantallaEscaneo` gana los parámetros
  `puedeIngresarAMano: Boolean` y `alIngresarAMano: () -> Unit`.

- [ ] **Step 1: Escribir los tests del botón**

En `celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt`,
agregar estos dos parámetros a **las dos** llamadas existentes a
`PantallaEscaneo(...)` (una en `el boton de la franja lleva al alta`, otra
en `montarConFicha`), justo después de `alSubir = {},`:

```kotlin
                puedeIngresarAMano = true,
                alIngresarAMano = {},
```

Y agregar estos dos tests nuevos, al final de la clase (antes de la última
llave que cierra `PantallaEscaneoTest`):

```kotlin
    @Test
    fun `el boton de ingreso a mano llama al callback cuando esta habilitado`() {
        var abrio = false
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = false,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = true,
                alIngresarAMano = { abrio = true },
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("A mano").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `el boton de ingreso a mano queda deshabilitado con algo mas abierto`() {
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = true,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = false,
                alIngresarAMano = {},
                camara = { _, _ -> },
            ) { }
        }

        compose.onNodeWithText("A mano").assertIsNotEnabled()
    }
```

Este archivo ya importa `assertTrue` y `performClick`; agregar
`import androidx.compose.ui.test.assertIsNotEnabled` a la lista de imports
del principio del archivo, junto a los otros `androidx.compose.ui.test.*`.

- [ ] **Step 2: Correr y verificar que falla**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.PantallaEscaneoTest" --no-daemon`
Expected: FALLA en compilación — `PantallaEscaneo` todavía no tiene los
parámetros `puedeIngresarAMano` ni `alIngresarAMano`.

- [ ] **Step 3: Agregar el botón a `PantallaEscaneo`**

En `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`,
la firma de `PantallaEscaneo` gana dos parámetros nuevos. Agregarlos
después de `alSubir: () -> Unit,`:

```kotlin
    alSubir: () -> Unit,
    /** Si el operario puede abrir el ingreso de código a mano ahora mismo. */
    puedeIngresarAMano: Boolean,
    alIngresarAMano: () -> Unit,
```

Y reemplazar el `Row` del encabezado —hoy termina con la llamada a
`IndicadorDePendientes(...)`— por:

```kotlin
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(pasada, style = MaterialTheme.typography.titleMedium)
            Text(operario, style = MaterialTheme.typography.bodyMedium)
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(
                    onClick = alIngresarAMano,
                    enabled = puedeIngresarAMano,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                ) {
                    Text("A mano", style = MaterialTheme.typography.bodySmall)
                }
                IndicadorDePendientes(
                    pendientes = pendientes,
                    estado = estadoDeSubida,
                    alSubir = alSubir,
                )
            }
        }
```

- [ ] **Step 4: Correr y verificar que pasan**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --tests "com.controldestock.ui.PantallaEscaneoTest" --no-daemon`
Expected: PASS, 4 tests sobre los 2 que ya había en esa clase.

- [ ] **Step 5: Conectar todo en `MainActivity.kt`**

Estos cambios no tienen test propio de Compose —`App()` monta la cámara real
y no corre sin celular—, así que se verifican en el paso siguiente, en el
celular.

**5a.** Agregar el estado nuevo, junto a `altaDe` (línea 78 de
`MainActivity.kt`):

```kotlin
    var altaDe by remember { mutableStateOf<String?>(null) }
    // Cuenta como una ficha más para pausar la cámara: sin esto, una
    // lectura de cámara en el medio le pisa el código que el operario está
    // tipeando a mano.
    var ingresandoAMano by remember { mutableStateOf(false) }
```

**5b.** Sacar el `alLeer` de adentro de la llamada a `PantallaEscaneo` y
convertirlo en un valor con nombre, para poder llamarlo también desde el
diálogo. Agregarlo justo después de la función `subir` (después de la
línea 122, antes de `LaunchedEffect`):

```kotlin
    /**
     * Resuelve un código nuevo, venga de la cámara o escrito a mano: los
     * dos entran por acá para heredar el mismo timbre, el mismo aviso de
     * repetido y el mismo camino al alta rápida sin duplicar nada.
     */
    val leerCodigo: (String) -> Unit = { codigo ->
        // La cámara avisa una lectura por cuadro, y esta guarda sola no
        // alcanza: decide acá, pero el estado se escribe recién cuando la
        // corrutina vuelve de la base. En esa ventana entra el barrido que
        // hace el operario al bajar el celular para tocar «Darlo de alta»,
        // y la lectura de otro estante se aplica encima de lo que ya tocó.
        //
        // La bandera se toma en el mismo golpe que la lectura, así hay una
        // sola búsqueda en vuelo por vez y no un chorro de consultas por
        // cuadro. Mira lo mismo que decide `fichaAbierta`: si mirara otra
        // cosa, la cámara seguiría entregando lecturas con una ficha en
        // pantalla.
        val laToma = hallazgo == null && altaDe == null &&
            leyendo.compareAndSet(false, true)

        if (laToma) {
            alcance.launch {
                try {
                    // Todo lo que consulta la base va primero: después de
                    // revalidar no puede quedar ninguna suspensión, o la
                    // ventana se vuelve a abrir entre el control y la
                    // escritura.
                    val h = contador.buscar(codigo)
                    val previosDelArticulo = (h as? Hallazgo.Encontrado)
                        ?.let { contador.conteosDe(it.articulo) }

                    // Lo que valía al leer puede no valer más: si mientras
                    // tanto se abrió una ficha o el alta, esta lectura
                    // llegó tarde y se descarta —si no, se aplica encima de
                    // lo que el operario ya eligió, que es lo único que él
                    // vio.
                    if (hallazgo != null || altaDe != null) return@launch

                    // El mismo desconocido, cuadro tras cuadro, no se
                    // vuelve a anunciar: la franja ya lo está mostrando.
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
                } finally {
                    leyendo.set(false)
                }
            }
        }
    }
```

**5c.** Dentro de `Pantalla.Escaneando -> { ... }`, justo después de
`val quien = vinculacion.value`, calcular si hay algo abierto y usarlo
tanto para `fichaAbierta` como para habilitar el botón:

```kotlin
        Pantalla.Escaneando -> {
            val quien = vinculacion.value
            // Cuando la única causa es `ingresandoAMano`, `fichaAbierta`
            // igual da true: `PantallaEscaneo` muestra la `Surface` de la
            // ficha, pero el contenido que le pasamos (más abajo) no
            // dibuja nada para ese caso, así que queda en 0dp de alto —no
            // se ve nada raro en pantalla.
            val hayAlgoAbierto = fichaAbierta(hallazgo, altaDe, ingresandoAMano)

            PantallaEscaneo(
                operario = quien?.operarioNombre.orEmpty(),
                pasada = quien?.pasadaEtiqueta.orEmpty(),
                pendientes = pendientes,
                fichaAbierta = hayAlgoAbierto,
                avisoDeDesconocido = avisoDesconocido,
                alDarDeAlta = codigoDesconocido?.let { codigo ->
                    {
                        hallazgo = null
                        altaDe = codigo
                    }
                },
                estadoDeSubida = estadoDeSubida,
                alSubir = {
                    if (subiendo.compareAndSet(false, true)) {
                        alcance.launch {
                            try {
                                subir(loPidioElOperario = true)
                            } finally {
                                subiendo.set(false)
                            }
                        }
                    }
                },
                puedeIngresarAMano = !hayAlgoAbierto,
                alIngresarAMano = { ingresandoAMano = true },
                alLeer = leerCodigo,
            ) {
```

(El resto del cuerpo de esta llamada —el contenido de la ficha, con
`FichaDelArticulo` y `FichaDeAlta`— no cambia.)

**5d.** Después de que se cierra la llamada a `PantallaEscaneo(...) { ... }`
pero todavía dentro de `Pantalla.Escaneando -> { ... }`, agregar el
diálogo:

```kotlin
            if (ingresandoAMano) {
                DialogoCodigoAMano(
                    alConfirmar = { codigo ->
                        ingresandoAMano = false
                        leerCodigo(codigo)
                    },
                    alCancelar = { ingresandoAMano = false },
                )
            }
        }
```

**5e.** Agregar los imports que falten al principio de `MainActivity.kt`,
junto a los otros `import com.controldestock.ui.*`:

```kotlin
import com.controldestock.ui.DialogoCodigoAMano
import com.controldestock.ui.fichaAbierta
```

- [ ] **Step 6: Compilar y correr toda la suite de Kotlin**

Run: `C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS, todos los tests — este paso no agrega tests nuevos a esta
suite completa (los de las Steps 1-4 ya corrieron), es la verificación de
que nada más se rompió.

- [ ] **Step 7: Verificar en el celular**

Instalar la app en un celular real y, contra un servidor con el maestro
cargado:

1. Tocar **"A mano"**, escribir el código de un artículo que está en el
   maestro, tocar **Confirmar**. Tiene que abrirse su ficha con la
   descripción y la ubicación correctas — las mismas que si se hubiera
   leído con la cámara.
2. Tocar **"A mano"** de nuevo, escribir un código que no existe, tocar
   **Confirmar**. Tiene que aparecer la franja roja con **"Darlo de
   alta"**, igual que con un código desconocido de cámara.
3. Abrir el diálogo y, sin cerrarlo, apuntar la cámara a un código válido
   real: no tiene que pasar nada mientras el diálogo sigue abierto — la
   cámara está pausada.
4. Con una ficha abierta (después de leer o escribir un código que está en
   el maestro), confirmar que el botón **"A mano"** se ve gris y no
   responde al toque.
5. Cargar la cantidad de un artículo que ya se había contado en esa
   ubicación usando el código a mano: tiene que salir el mismo aviso
   «¿Ya lo contaste acá?» que sale con cámara.

Si alguno de estos pasos falla, no seguir: es exactamente lo que esta tarea
viene a resolver.

- [ ] **Step 8: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt \
        celular/app/src/testDebug/kotlin/com/controldestock/ui/PantallaEscaneoTest.kt \
        celular/app/src/main/kotlin/com/controldestock/MainActivity.kt
git commit -m "Conecta el ingreso de codigo a mano con la pantalla de escaneo

El boton 'A mano' abre el dialogo de la tarea anterior; al confirmar, el
codigo tipeado entra por el mismo leerCodigo que ya usa la camara, asi que
hereda el timbre, el aviso de repetido y el alta rapida sin logica nueva.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Verificación final del plan

```powershell
cd "C:\clientes\Control de Stock\celular"
C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
```

Todo en verde, y sobre todo: **un operario puede escribir un código a mano
desde la pantalla de escaneo y contar el artículo, sea que esté en el
maestro o no, sin que la cámara le pise el código mientras lo escribe.**
