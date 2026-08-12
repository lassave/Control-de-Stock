package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PlanDeSincronizacionTest {

    private val reloj = RelojFijo("2026-08-11T10:00:00Z")

    private fun local(codigo: String, estado: EstadoSync = EstadoSync.PENDIENTE) =
        ConteoLocal(EventoConteo.nuevo(codigo, 1000, reloj), estado)

    @Test
    fun `manda solo los pendientes`() {
        val locales = listOf(
            local("A"),
            local("B", EstadoSync.ENVIADO),
            local("C", EstadoSync.RECHAZADO),
            local("D"),
        )

        val aEnviar = PlanDeSincronizacion.aEnviar(locales)

        assertEquals(listOf("A", "D"), aEnviar.map { it.codigo })
    }

    @Test
    fun `un rechazado no reintentable no vuelve a la cola`() {
        // Reintentar para siempre algo que nunca va a entrar deja la cola
        // trabada y el indicador de pendientes mintiendo.
        val locales = listOf(local("A", EstadoSync.RECHAZADO))

        assertTrue(PlanDeSincronizacion.aEnviar(locales).isEmpty())
    }

    @Test
    fun `lo aceptado queda como enviado`() {
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(registrados = 1, duplicados = 0, rechazados = emptyList())

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.ENVIADO, resultado.single().estadoSync)
    }

    @Test
    fun `un duplicado tambien queda como enviado`() {
        // El servidor ya lo tenía: reenviar es inofensivo y no hay nada que
        // arreglar del lado del celular.
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(registrados = 0, duplicados = 1, rechazados = emptyList())

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.ENVIADO, resultado.single().estadoSync)
    }

    @Test
    fun `un rechazo definitivo queda marcado con su motivo`() {
        val evento = EventoConteo.nuevo("no-existe", 1000, reloj)
        val respuesta = RespuestaConteos(
            registrados = 0, duplicados = 0,
            rechazados = listOf(
                ConteoRechazado(evento.uuid, "Código desconocido: no-existe", reintentable = false),
            ),
        )

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.RECHAZADO, resultado.single().estadoSync)
        assertEquals("Código desconocido: no-existe", resultado.single().motivoRechazo)
    }

    @Test
    fun `un rechazo reintentable vuelve a quedar pendiente`() {
        // Pasa cuando una anulación llega antes que el conteo que anula: los
        // celulares sincronizan en cualquier orden.
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(
            registrados = 0, duplicados = 0,
            rechazados = listOf(
                ConteoRechazado(evento.uuid, "El conteo que anula todavía no llegó", reintentable = true),
            ),
        )

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.PENDIENTE, resultado.single().estadoSync)
    }

    @Test
    fun `un evento que la respuesta no menciona se da por enviado`() {
        // El servidor contesta con totales, no con la lista de uuid aceptados,
        // así que no se puede saber cuál de los dos entró. Reenviar es
        // inofensivo gracias al uuid; perder un conteo no lo es.
        val enviados = listOf(
            EventoConteo.nuevo("A", 1000, reloj),
            EventoConteo.nuevo("B", 1000, reloj),
        )
        val respuesta = RespuestaConteos(registrados = 1, duplicados = 0, rechazados = emptyList())

        val resultado = PlanDeSincronizacion.aplicar(enviados, respuesta)

        assertEquals(2, resultado.size)
        assertTrue(resultado.all { it.estadoSync == EstadoSync.ENVIADO })
    }

    @Test
    fun `cuenta los pendientes para el indicador de pantalla`() {
        val locales = listOf(
            local("A"),
            local("B", EstadoSync.ENVIADO),
            local("C"),
        )

        assertEquals(2, PlanDeSincronizacion.pendientes(locales))
    }

    @Test
    fun `el orden de envio respeta el de la cola`() {
        // Una anulación mandada antes que su conteo se rechaza como
        // reintentable y da una vuelta de más. Mantener el orden de carga
        // evita ese ida y vuelta en el caso normal.
        val locales = listOf(local("A"), local("B"), local("C"))

        val aEnviar = PlanDeSincronizacion.aEnviar(locales)

        assertEquals(listOf("A", "B", "C"), aEnviar.map { it.codigo })
    }

    @Test
    fun `un rechazo de un uuid que no se mando no afecta a los demas`() {
        // El servidor puede contestar sobre un evento de otro lote si hubo un
        // reintento cruzado. Lo que importa es no marcar mal lo que sí se mandó.
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        val respuesta = RespuestaConteos(
            registrados = 1, duplicados = 0,
            rechazados = listOf(
                ConteoRechazado("uuid-de-otro-lote", "Código desconocido", reintentable = false),
            ),
        )

        val resultado = PlanDeSincronizacion.aplicar(listOf(evento), respuesta)

        assertEquals(EstadoSync.ENVIADO, resultado.single().estadoSync)
    }
}
