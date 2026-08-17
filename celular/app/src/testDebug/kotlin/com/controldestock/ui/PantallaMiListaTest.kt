package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
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
        pasada: String = "Conteo 1",
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
                pasada = pasada,
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
    fun `la etiqueta de la pasada activa se muestra bajo el titulo`() {
        montar(pasada = "Conteo 2")

        compose.onNodeWithText("Conteo 2").assertIsDisplayed()
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
    fun `la tarjeta de ubicacion muestra el nombre y el resumen numerico`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-3", (1..40).map {
                    renglon("SKU$it", contado = if (it <= 12) 1000 else null)
                }),
            ),
        )

        compose.onNodeWithText("UBICACIÓN ASIGNADA").assertIsDisplayed()
        compose.onNodeWithText("P-3").assertIsDisplayed()
        compose.onNodeWithText("40").assertIsDisplayed() // total
        compose.onNodeWithText("12").assertIsDisplayed() // contados
        compose.onNodeWithText("28").assertIsDisplayed() // sin contar
    }

    @Test
    fun `un articulo contado muestra la etiqueta CONTADO y la cantidad`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon("A", contado = 5000))),
            ),
        )

        // Con scroll: en una ventana chica el renglón queda debajo de la
        // tarjeta y de la etiqueta de la pasada, igual que en un celular real
        // con poco alto disponible. `performScrollTo` es lo mismo que haría
        // el dedo del operario.
        compose.onNodeWithText("CONTADO").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("5 UN", substring = true).performScrollTo().assertIsDisplayed()
    }

    @Test
    fun `un articulo pendiente muestra la etiqueta PENDIENTE sin ninguna cantidad`() {
        // Regla dura: el celular no puede insinuar el stock del sistema. Un
        // pendiente no tiene cantidad propia todavía, así que no se muestra
        // ningún número — ni el que cargó el operario, porque no cargó nada.
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon("A"))),
            ),
        )

        compose.onNodeWithText("PENDIENTE").assertIsDisplayed()
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
    fun `el indicador de pendientes se muestra en la franja inferior`() {
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
