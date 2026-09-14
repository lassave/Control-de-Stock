package com.controldestock.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.controldestock.nucleo.OperarioParaIdentificar
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class DialogoIdentificarseTest {

    @get:Rule
    val compose = createComposeRule()

    private val juan = OperarioParaIdentificar(1, "Juan", tienePin = false)
    private val ana = OperarioParaIdentificar(2, "Ana", tienePin = true)

    @Test
    fun `tocar un operario sin pin identifica directo`() {
        var elegido: Pair<String, String?>? = null
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(juan), cargando = false, error = null,
                alElegir = { nombre, pin -> elegido = nombre to pin }, alCerrar = {},
            )
        }

        compose.onNodeWithText("Juan").performClick()

        assertEquals("Juan" to null, elegido)
    }

    @Test
    fun `tocar un operario con pin pide el pin antes de entrar`() {
        var elegido: Pair<String, String?>? = null
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(ana), cargando = false, error = null,
                alElegir = { nombre, pin -> elegido = nombre to pin }, alCerrar = {},
            )
        }

        compose.onNodeWithText("Ana").performClick()
        compose.onNodeWithText("PIN").performScrollTo().performTextInput("1234")
        compose.onNodeWithText("Entrar").performClick()

        assertEquals("Ana" to "1234", elegido)
    }

    @Test
    fun `mientras carga no muestra ningun nombre`() {
        compose.setContent {
            DialogoIdentificarse(
                operarios = emptyList(), cargando = true, error = null,
                alElegir = { _, _ -> }, alCerrar = {},
            )
        }

        compose.onNodeWithText("Cargando…").assertIsDisplayed()
    }

    @Test
    fun `un error se muestra`() {
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(juan), cargando = false, error = "El PIN no coincide",
                alElegir = { _, _ -> }, alCerrar = {},
            )
        }

        compose.onNodeWithText("El PIN no coincide").assertIsDisplayed()
    }

    @Test
    fun `cancelar avisa`() {
        var cancelado = false
        compose.setContent {
            DialogoIdentificarse(
                operarios = listOf(juan), cargando = false, error = null,
                alElegir = { _, _ -> }, alCerrar = { cancelado = true },
            )
        }

        compose.onNodeWithText("Cancelar").performClick()

        assertTrue(cancelado)
    }
}
