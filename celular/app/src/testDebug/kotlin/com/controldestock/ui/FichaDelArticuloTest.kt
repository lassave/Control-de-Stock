package com.controldestock.ui

import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onLast
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.EventoConteo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Vive en `testDebug` y no en `test` a propósito.
 *
 * Probar una pantalla necesita una actividad que aporta `ui-test-manifest`,
 * y eso es andamiaje que no puede viajar en el APK que se instala en el
 * depósito. Desde `test`, el mismo archivo corre también contra release,
 * donde esa actividad no existe, y la suite se cae sin que nada esté mal.
 */
@RunWith(RobolectricTestRunner::class)
class FichaDelArticuloTest {

    @get:Rule
    val compose = createComposeRule()

    private val tornillos = ArticuloEntidad(
        id = 1, idOrden = 1, sku = "A-1", descripcion = "Tornillos",
        unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
        busqueda = textoDeBusqueda("Tornillos", "A-1", "P-1"),
    )

    private val pregunta = "Esta unidad se cuenta entera. ¿Cargamos 3,5?"

    private val yaContado = listOf(
        ConteoLocal(
            EventoConteo(
                uuid = "uuid-1", codigo = "7790001", cantidad = 24000,
                timestampDispositivo = "2026-08-12T13:32:00Z",
            ),
        ),
    )

    private fun abrirFicha() {
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos,
                admiteDecimales = false,
                ubicaciones = emptyList(),
                previos = emptyList(),
                alCancelar = {},
                alConfirmar = { _, _, _ -> },
            )
        }
    }

    private fun abrirFichaConteada() {
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos,
                admiteDecimales = false,
                ubicaciones = listOf("P-1", "P-9"),
                previos = yaContado,
                alCancelar = {},
                alConfirmar = { _, _, _ -> },
            )
        }
    }

    /** La ficha es más alta que la pantalla: hay que ir hasta la tecla. */
    private fun tocar(texto: String) {
        compose.onNodeWithText(texto).performScrollTo().performClick()
    }

    private fun teclear(vararg teclas: String) = teclas.forEach { tocar(it) }

    @Test
    fun `la pregunta por el decimal se hace una sola vez`() {
        // Repetida arriba y abajo se lee como dos problemas distintos, y el
        // operario está apurado: la pregunta es una, y la contesta en el
        // cartel.
        abrirFicha()
        teclear("3", ",", "5")

        tocar("Confirmar")

        compose.onAllNodesWithText(pregunta).assertCountEquals(1)
    }

    @Test
    fun `al volver a corregir la pregunta no queda colgada`() {
        // Quien elige corregir ya contestó: dejarle el texto en rojo debajo
        // del teclado lo hace buscar un error que no existe.
        abrirFicha()
        teclear("3", ",", "5")
        tocar("Confirmar")

        compose.onAllNodesWithText("Corregir").onLast().performClick()

        compose.onAllNodesWithText(pregunta).assertCountEquals(0)
    }

    @Test
    fun `avisa cuando ese producto ya se conto en esa ubicacion`() {
        // Un SKU se cuenta una sola vez por ubicación: el segundo escaneo en
        // el mismo estante es que el operario perdió la cuenta.
        abrirFichaConteada()
        teclear("6")

        tocar("Confirmar")

        compose.onNodeWithText("¿Ya lo contaste acá?").assertExists()
    }

    @Test
    fun `el aviso dice cuanto y cuando se cargo`() {
        abrirFichaConteada()
        teclear("6")

        tocar("Confirmar")

        compose.onNodeWithText("Ya cargaste 24 UN", substring = true).assertExists()
    }

    @Test
    fun `cargar igual registra el conteo`() {
        // Si el estante tenía dos pallets separados, el operario sabe más que
        // la regla.
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = yaContado,
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("6")
        tocar("Confirmar")

        compose.onNodeWithText("Cargar igual").performClick()

        assertEquals(6000, cargado)
    }

    @Test
    fun `cancelar el aviso no registra nada y deja la ficha abierta`() {
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = yaContado,
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("6")
        tocar("Confirmar")

        compose.onAllNodesWithText("Cancelar").onLast().performClick()

        assertNull(cargado)
        compose.onNodeWithText("6 UN").assertExists()
    }

    @Test
    fun `sin conteos previos confirma derecho`() {
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = emptyList(),
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("6")

        tocar("Confirmar")

        assertEquals(6000, cargado)
    }

    @Test
    fun `corregir a otra ubicacion no dispara el aviso`() {
        // El mismo producto sí puede estar en dos estantes, y ahí los conteos
        // suman: avisar sería enseñarle al operario a ignorar el cartel.
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = listOf("P-1", "P-9"), previos = yaContado,
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        tocar("Corregir")
        compose.onNodeWithText("P-9").performClick()
        teclear("6")

        tocar("Confirmar")

        assertEquals(6000, cargado)
    }

    @Test
    fun `el decimal se pregunta antes que el repetido`() {
        // Dos preguntas a la vez no se entienden, y la cantidad tiene que
        // estar resuelta para poder decir cuánto se está sumando.
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = yaContado,
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("3", ",", "5")
        tocar("Confirmar")
        compose.onNodeWithText(pregunta).assertExists()

        compose.onNodeWithText("Sí, cargar").performClick()

        compose.onNodeWithText("¿Ya lo contaste acá?").assertExists()
        assertNull(cargado)
        compose.onNodeWithText("Cargar igual").performClick()
        assertEquals(3500, cargado)
    }
}
