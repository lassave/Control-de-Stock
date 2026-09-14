package com.controldestock.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.Text
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * La pantalla con una cámara de mentira en lugar de CameraX, que no arranca
 * sin celular.
 *
 * Lo que se prueba acá es el cableado que la pantalla decide y nadie más
 * puede decidir por ella: que el botón de la franja lleve al alta —es el
 * único camino de entrada, y si se corta cada código desconocido del depósito
 * se pierde— y que el escaneo se pause mientras hay una ficha abierta, que es
 * lo que evita que el mismo código se cuente veinte veces.
 */
@RunWith(RobolectricTestRunner::class)
class PantallaEscaneoTest {

    @get:Rule
    val compose = createComposeRule()

    private val aviso = "Este código no está en el conteo: 7790999"

    @Test
    fun `el boton de la franja lleva al alta`() {
        var abrio = false
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = false,
                avisoDeDesconocido = aviso,
                alDarDeAlta = { abrio = true },
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = true,
                alIngresarAMano = {},
                puedeBuscar = true,
                alBuscar = {},
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText(aviso).assertIsDisplayed()
        compose.onNodeWithText("Darlo de alta").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `con la ficha abierta la camara deja de avisar lecturas`() {
        val activo = montarConFicha(abierta = true)

        compose.onNodeWithText("La ficha").assertIsDisplayed()
        assertTrue("la cámara siguió leyendo: $activo", activo.none { it })
    }

    @Test
    fun `sin ninguna ficha abierta la camara lee`() {
        // La otra dirección: apagarla siempre es el modo de falla peor de
        // todos, porque el operario apunta y no pasa nada.
        val activo = montarConFicha(abierta = false)

        assertTrue("la cámara quedó apagada: $activo", activo.all { it })
    }

    /** Cómo quedó `activo` en cada composición de la cámara. */
    private fun montarConFicha(abierta: Boolean): List<Boolean> {
        val activo = mutableListOf<Boolean>()
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = abierta,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = true,
                alIngresarAMano = {},
                puedeBuscar = true,
                alBuscar = {},
                alVolver = {},
                camara = { esta, _ -> activo += esta },
            ) {
                Box { Text("La ficha") }
            }
        }
        // Que se haya compuesto una sola vez no es una regla de nada: lo que
        // importa es que ninguna composición la haya dejado del lado que no
        // corresponde.
        assertTrue("la cámara no se compuso nunca", activo.isNotEmpty())
        return activo
    }

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
                puedeBuscar = true,
                alBuscar = {},
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("A mano").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `un nombre de operario largo no tapa el boton a mano`() {
        // Deuda anotada antes de esta pantalla: el encabezado sin peso podía
        // empujar «A mano» —el único camino al ingreso manual— fuera de la
        // pantalla. La izquierda ahora se achica primero.
        compose.setContent {
            PantallaEscaneo(
                operario = "María de los Ángeles Fernández Etchegaray de la Torre",
                pasada = "Conteo 1",
                pendientes = 0,
                fichaAbierta = false,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                estadoDeSubida = EstadoDeSubida.Quieto,
                alSubir = {},
                puedeIngresarAMano = true,
                alIngresarAMano = {},
                puedeBuscar = true,
                alBuscar = {},
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("A mano").assertIsDisplayed()
        compose.onNodeWithText("A mano").assertIsEnabled()
    }

    @Test
    fun `la flecha vuelve a la lista`() {
        var volvio = false
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
                alIngresarAMano = {},
                puedeBuscar = true,
                alBuscar = {},
                alVolver = { volvio = true },
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("←").performClick()

        assertTrue(volvio)
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
                puedeBuscar = true,
                alBuscar = {},
                alVolver = {},
                camara = { _, _ -> },
            ) { }
        }

        compose.onNodeWithText("A mano").assertIsNotEnabled()
    }

    @Test
    fun `el boton de buscar llama al callback cuando esta habilitado`() {
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
                alIngresarAMano = {},
                puedeBuscar = true,
                alBuscar = { abrio = true },
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("Buscar").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `el boton de buscar queda deshabilitado con algo mas abierto`() {
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
                puedeBuscar = false,
                alBuscar = {},
                alVolver = {},
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText("Buscar").assertIsNotEnabled()
    }
}
