package com.controldestock.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TemaTest {

    @Test
    fun `sin preferencia guardada usa el tema del sistema`() {
        assertTrue(esOscuro(preferencia = null, sistemaOscuro = true))
        assertFalse(esOscuro(preferencia = null, sistemaOscuro = false))
    }

    @Test
    fun `la preferencia guardada gana aunque el sistema diga lo contrario`() {
        assertTrue(esOscuro(preferencia = true, sistemaOscuro = false))
        assertFalse(esOscuro(preferencia = false, sistemaOscuro = true))
    }
}
