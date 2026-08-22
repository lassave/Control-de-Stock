package com.controldestock.datos

import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class PreferenciasDeTemaTest {

    private val contexto = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Test
    fun `sin nada guardado todavia devuelve null`() {
        val preferencias = PreferenciasDeTema(contexto)

        assertNull(preferencias.leer())
    }

    @Test
    fun `lo guardado se puede volver a leer`() {
        val preferencias = PreferenciasDeTema(contexto)

        preferencias.guardar(oscuro = true)

        assertEquals(true, preferencias.leer())
    }

    @Test
    fun `queda guardado entre instancias distintas, no solo en memoria`() {
        PreferenciasDeTema(contexto).guardar(oscuro = false)

        // Una instancia nueva simula reabrir la app: si esto no lee lo que
        // guardó la anterior, la preferencia no sobrevive un reinicio.
        assertEquals(false, PreferenciasDeTema(contexto).leer())
    }
}
