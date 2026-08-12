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

    /** Los pendientes, en el orden en que se cargaron. */
    fun aEnviar(locales: List<ConteoLocal>): List<EventoConteo> =
        locales.filter { it.estadoSync == EstadoSync.PENDIENTE }.map { it.evento }

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
