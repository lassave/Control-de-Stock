package com.controldestock.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.Text
import androidx.compose.ui.test.assertIsDisplayed
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
                camara = { _, _ -> },
            ) {}
        }

        compose.onNodeWithText(aviso).assertIsDisplayed()
        compose.onNodeWithText("Darlo de alta").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `con la ficha abierta la camara deja de avisar lecturas`() {
        val activo = mutableListOf<Boolean>()
        compose.setContent {
            PantallaEscaneo(
                operario = "Ana",
                pasada = "Pasada 1",
                pendientes = 0,
                fichaAbierta = true,
                avisoDeDesconocido = null,
                alDarDeAlta = null,
                alLeer = {},
                camara = { esta, _ -> activo += esta },
            ) {
                Box { Text("La ficha") }
            }
        }

        compose.onNodeWithText("La ficha").assertIsDisplayed()
        assertEquals(listOf(false), activo)
    }
}
