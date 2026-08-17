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

    private fun montar(
        ubicaciones: List<UbicacionAsignada> = emptyList(),
        actualizando: Boolean = false,
        avisoDeActualizacion: String? = null,
        pendientes: Int = 0,
        estadoDeSubida: EstadoDeSubida = EstadoDeSubida.Quieto,
        alActualizar: () -> Unit = {},
        alSubir: () -> Unit = {},
        alContar: () -> Unit = {},
    ) {
        compose.setContent {
            PantallaMiLista(
                ubicaciones = ubicaciones,
                actualizando = actualizando,
                avisoDeActualizacion = avisoDeActualizacion,
                pendientes = pendientes,
                estadoDeSubida = estadoDeSubida,
                alActualizar = alActualizar,
                alSubir = alSubir,
                alContar = alContar,
            )
        }
    }

    @Test
    fun `el titulo es Productos asignados`() {
        montar()

        compose.onNodeWithText("PRODUCTOS ASIGNADOS").assertIsDisplayed()
    }

    @Test
    fun `sin ubicaciones asignadas muestra el cartel y el boton de contar sigue andando`() {
        var conto = false
        montar(alContar = { conto = true })

        compose.onNodeWithText("Todavía no te asignaron ninguna ubicación").assertIsDisplayed()
        compose.onNodeWithText("Contar").assertIsEnabled()
        compose.onNodeWithText("Contar").performClick()

        assertTrue(conto)
    }

    @Test
    fun `el tilde aparece solo en los articulos contados`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon("A", contado = 5000), renglon("B"))),
            ),
        )

        compose.onNodeWithText("✓ 5", substring = true).assertIsDisplayed()
    }

    @Test
    fun `muestra el avance de cada ubicacion con el rotulo Ubicacion`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-3", (1..40).map {
                    renglon("SKU$it", contado = if (it <= 12) 1000 else null)
                }),
            ),
        )

        compose.onNodeWithText("Ubicación: P-3 — 12 de 40").assertIsDisplayed()
    }

    @Test
    fun `el boton actualizar llama a lo suyo`() {
        var actualizo = false
        montar(alActualizar = { actualizo = true })

        compose.onNodeWithText("Actualizar").performClick()

        assertTrue(actualizo)
    }

    @Test
    fun `el aviso de actualizacion se muestra cuando hay uno`() {
        montar(avisoDeActualizacion = "No se pudo actualizar. Se muestra la última lista que bajó.")

        compose.onNodeWithText(
            "No se pudo actualizar. Se muestra la última lista que bajó.",
        ).assertIsDisplayed()
    }

    @Test
    fun `el indicador de pendientes se muestra al lado de actualizar`() {
        montar(pendientes = 3)

        compose.onNodeWithText("3 sin subir").assertIsDisplayed()
    }

    @Test
    fun `tocar el indicador de pendientes fuerza la subida`() {
        var subio = false
        montar(pendientes = 3, alSubir = { subio = true })

        compose.onNodeWithText("3 sin subir").performClick()

        assertTrue(subio)
    }
}
