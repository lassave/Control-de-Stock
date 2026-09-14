package com.controldestock.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.controldestock.Hallazgo
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.textoDeBusqueda
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class DialogoBuscarProductoTest {

    @get:Rule
    val compose = createComposeRule()

    private val fideos = Hallazgo.Encontrado(
        ArticuloEntidad(
            id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
            unidad = "UN", pasadaNumero = 1, proyectoId = 1,
            busqueda = textoDeBusqueda("Fideos", "A-1", null),
        ),
        admiteDecimales = false, codigo = "A-1",
    )

    @Test
    fun `escribir dispara la busqueda con el texto tipeado`() {
        var buscado: String? = null
        compose.setContent {
            DialogoBuscarProducto(
                resultados = emptyList(),
                alCambiarTexto = { buscado = it },
                alElegir = {}, alIngresarAMano = {}, alCerrar = {},
            )
        }

        compose.onNodeWithText("SKU o descripción").performScrollTo().performTextInput("fide")

        assertEquals("fide", buscado)
    }

    @Test
    fun `muestra los resultados y tocar uno lo elige`() {
        var elegido: Hallazgo.Encontrado? = null
        compose.setContent {
            DialogoBuscarProducto(
                resultados = listOf(fideos),
                alCambiarTexto = {}, alElegir = { elegido = it },
                alIngresarAMano = {}, alCerrar = {},
            )
        }

        compose.onNodeWithText("A-1 — Fideos", substring = true).performClick()

        assertEquals(fideos, elegido)
    }

    @Test
    fun `sin resultados con texto tipeado ofrece ingresarlo a mano`() {
        var fueAMano = false
        compose.setContent {
            DialogoBuscarProducto(
                resultados = emptyList(),
                alCambiarTexto = {}, alElegir = {}, alIngresarAMano = { fueAMano = true },
                alCerrar = {},
            )
        }
        compose.onNodeWithText("SKU o descripción").performScrollTo().performTextInput("nada")

        compose.onNodeWithText("Ingresarlo a mano").performClick()

        assertTrue(fueAMano)
    }

    @Test
    fun `sin escribir nada todavia no ofrece ingresarlo a mano`() {
        compose.setContent {
            DialogoBuscarProducto(
                resultados = emptyList(),
                alCambiarTexto = {}, alElegir = {}, alIngresarAMano = {}, alCerrar = {},
            )
        }

        // No hay texto tipeado: no es que no se encontró nada, es que
        // todavía no se buscó nada.
        assertTrue(
            compose.onAllNodesWithText("Ingresarlo a mano").fetchSemanticsNodes().isEmpty(),
        )
    }
}
