package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RelojFijo(private val instante: String) : Reloj {
    override fun ahora() = instante
}

class EventoConteoTest {

    private val reloj = RelojFijo("2026-08-11T10:00:00Z")

    @Test
    fun `un evento nuevo trae uuid propio y la hora del dispositivo`() {
        val evento = EventoConteo.nuevo("7790001001234", 48000, reloj)

        assertTrue(evento.uuid.isNotEmpty())
        assertEquals("2026-08-11T10:00:00Z", evento.timestampDispositivo)
        assertEquals(48000, evento.cantidad)
        assertNull(evento.anulaUuid)
    }

    @Test
    fun `cada evento recibe un uuid distinto`() {
        // El uuid es lo que vuelve inofensivo reenviar: si dos eventos lo
        // comparten, el servidor descarta el segundo como duplicado y se
        // pierde un conteo real.
        val primero = EventoConteo.nuevo("A", 1000, reloj)
        val segundo = EventoConteo.nuevo("A", 1000, reloj)

        assertNotEquals(primero.uuid, segundo.uuid)
    }

    @Test
    fun `la anulacion apunta al original y no lo modifica`() {
        val original = EventoConteo.nuevo("A", 48000, reloj)

        val anulacion = EventoConteo.anulacionDe(original, RelojFijo("2026-08-11T10:05:00Z"))

        assertEquals(original.uuid, anulacion.anulaUuid)
        assertEquals(original.codigo, anulacion.codigo)
        assertEquals(0, anulacion.cantidad)
        assertNotEquals(original.uuid, anulacion.uuid)
        assertEquals("2026-08-11T10:05:00Z", anulacion.timestampDispositivo)
        // El original queda intacto: nada se edita ni se borra.
        assertNull(original.anulaUuid)
    }

    @Test
    fun `la hora tiene el formato del proyecto`() {
        val evento = EventoConteo.nuevo("A", 1000, RelojDelSistema.DEL_SISTEMA)

        assertTrue(
            evento.timestampDispositivo,
            Regex("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z")
                .matches(evento.timestampDispositivo),
        )
    }

    @Test
    fun `guarda ubicacion real y observaciones cuando las hay`() {
        val evento = EventoConteo.nuevo(
            "A", 1000, reloj,
            ubicacionReal = "P-9",
            observaciones = "Estaba en otro estante",
        )

        assertEquals("P-9", evento.ubicacionReal)
        assertEquals("Estaba en otro estante", evento.observaciones)
    }
}
