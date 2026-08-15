package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
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
 * Vive en `testDebug` y no en `test`: el `AlertDialog` de Compose necesita
 * `ui-test-manifest`, que es dependencia solo de `debug`. Ver el comentario
 * de la misma clase en `PantallaEscaneoTest.kt`.
 */
@RunWith(RobolectricTestRunner::class)
class DialogoCodigoAManoTest {

    @get:Rule
    val compose = createComposeRule()

    @Test
    fun `tocar digitos arma el texto`() {
        // Tres dígitos distintos y sin volver a tocar ninguno: en cuanto el
        // visor muestra un dígito, ese mismo texto coincide también con su
        // tecla, y `onNodeWithText` no puede elegir entre los dos si se lo
        // vuelve a pedir.
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("1").performClick()
        compose.onNodeWithText("2").performClick()
        compose.onNodeWithText("3").performClick()

        compose.onNodeWithText("123").assertIsDisplayed()
    }

    @Test
    fun `C vacia lo tipeado`() {
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("1").performClick()
        compose.onNodeWithText("C").performClick()

        compose.onNodeWithText("…").assertIsDisplayed()
    }

    @Test
    fun `la coma no hace nada`() {
        // Un código de barras no lleva decimales.
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("1").performClick()
        compose.onNodeWithText("2").performClick()
        compose.onNodeWithText(",").performClick()

        compose.onNodeWithText("12").assertIsDisplayed()
    }

    @Test
    fun `confirmar esta deshabilitado con el campo vacio`() {
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = {})
        }

        compose.onNodeWithText("Confirmar").assertIsNotEnabled()
    }

    @Test
    fun `confirmar con texto avisa con lo tipeado`() {
        var confirmado: String? = null
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = { confirmado = it }, alCancelar = {})
        }

        compose.onNodeWithText("7").performClick()
        compose.onNodeWithText("9").performClick()
        compose.onNodeWithText("Confirmar").performClick()

        assertEquals("79", confirmado)
    }

    @Test
    fun `cancelar avisa sin tipear nada`() {
        var cancelado = false
        compose.setContent {
            DialogoCodigoAMano(alConfirmar = {}, alCancelar = { cancelado = true })
        }

        compose.onNodeWithText("Cancelar").performClick()

        assertTrue(cancelado)
    }
}
