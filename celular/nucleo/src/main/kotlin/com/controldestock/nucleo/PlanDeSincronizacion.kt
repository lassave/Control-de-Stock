package com.controldestock.nucleo

/**
 * En qué estado está un conteo respecto del servidor.
 *
 * `RECHAZADO` existe porque un conteo que el servidor nunca va a aceptar no
 * puede reintentarse para siempre ni desaparecer sin dejar rastro: queda
 * visible en «Mis conteos» con su motivo.
 */
enum class EstadoSync { PENDIENTE, ENVIADO, RECHAZADO }

data class ConteoLocal(
    val evento: EventoConteo,
    val estadoSync: EstadoSync = EstadoSync.PENDIENTE,
    val motivoRechazo: String? = null,
)

/**
 * Qué mandar y qué hacer con la respuesta.
 *
 * Es lógica pura a propósito: así los casos que solo aparecen con mala señal
 * se prueban en milisegundos, sin red ni base de datos.
 */
object PlanDeSincronizacion {

    /**
     * Los pendientes, en el orden en que se cargaron.
     *
     * Se descarta la anulación de un conteo que el servidor nunca aceptó.
     * El caso se cierra solo: un conteo se rechaza como «código desconocido»,
     * el operario lo ve mal en «Mis conteos» y lo anula; el servidor rechaza
     * esa anulación como reintentable —porque el conteo que anula no le
     * llegó nunca— y vuelve a la cola. Para siempre: el indicador de
     * pendientes no baja a cero y el trabajo en segundo plano quema batería y
     * red sin fin. Es la misma falla que el estado RECHAZADO existe para
     * evitar, entrando por la puerta de la anulación.
     *
     * Y se retiene lo que depende de un alta que todavía no llegó: mandar un
     * conteo antes que su artículo es tirarlo, porque el servidor rechaza
     * para siempre un código que no conoce.
     */
    fun aEnviar(
        locales: List<ConteoLocal>,
        codigosSinArticulo: Set<String> = emptySet(),
    ): List<EventoConteo> {
        val nuncaLlegaron = locales
            .filter { it.estadoSync == EstadoSync.RECHAZADO }
            .map { it.evento.uuid }
            .toSet()

        return locales
            .filter { it.estadoSync == EstadoSync.PENDIENTE }
            .filterNot { it.evento.anulaUuid in nuncaLlegaron }
            .filterNot { it.evento.codigo in codigosSinArticulo }
            .map { it.evento }
    }

    /**
     * Los conteos que hay que cerrar porque su alta no va a entrar nunca.
     *
     * Si el servidor rechazó el artículo para siempre —una unidad que no está
     * en su catálogo, el inventario cerrado— sus conteos no tienen a dónde
     * llegar. Dejarlos pendientes deja la cola girando para siempre, quema
     * batería y red, y el indicador de «sin subir» pasa a mentir.
     */
    fun cerradosPorAltaRechazada(
        locales: List<ConteoLocal>,
        codigo: String,
        motivo: String,
    ): List<ConteoLocal> = locales
        .filter { it.estadoSync == EstadoSync.PENDIENTE }
        .filter { it.evento.codigo == codigo }
        .map { it.copy(estadoSync = EstadoSync.RECHAZADO, motivoRechazo = motivo) }

    /**
     * Las anulaciones que no tiene sentido mandar, con su motivo.
     *
     * Quien las guarda las marca como rechazadas: si no, quedan pendientes
     * para siempre y el contador miente.
     */
    fun anulacionesSinDestino(locales: List<ConteoLocal>): List<ConteoLocal> {
        val nuncaLlegaron = locales
            .filter { it.estadoSync == EstadoSync.RECHAZADO }
            .map { it.evento.uuid }
            .toSet()

        return locales
            .filter { it.estadoSync == EstadoSync.PENDIENTE }
            .filter { it.evento.anulaUuid in nuncaLlegaron }
            .map {
                it.copy(
                    estadoSync = EstadoSync.RECHAZADO,
                    motivoRechazo = "El conteo que anula nunca entró al servidor",
                )
            }
    }

    fun pendientes(locales: List<ConteoLocal>): Int =
        locales.count { it.estadoSync == EstadoSync.PENDIENTE }

    /**
     * Aplica la respuesta del servidor a los eventos que se mandaron.
     *
     * El servidor contesta con totales, no con la lista de uuid aceptados,
     * así que lo único seguro es dar por enviado todo lo que no venga
     * rechazado: reenviar es inofensivo gracias al uuid, y perder un conteo
     * no lo es.
     */
    fun aplicar(
        enviados: List<EventoConteo>,
        respuesta: RespuestaConteos,
    ): List<ConteoLocal> {
        val porUuid = respuesta.rechazados.associateBy { it.uuid }

        return enviados.map { evento ->
            val rechazo = porUuid[evento.uuid]
            when {
                rechazo == null ->
                    ConteoLocal(evento, EstadoSync.ENVIADO)

                rechazo.reintentable ->
                    ConteoLocal(evento, EstadoSync.PENDIENTE, rechazo.motivo)

                else ->
                    ConteoLocal(evento, EstadoSync.RECHAZADO, rechazo.motivo)
            }
        }
    }
}
