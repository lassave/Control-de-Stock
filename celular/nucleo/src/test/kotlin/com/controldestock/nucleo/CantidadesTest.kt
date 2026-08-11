package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CantidadesTest {

    // Los mismos casos que servidor/tests/test_cantidades.py. Si los dos lados
    // no convierten igual, aparecen diferencias que nadie puede explicar.
    @Test
    fun `convierte texto a milesimas`() {
        val casos = mapOf(
            "24" to 24000,
            "0" to 0,
            "3,5" to 3500,
            "3.5" to 3500,
            "0,001" to 1,
            "1.234,56" to 1234560,
            "1,234.56" to 1234560,
            "  12  " to 12000,
            "-4" to -4000,
        )

        for ((texto, esperado) in casos) {
            assertEquals("convirtiendo «$texto»", esperado, Cantidades.aMilesimas(texto))
        }
    }

    @Test
    fun `acepta miles agrupados sin decimales`() {
        assertEquals(1234567000, Cantidades.aMilesimas("1.234.567"))
        assertEquals(1234567000, Cantidades.aMilesimas("1,234,567"))
    }

    @Test
    fun `redondea los decimales sobrantes en vez de truncar`() {
        // Truncar sesgaría todas las cantidades a la baja de forma sistemática.
        assertEquals(1235, Cantidades.aMilesimas("1,2345"))
        assertEquals(1234, Cantidades.aMilesimas("1,2344"))
        assertEquals(1, Cantidades.aMilesimas("0,0005"))
        assertEquals(0, Cantidades.aMilesimas("0,0004"))
    }

    @Test
    fun `rechaza lo que no es una cantidad`() {
        val invalidos = listOf(
            "", "   ", "abc", "1,2,3",
            ".", ",", "-", "-,",      // separador suelto: celda rota, no cero
            "1 2",                    // dos números pegados, no doce mil
            "1.23.456",               // grupos de miles mal formados
            "inf", "-inf", "nan",
            "1e3", "1_000",
        )

        for (texto in invalidos) {
            try {
                Cantidades.aMilesimas(texto)
                throw AssertionError("«$texto» tendría que haber sido rechazado")
            } catch (esperado: IllegalArgumentException) {
                assertTrue(esperado.message!!.isNotEmpty())
            }
        }
    }

    @Test
    fun `convierte milesimas a texto`() {
        val casos = mapOf(
            24000 to "24",
            0 to "0",
            3500 to "3,5",
            1 to "0,001",
            1234560 to "1234,56",
            -4000 to "-4",
        )

        for ((milesimas, esperado) in casos) {
            assertEquals(esperado, Cantidades.aTexto(milesimas))
        }
    }

    @Test
    fun `la ida y vuelta no pierde precision`() {
        for (texto in listOf("24", "3,5", "0,001", "999999,999")) {
            assertEquals(texto, Cantidades.aTexto(Cantidades.aMilesimas(texto)))
        }
    }

    @Test
    fun `sumar decimales es exacto`() {
        // Con punto flotante, diez veces 0,1 no da 1. Un inventario suma miles
        // de veces, así que el error se acumula hasta ser visible.
        val total = (1..10).sumOf { Cantidades.aMilesimas("0,1") }

        assertEquals(Cantidades.aMilesimas("1"), total)
    }
}
