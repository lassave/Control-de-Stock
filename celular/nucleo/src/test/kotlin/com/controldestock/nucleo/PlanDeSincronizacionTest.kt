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
    fun `no manda la anulacion de un conteo que el servidor nunca acepto`() {
        // El caso se cierra solo: el conteo se rechaza como código
        // desconocido, el operario lo ve mal en «Mis conteos» y lo anula, y
        // el servidor rechaza la anulación como reintentable porque el
        // conteo que anula no le llegó nunca. Sin este filtro, esa anulación
        // vuelve a la cola para siempre.
        val rechazado = EventoConteo.nuevo("no-existe", 1000, reloj)
        val locales = listOf(
            ConteoLocal(rechazado, EstadoSync.RECHAZADO, "Código desconocido"),
            ConteoLocal(EventoConteo.anulacionDe(rechazado, reloj), EstadoSync.PENDIENTE),
            local("A"),
        )

        val aEnviar = PlanDeSincronizacion.aEnviar(locales)

        assertEquals(listOf("A"), aEnviar.map { it.codigo })
    }

    @Test
    fun `esa anulacion queda marcada con su motivo en vez de pendiente`() {
        // Si quedara pendiente, el indicador de conteos sin subir nunca
        // bajaría a cero y el operario no sabría por qué.
        val rechazado = EventoConteo.nuevo("no-existe", 1000, reloj)
        val anulacion = EventoConteo.anulacionDe(rechazado, reloj)
        val locales = listOf(
            ConteoLocal(rechazado, EstadoSync.RECHAZADO, "Código desconocido"),
            ConteoLocal(anulacion, EstadoSync.PENDIENTE),
        )

        val sinDestino = PlanDeSincronizacion.anulacionesSinDestino(locales)

        assertEquals(1, sinDestino.size)
        assertEquals(anulacion.uuid, sinDestino.single().evento.uuid)
        assertEquals(EstadoSync.RECHAZADO, sinDestino.single().estadoSync)
        assertTrue(sinDestino.single().motivoRechazo!!.isNotEmpty())
    }

    @Test
    fun `la anulacion de un conteo que si entro se manda normalmente`() {
        val enviado = EventoConteo.nuevo("A", 1000, reloj)
        val locales = listOf(
            ConteoLocal(enviado, EstadoSync.ENVIADO),
            ConteoLocal(EventoConteo.anulacionDe(enviado, reloj), EstadoSync.PENDIENTE),
        )

        assertEquals(1, PlanDeSincronizacion.aEnviar(locales).size)
        assertTrue(PlanDeSincronizacion.anulacionesSinDestino(locales).isEmpty())
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

    @Test
    fun `un conteo cuyo articulo no existe todavia en el servidor espera`() {
        // Mandarlo antes que su alta es tirarlo: el servidor rechaza para
        // siempre un conteo cuyo codigo no conoce.
        val locales = listOf(
            ConteoLocal(EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z")),
            ConteoLocal(EventoConteo("uuid-2", "7790001", 1000, "2026-08-12T10:01:00Z")),
        )

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, setOf("uuid-1"))

        assertEquals(listOf("uuid-2"), aEnviar.map { it.uuid })
    }

    @Test
    fun `un alta trabada no frena a los conteos de los demas articulos`() {
        // El operario conto cincuenta articulos del maestro y uno nuevo: los
        // cincuenta no tienen por que esperar al que falta.
        val locales = (1..3).map {
            ConteoLocal(EventoConteo("uuid-$it", "779000$it", 1000, "2026-08-12T10:0$it:00Z"))
        }

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, setOf("uuid-de-otro"))

        assertEquals(3, aEnviar.size)
    }

    @Test
    fun `retener es por conteo y no por codigo`() {
        // Un codigo puede pertenecer a dos articulos a la vez: el alta local
        // que todavia no subio y el del maestro que ya lo trae, porque otro
        // operario lo dio de alta antes. Reteniendo por codigo, los conteos
        // del articulo del maestro —que el servidor acepta sin chistar—
        // esperarian a un alta que no tiene nada que ver con ellos.
        val locales = listOf(
            ConteoLocal(EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z")),
            ConteoLocal(EventoConteo("uuid-2", "7790999", 2000, "2026-08-12T10:01:00Z")),
        )

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, setOf("uuid-1"))

        assertEquals(listOf("uuid-2"), aEnviar.map { it.uuid })
    }

    @Test
    fun `los conteos de un alta rechazada para siempre se cierran con su motivo`() {
        val locales = listOf(
            ConteoLocal(EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z")),
            ConteoLocal(EventoConteo("uuid-2", "7790001", 1000, "2026-08-12T10:01:00Z")),
        )

        val cerrados = PlanDeSincronizacion.cerradosPorAltaRechazada(
            locales, setOf("uuid-1"), "La unidad «XX» no está en el catálogo",
        )

        assertEquals(1, cerrados.size)
        assertEquals("uuid-1", cerrados.single().evento.uuid)
        assertEquals(EstadoSync.RECHAZADO, cerrados.single().estadoSync)
        assertEquals(
            "La unidad «XX» no está en el catálogo",
            cerrados.single().motivoRechazo,
        )
    }

    @Test
    fun `cerrar es por conteo y no por codigo`() {
        // El mismo caso de arriba, del lado del cierre y peor: cerrar por
        // codigo tira conteos de un articulo del maestro que el servidor
        // habria aceptado, y de esos no se vuelve.
        val locales = listOf(
            ConteoLocal(EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z")),
            ConteoLocal(EventoConteo("uuid-2", "7790999", 2000, "2026-08-12T10:01:00Z")),
        )

        val cerrados = PlanDeSincronizacion.cerradosPorAltaRechazada(
            locales, setOf("uuid-1"), "La unidad «XX» no está en el catálogo",
        )

        assertEquals(listOf("uuid-1"), cerrados.map { it.evento.uuid })
    }

    @Test
    fun `cerrar los conteos de un alta rechazada no toca a los que ya subieron`() {
        val locales = listOf(
            ConteoLocal(
                EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z"),
                EstadoSync.ENVIADO,
            ),
        )

        val cerrados = PlanDeSincronizacion.cerradosPorAltaRechazada(
            locales, setOf("uuid-1"), "no",
        )

        assertEquals(emptyList<ConteoLocal>(), cerrados)
    }
}
