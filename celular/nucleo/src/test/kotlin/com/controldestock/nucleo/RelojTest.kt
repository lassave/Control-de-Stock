package com.controldestock.nucleo

import java.time.Clock
import java.time.Instant
import java.time.ZoneId
import org.junit.Assert.assertEquals
import org.junit.Test

class RelojTest {

    @Test
    fun `la hora sale en UTC aunque el celular este en otra zona`() {
        // El celular del depósito está en Buenos Aires, tres horas detrás de
        // UTC. Si la app mandara la hora local con una «Z» pegada al final,
        // cada conteo quedaría corrido tres horas y nadie lo notaría hasta
        // conciliar los números con el cliente.
        val enBuenosAires = Clock.fixed(
            Instant.parse("2026-08-11T14:32:05Z"),
            ZoneId.of("America/Argentina/Buenos_Aires"),
        )

        val reloj = RelojDelSistema(enBuenosAires)

        assertEquals("2026-08-11T14:32:05Z", reloj.ahora())
    }

    @Test
    fun `la hora sale en UTC aunque el celular este adelantado`() {
        val enTokio = Clock.fixed(
            Instant.parse("2026-08-11T14:32:05Z"),
            ZoneId.of("Asia/Tokyo"),
        )

        assertEquals("2026-08-11T14:32:05Z", RelojDelSistema(enTokio).ahora())
    }

    @Test
    fun `el formato es el mismo que usa el servidor`() {
        // servidor/app/reloj.py produce exactamente este formato.
        val fijo = Clock.fixed(Instant.parse("2026-01-05T09:07:03Z"), ZoneId.of("UTC"))

        assertEquals("2026-01-05T09:07:03Z", RelojDelSistema(fijo).ahora())
    }
}
