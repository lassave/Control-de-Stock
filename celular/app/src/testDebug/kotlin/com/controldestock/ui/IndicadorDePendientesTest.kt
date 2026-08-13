package com.controldestock.ui

import androidx.compose.ui.test.assertHasClickAction
import androidx.compose.ui.test.assertHasNoClickAction
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
 * El indicador del encabezado, que además de informar resuelve.
 *
 * Vive en `testDebug` por lo mismo que las otras pruebas de pantalla:
 * necesitan una actividad que aporta `ui-test-manifest`, que es dependencia
 * de debug, y desde `src/test` el archivo correría también contra release,
 * donde esa actividad no existe.
 */
@RunWith(RobolectricTestRunner::class)
class IndicadorDePendientesTest {

    @get:Rule
    val compose = createComposeRule()

    private var subio = false

    private fun montar(pendientes: Int, estado: EstadoDeSubida) {
        compose.setContent {
            IndicadorDePendientes(
                pendientes = pendientes,
                estado = estado,
                alSubir = { subio = true },
            )
        }
    }

    @Test
    fun `sin nada pendiente avisa que esta al dia y no se toca`() {
        montar(pendientes = 0, estado = EstadoDeSubida.Quieto)

        compose.onNodeWithText("Todo al día").assertIsDisplayed()
        compose.onNodeWithText("Todo al día").assertHasNoClickAction()
    }

    @Test
    fun `con pendientes dice cuantos y sube al tocarlo`() {
        // Es el lugar donde el operario ya mira para saber si le falta algo:
        // que sea también donde toca para resolverlo le ahorra una pantalla.
        montar(pendientes = 3, estado = EstadoDeSubida.Quieto)

        compose.onNodeWithText("3 sin subir").assertHasClickAction()
        compose.onNodeWithText("3 sin subir").performClick()

        assertTrue(subio)
    }

    @Test
    fun `mientras sube lo dice y no se puede volver a tocar`() {
        montar(pendientes = 3, estado = EstadoDeSubida.Subiendo)

        compose.onNodeWithText("Subiendo…").assertIsDisplayed()
        compose.onNodeWithText("Subiendo…").assertHasNoClickAction()
    }

    @Test
    fun `si no pudo lo dice y se puede reintentar`() {
        // Sin esto el operario no tiene forma de saber que su intento falló,
        // ni de volver a intentarlo sin inventarse un escaneo.
        montar(pendientes = 3, estado = EstadoDeSubida.NoPudo)

        compose.onNodeWithText("No se pudo subir").assertHasClickAction()
        compose.onNodeWithText("No se pudo subir").performClick()

        assertTrue(subio)
    }

    @Test
    fun `no pudo se muestra aunque el contador quede en cero`() {
        // Puede pasar: sube todo menos un alta rechazada. Decir «Todo al día»
        // ahí sería mentirle.
        montar(pendientes = 0, estado = EstadoDeSubida.NoPudo)

        compose.onNodeWithText("No se pudo subir").assertIsDisplayed()
    }
}
