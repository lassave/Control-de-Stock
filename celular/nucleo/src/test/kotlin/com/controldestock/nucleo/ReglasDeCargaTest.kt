package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ReglasDeCargaTest {

    @Test
    fun `una cantidad entera en unidad entera es valida`() {
        val resultado = ReglasDeCarga.validar("24", admiteDecimales = false)

        assertEquals(ResultadoDeCarga.Valida(24000), resultado)
    }

    @Test
    fun `una cantidad con decimales en unidad decimal es valida`() {
        val resultado = ReglasDeCarga.validar("3,5", admiteDecimales = true)

        assertEquals(ResultadoDeCarga.Valida(3500), resultado)
    }

    @Test
    fun `un decimal en unidad entera pide confirmacion pero no bloquea`() {
        // Medio tornillo suele ser un error de tipeo, pero a veces no: el
        // operario tiene que poder confirmarlo, no quedarse trabado.
        val resultado = ReglasDeCarga.validar("3,5", admiteDecimales = false)

        assertTrue(resultado is ResultadoDeCarga.PideConfirmacion)
        assertEquals(3500, (resultado as ResultadoDeCarga.PideConfirmacion).milesimas)
        assertTrue(resultado.motivo.isNotEmpty())
    }

    @Test
    fun `una cantidad vacia es invalida`() {
        val resultado = ReglasDeCarga.validar("", admiteDecimales = true)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
    }

    @Test
    fun `una cantidad que no es numero es invalida`() {
        val resultado = ReglasDeCarga.validar("abc", admiteDecimales = true)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
        assertTrue((resultado as ResultadoDeCarga.Invalida).motivo.isNotEmpty())
    }

    @Test
    fun `una cantidad negativa es invalida`() {
        // Restar existe como anulación, no como cantidad negativa.
        val resultado = ReglasDeCarga.validar("-4", admiteDecimales = true)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
    }

    @Test
    fun `cero es una cantidad valida`() {
        // Contar cero es un dato real: el estante estaba vacío.
        assertEquals(ResultadoDeCarga.Valida(0), ReglasDeCarga.validar("0", true))
    }

    @Test
    fun `rechaza una cantidad que no entra en la base del servidor`() {
        // El servidor guarda enteros de 64 bits; la app manda Int, pero el
        // texto puede traer cualquier cosa.
        val resultado = ReglasDeCarga.validar("99999999999", admiteDecimales = false)

        assertTrue(resultado is ResultadoDeCarga.Invalida)
        // El motivo tiene que explicar el desborde: si saliera el mensaje de
        // «escribí una cantidad», el operario corregiría un tipeo que no hizo.
        assertEquals(
            "Esa cantidad es demasiado grande",
            (resultado as ResultadoDeCarga.Invalida).motivo,
        )
    }
}
