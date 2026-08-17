package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.controldestock.nucleo.RenglonAsignado
import com.controldestock.nucleo.UbicacionAsignada
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PantallaMiListaTest {

    @get:Rule
    val compose = createComposeRule()

    private fun renglon(sku: String, contado: Int? = null) = RenglonAsignado(
        idOrden = 1, sku = sku, descripcion = "Producto $sku",
        codigos = sku, unidad = "UN", contado = contado,
    )

    @Test
    fun `sin ubicaciones asignadas muestra el cartel y el boton de contar sigue andando`() {
        var conto = false
        compose.setContent {
            PantallaMiLista(
                ubicaciones = emptyList(),
                actualizando = false,
                avisoDeActualizacion = null,
                alActualizar = {},
                alContar = { conto = true },
            )
        }

        compose.onNodeWithText("Todavía no te asignaron ninguna ubicación").assertIsDisplayed()
        compose.onNodeWithText("Contar").assertIsEnabled()
        compose.onNodeWithText("Contar").performClick()

        assertTrue(conto)
    }

    @Test
    fun `el tilde aparece solo en los articulos contados`() {
        compose.setContent {
            PantallaMiLista(
                ubicaciones = listOf(
                    UbicacionAsignada("P-1", listOf(renglon("A", contado = 5000), renglon("B"))),
                ),
                actualizando = false,
                avisoDeActualizacion = null,
                alActualizar = {},
                alContar = {},
            )
        }

        compose.onNodeWithText("✓ 5", substring = true).assertIsDisplayed()
    }

    @Test
    fun `muestra el avance de cada ubicacion`() {
        compose.setContent {
            PantallaMiLista(
                ubicaciones = listOf(
                    UbicacionAsignada("P-3", (1..40).map {
                        renglon("SKU$it", contado = if (it <= 12) 1000 else null)
                    }),
                ),
                actualizando = false,
                avisoDeActualizacion = null,
                alActualizar = {},
                alContar = {},
            )
        }

        compose.onNodeWithText("P-3 — 12 de 40").assertIsDisplayed()
    }

    @Test
    fun `el boton actualizar llama a lo suyo`() {
        var actualizo = false
        compose.setContent {
            PantallaMiLista(
                ubicaciones = emptyList(),
                actualizando = false,
                avisoDeActualizacion = null,
                alActualizar = { actualizo = true },
                alContar = {},
            )
        }

        compose.onNodeWithText("Actualizar").performClick()

        assertTrue(actualizo)
    }

    @Test
    fun `el aviso de actualizacion se muestra cuando hay uno`() {
        compose.setContent {
            PantallaMiLista(
                ubicaciones = emptyList(),
                actualizando = false,
                avisoDeActualizacion = "No se pudo actualizar. Se muestra la última lista que bajó.",
                alActualizar = {},
                alContar = {},
            )
        }

        compose.onNodeWithText(
            "No se pudo actualizar. Se muestra la última lista que bajó.",
        ).assertIsDisplayed()
    }
}
