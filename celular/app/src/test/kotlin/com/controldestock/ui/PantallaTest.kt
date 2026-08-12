package com.controldestock.ui

import com.controldestock.datos.VinculacionEntidad
import org.junit.Assert.assertEquals
import org.junit.Test

class PantallaTest {

    private val vinculacion = VinculacionEntidad(
        url = "http://172.16.11.12:8000", token = "abc",
        operarioId = 1, operarioNombre = "Juan",
        sesionId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
    )

    @Test
    fun `sin vincular va a la pantalla de vinculacion`() {
        assertEquals(Pantalla.Vinculando, pantallaSegun(null))
    }

    @Test
    fun `vinculado va derecho a escanear`() {
        // El operario abre la app para contar, no para ver un menú: la cámara
        // tiene que estar lista sin tocar nada.
        assertEquals(Pantalla.Escaneando, pantallaSegun(vinculacion))
    }
}
