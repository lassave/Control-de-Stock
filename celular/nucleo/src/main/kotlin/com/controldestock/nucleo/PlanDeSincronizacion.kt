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
     */
    fun aEnviar(locales: List<ConteoLocal>): List<EventoConteo> {
        val nuncaLlegaron = locales
            .filter { it.estadoSync == EstadoSync.RECHAZADO }
            .map { it.evento.uuid }
            .toSet()

        return locales
            .filter { it.estadoSync == EstadoSync.PENDIENTE }
            .filterNot { it.evento.anulaUuid in nuncaLlegaron }
            .map { it.evento }
    }

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
