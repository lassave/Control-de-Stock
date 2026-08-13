package com.controldestock.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.controldestock.datos.UnidadEntidad
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Vive en `testDebug` por lo mismo que `FichaDelArticuloTest`: probar una
 * pantalla necesita una actividad que aporta `ui-test-manifest`, y eso no
 * puede viajar en el APK que se instala en el depósito.
 *
 * Estos tests son la única red que tienen las guardas del alta: `darDeAlta`
 * acepta una descripción vacía, una unidad que no está en el catálogo y
 * cualquier cantidad. Todo lo que no se ataje acá llega al servidor.
 */
@RunWith(RobolectricTestRunner::class)
class FichaDeAltaTest {

    @get:Rule
    val compose = createComposeRule()

    private val unidades = listOf(
        UnidadEntidad("UN", "Unidad", 0),
        UnidadEntidad("KG", "Kilogramo", 1),
    )

    private var alta: List<Any?>? = null
    private var cancelado = false

    private fun abrir(catalogo: List<UnidadEntidad> = unidades) {
        compose.setContent {
            FichaDeAlta(
                codigo = "7790999",
                unidades = catalogo,
                ubicaciones = listOf("P-1"),
                alCancelar = { cancelado = true },
                alConfirmar = { descripcion, unidad, ubicacion, milesimas, observaciones ->
                    alta = listOf(descripcion, unidad, ubicacion, milesimas, observaciones)
                },
            )
        }
    }

    /** La ficha es más alta que la pantalla: hay que ir hasta el control. */
    private fun tocar(texto: String, parcial: Boolean = false) {
        compose.onNodeWithText(texto, substring = parcial).performScrollTo().performClick()
    }

    private fun escribirQueEs(que: String) {
        compose.onNodeWithText("¿Qué es?").performScrollTo().performTextInput(que)
    }

    @Test
    fun `muestra el codigo escaneado para poder confirmarlo`() {
        // El operario tiene que poder verificar que la app leyó el código que
        // él ve en la etiqueta, no el de la caja de al lado.
        abrir()

        compose.onNodeWithText("7790999", substring = true).assertExists()
    }

    @Test
    fun `sin descripcion no deja dar de alta`() {
        // Un artículo sin descripción es una fila que nadie va a poder
        // resolver después en el ERP.
        abrir()
        tocar("6")

        tocar("Dar de alta")

        assertNull(alta)
        compose.onNodeWithText("Escribí qué es el producto").assertExists()
    }

    @Test
    fun `una descripcion de solo espacios tampoco alcanza`() {
        // La barra espaciadora se aprieta sola en un bolsillo: una fila con
        // tres espacios por descripción es tan inútil como una vacía, y no la
        // atajaría una guarda que solo mire si el texto está vacío.
        abrir()
        escribirQueEs("   ")
        tocar("6")

        tocar("Dar de alta")

        assertNull(alta)
        compose.onNodeWithText("Escribí qué es el producto").assertExists()
    }

    @Test
    fun `da de alta con lo que cargo el operario`() {
        abrir()
        escribirQueEs("Pack por 6")
        tocar("6")

        tocar("Dar de alta")

        assertEquals(listOf("Pack por 6", "UN", null, 6000, null), alta)
    }

    @Test
    fun `los espacios de los costados no viajan en la descripcion`() {
        // Escribiendo apurado sobra un espacio al final, y esa descripción es
        // la que después se busca en el ERP.
        abrir()
        escribirQueEs("  Pack por 6  ")
        tocar("6")

        tocar("Dar de alta")

        assertEquals(listOf("Pack por 6", "UN", null, 6000, null), alta)
    }

    @Test
    fun `la unidad se puede cambiar y habilita los decimales`() {
        // Media unidad suele ser un error; medio kilo no.
        abrir()
        escribirQueEs("Harina suelta")
        // La unidad que se muestra tiene que ser la que se va a mandar: el
        // operario confirma lo que lee.
        compose.onNodeWithText("Unidad: UN").assertExists()
        tocar("Cambiar")
        // El botón del catálogo dibuja «Kilogramo (KG)».
        tocar("Kilogramo", parcial = true)
        tocar("3")
        tocar(",")
        tocar("5")

        tocar("Dar de alta")

        assertEquals(listOf("Harina suelta", "KG", null, 3500, null), alta)
    }

