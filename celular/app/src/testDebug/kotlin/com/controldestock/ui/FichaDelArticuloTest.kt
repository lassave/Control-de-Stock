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

    private fun abrirFicha() {
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos,
                admiteDecimales = false,
                ubicaciones = emptyList(),
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
}
