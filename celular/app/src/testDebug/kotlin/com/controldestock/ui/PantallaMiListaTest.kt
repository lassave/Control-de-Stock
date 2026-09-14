package com.controldestock.ui

import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToNode
import com.controldestock.nucleo.RenglonAsignado
import com.controldestock.nucleo.UbicacionAsignada
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PantallaMiListaTest {

    @get:Rule
    val compose = createComposeRule()

    /**
     * Trae hasta la vista un nodo que `LazyColumn` todavía no compuso: en la
     * ventana chica de un test, cualquier renglón queda más allá del margen
     * que Compose prepara de más, y ni `performScrollTo()` lo encuentra para
     * poder desplazarse — hace falta pedirle a la lista misma que se
     * desplace hasta él.
     */
    private fun scrollHasta(texto: String, substring: Boolean = false) {
        compose.onNodeWithTag("lista-de-productos")
            .performScrollToNode(hasText(texto, substring = substring))
    }

    private fun renglon(
        idOrden: Int, sku: String, contado: Int? = null,
        articuloId: Int = idOrden, agregado: Boolean = false,
    ) = RenglonAsignado(
        idOrden = idOrden, sku = sku, descripcion = "Producto $sku",
        codigos = sku, unidad = "UN", contado = contado,
        articuloId = articuloId, agregado = agregado,
    )

    private fun montar(
        ubicaciones: List<UbicacionAsignada> = emptyList(),
        pasada: String = "Conteo 1",
        operario: String = "Juan",
        actualizando: Boolean = false,
        avisoDeActualizacion: String? = null,
        pendientes: Int = 0,
        estadoDeSubida: EstadoDeSubida = EstadoDeSubida.Quieto,
        oscuro: Boolean = false,
        version: String = "v2026-08-21 (build 223)",
        alActualizar: () -> Unit = {},
        alSubir: () -> Unit = {},
        alContar: () -> Unit = {},
        alCambiarTema: () -> Unit = {},
        alTocarProducto: (Int) -> Unit = {},
        alIdentificarse: () -> Unit = {},
    ) {
        compose.setContent {
            PantallaMiLista(
                ubicaciones = ubicaciones,
                pasada = pasada,
                operario = operario,
                actualizando = actualizando,
                avisoDeActualizacion = avisoDeActualizacion,
                pendientes = pendientes,
                estadoDeSubida = estadoDeSubida,
                oscuro = oscuro,
                version = version,
                alActualizar = alActualizar,
                alSubir = alSubir,
                alContar = alContar,
                alCambiarTema = alCambiarTema,
                alTocarProducto = alTocarProducto,
                alIdentificarse = alIdentificarse,
            )
        }
    }

    @Test
    fun `el titulo es Productos asignados, con la etiqueta Inventario arriba`() {
        montar()

        compose.onNodeWithText("INVENTARIO").assertIsDisplayed()
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
        compose.onNodeWithText("+").assertIsEnabled()
        compose.onNodeWithText("+").performClick()

        assertTrue(conto)
    }

    @Test
    fun `la tarjeta de ubicacion muestra el nombre y el resumen numerico`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-3", (1..40).map {
                    renglon(it, "SKU$it", contado = if (it <= 12) 1000 else null)
                }),
            ),
        )

        // Con scroll: la fila nueva de operario/Cambiar en el encabezado
        // achica lo que le queda a la lista en la ventana chica del test.
        scrollHasta("UBICACIÓN ASIGNADA:")
        compose.onNodeWithText("UBICACIÓN ASIGNADA:").assertIsDisplayed()
        compose.onNodeWithText("P-3").assertIsDisplayed()
        scrollHasta("40")
        compose.onNodeWithText("40").assertIsDisplayed() // total
        compose.onNodeWithText("12").assertIsDisplayed() // contados
        compose.onNodeWithText("28").assertIsDisplayed() // sin contar
    }

    @Test
    fun `el listado de productos muestra el ID y el SKU de cada renglon`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(idOrden = 7, sku = "A-1"))),
            ),
        )

        compose.onNodeWithText("LISTADO DE PRODUCTOS").assertIsDisplayed()
        scrollHasta("ID: 007 | SKU: A-1", substring = true)
        compose.onNodeWithText("ID: 007 | SKU: A-1", substring = true).assertIsDisplayed()
    }

    @Test
    fun `un articulo contado muestra la etiqueta CONTADO y la cantidad`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A", contado = 5000))),
            ),
        )

        // Con scroll: en una ventana chica el renglón queda debajo de la
        // tarjeta y de la etiqueta de la pasada, igual que en un celular real
        // con poco alto disponible.
        scrollHasta("CONTADO")
        compose.onNodeWithText("CONTADO").assertIsDisplayed()
        compose.onNodeWithText("5 UN", substring = true).assertIsDisplayed()
    }

    @Test
    fun `un articulo pendiente muestra la etiqueta PENDIENTE sin ninguna cantidad`() {
        // Regla dura: el celular no puede insinuar el stock del sistema. Un
        // pendiente no tiene cantidad propia todavía, solo un guion junto a
        // la unidad — nunca un número, ni el que cargó el operario, porque no
        // cargó nada.
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A"))),
            ),
        )

        scrollHasta("PENDIENTE")
        compose.onNodeWithText("PENDIENTE").assertIsDisplayed()
        compose.onNodeWithText("- UN", substring = true).assertIsDisplayed()
    }

    @Test
    fun `la flecha de la ubicacion colapsa y expande su lista`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A"))),
            ),
        )

        scrollHasta("PENDIENTE")
        compose.onNodeWithText("PENDIENTE").assertIsDisplayed()

        // La flecha quedó fuera de vista al desplazarse hasta el renglón:
        // hay que volver a buscarla antes de tocarla.
        scrollHasta("▾")
        compose.onNodeWithText("▾").performClick()
        compose.onAllNodesWithText("PENDIENTE").assertCountEquals(0)

        scrollHasta("▸")
        compose.onNodeWithText("▸").performClick()
        scrollHasta("PENDIENTE")
        compose.onNodeWithText("PENDIENTE").assertIsDisplayed()
    }

    @Test
    fun `el boton actualizar llama a lo suyo`() {
        var actualizo = false
        montar(alActualizar = { actualizo = true })

        compose.onNodeWithText("ACTUALIZAR").performClick()

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

    @Test
    fun `el boton de tema muestra la luna en oscuro y llama al cambio`() {
        var cambio = false
        montar(oscuro = true, alCambiarTema = { cambio = true })

        compose.onNodeWithText("🌙").assertIsDisplayed()
        compose.onNodeWithText("🌙").performClick()

        assertTrue(cambio)
    }

    @Test
    fun `el boton de tema muestra el sol en claro`() {
        montar(oscuro = false)

        compose.onNodeWithText("☀️").assertIsDisplayed()
    }

    @Test
    fun `el pie de pagina muestra la version instalada`() {
        montar(version = "v2026-08-21 (build 223)")

        compose.onNodeWithText("v2026-08-21 (build 223)").assertIsDisplayed()
    }

    @Test
    fun `el nombre del operario se muestra en el encabezado`() {
        montar(operario = "María")

        compose.onNodeWithText("María").assertIsDisplayed()
    }

    @Test
    fun `el boton Cambiar llama a alIdentificarse`() {
        var identificando = false
        montar(alIdentificarse = { identificando = true })

        compose.onNodeWithText("Cambiar").performClick()

        assertTrue(identificando)
    }

    @Test
    fun `tocar la tarjeta de un producto llama a alTocarProducto con su id`() {
        var tocado: Int? = null
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A-1", articuloId = 42))),
            ),
            alTocarProducto = { tocado = it },
        )

        scrollHasta("ID: 001 | SKU: A-1", substring = true)
        compose.onNodeWithText("ID: 001 | SKU: A-1", substring = true).performClick()

        assertEquals(42, tocado)
    }

    @Test
    fun `un producto agregado muestra la etiqueta AGREGADO`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A", agregado = true))),
            ),
        )

        scrollHasta("AGREGADO")
        compose.onNodeWithText("AGREGADO").assertIsDisplayed()
    }

    @Test
    fun `un producto del maestro original no muestra AGREGADO`() {
        montar(
            ubicaciones = listOf(
                UbicacionAsignada("P-1", listOf(renglon(1, "A"))),
            ),
        )

        scrollHasta("PENDIENTE")
        compose.onAllNodesWithText("AGREGADO").assertCountEquals(0)
    }
}