    @Test
    fun `sin cantidad no deja dar de alta`() {
        abrir()
        escribirQueEs("Pack por 6")

        tocar("Dar de alta")

        assertNull(alta)
    }

    @Test
    fun `en cero no se da de alta`() {
        // Nada se edita ni se borra, así que un alta en cero es un fantasma
        // permanente en el maestro del cliente y en la exportación. Y no hay
        // caso legítimo: el producto está en la mano del operario, que para
        // eso lo escaneó. En la ficha de un artículo del maestro el cero sí
        // vale —significa «acá no hay ninguno»—, pero eso es un dato del
        // inventario y esto sería inventar una fila.
        abrir()
        escribirQueEs("Pack por 6")
        tocar("0")

        tocar("Dar de alta")

        assertNull(alta)
        compose.onNodeWithText("Escribí cuántos hay: un producto nuevo no se da de alta en cero")
            .assertExists()
    }

    @Test
    fun `la cantidad tiene que ser una cantidad`() {
        // Una coma sola no es un número, y el alta no valida nada río abajo:
        // si pasa de acá, el conteo queda con una cantidad que nadie tecleó.
        abrir()
        escribirQueEs("Pack por 6")
        tocar(",")

        tocar("Dar de alta")

        assertNull(alta)
        compose.onNodeWithText("Escribí una cantidad, por ejemplo 24 o 3,5").assertExists()
    }

    @Test
    fun `un decimal en una unidad entera se pregunta antes de cargar`() {
        // Medio pack casi siempre es una coma de más, pero a veces el pack
        // está abierto: se pregunta, no se bloquea.
        abrir()
        escribirQueEs("Pack por 6")
        tocar("3")
        tocar(",")
        tocar("5")

        tocar("Dar de alta")

        assertNull(alta)
        compose.onNodeWithText("Esta unidad se cuenta entera. ¿Cargamos 3,5?").assertExists()
        compose.onNodeWithText("Sí, cargar").performClick()
        assertEquals(listOf("Pack por 6", "UN", null, 3500, null), alta)
    }

    @Test
    fun `sin catalogo de unidades manda la unidad que el servidor siempre tiene`() {
        // El celular puede quedarse sin catálogo si nunca sincronizó; «UN»
        // igual entra porque el servidor la siembra en el esquema y es su
        // propio valor por defecto para las altas.
        abrir(catalogo = emptyList())
        escribirQueEs("Pack por 6")
        tocar("6")

        tocar("Dar de alta")

        assertEquals(listOf("Pack por 6", "UN", null, 6000, null), alta)
    }

    @Test
    fun `lo que el operario escribe en observaciones viaja con el alta`() {
        // «Caja rota» es justo el dato que explica un conteo raro: si se
        // pierde en el camino, nadie se entera de que se perdió.
        abrir()
        escribirQueEs("Pack por 6")
        compose.onNodeWithText("Observaciones (opcional)")
            .performScrollTo()
            .performTextInput("Caja rota")
        tocar("6")

        tocar("Dar de alta")

        assertEquals(listOf("Pack por 6", "UN", null, 6000, "Caja rota"), alta)
    }

    @Test
    fun `cancelar cierra la ficha sin dar de alta nada`() {
        // La salida del operario que se dio cuenta de que el código estaba
        // mal leído: cancelar tiene que cancelar, no cargar.
        abrir()
        escribirQueEs("Pack por 6")
        tocar("6")

        tocar("Cancelar")

        assertNull(alta)
        assertTrue(cancelado)
    }

    @Test
    fun `la ubicacion elegida viaja con el alta`() {
        abrir()
        escribirQueEs("Pack por 6")
        tocar("Elegir")
        compose.onNodeWithText("P-1").performClick()
        tocar("6")

        tocar("Dar de alta")

        assertEquals(listOf("Pack por 6", "UN", "P-1", 6000, null), alta)
    }
}
