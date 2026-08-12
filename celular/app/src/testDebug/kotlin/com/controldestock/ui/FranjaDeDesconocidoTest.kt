package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * La franja se prueba aparte de `PantallaEscaneo` porque esa pantalla monta
 * la cámara, y CameraX no arranca sin celular.
 *
 * Es el único camino de entrada al alta: si un refactor se lleva puesto el
 * botón, la ficha del alta queda inalcanzable y cada código desconocido del
 * depósito termina sin registrarse, con toda la pantalla escrita y probada.
 */
@RunWith(RobolectricTestRunner::class)
class FranjaDeDesconocidoTest {

    @get:Rule
    val compose = createComposeRule()

    private val aviso = "Este código no está en el conteo: 7790999"

    @Test
    fun `con el codigo desconocido ofrece darlo de alta`() {
        var abrio = false
        compose.setContent { FranjaDeDesconocido(aviso = aviso, alDarDeAlta = { abrio = true }) }

        compose.onNodeWithText(aviso).assertIsDisplayed()
        compose.onNodeWithText("Darlo de alta").performClick()

        assertTrue(abrio)
    }

    @Test
    fun `sin a donde ir avisa igual pero sin boton`() {
        // El aviso solo también sirve: le dice al operario que ese código no
        // se contó. Lo que no puede pasar es ofrecer un botón que no lleva a
        // ningún lado.
        compose.setContent { FranjaDeDesconocido(aviso = aviso, alDarDeAlta = null) }

        compose.onNodeWithText(aviso).assertIsDisplayed()

        compose.onNodeWithText("Darlo de alta").assertDoesNotExist()
    }
}
