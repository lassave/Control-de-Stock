package com.controldestock.nucleo

import java.util.UUID

/**
 * Un escaneo, tal como viaja al servidor.
 *
 * Nace en el celular con su propio `uuid`, y eso es lo que vuelve inofensivo
 * reenviarlo: el servidor descarta los uuid que ya recibió. Sin esa garantía
 * la app no podría reintentar cuando se corta la señal.
 */
data class EventoConteo(
    val uuid: String,
    val codigo: String,
    val cantidad: Int,
    val timestampDispositivo: String,
    val ubicacionReal: String? = null,
    val observaciones: String? = null,
    val anulaUuid: String? = null,
) {
    companion object {

        fun nuevo(
            codigo: String,
            cantidad: Int,
            reloj: Reloj,
            ubicacionReal: String? = null,
            observaciones: String? = null,
        ) = EventoConteo(
            uuid = UUID.randomUUID().toString(),
            codigo = codigo,
            cantidad = cantidad,
            timestampDispositivo = reloj.ahora(),
            ubicacionReal = ubicacionReal,
            observaciones = observaciones,
        )

        /**
         * La anulación de un conteo es otro evento, nunca una edición.
         *
         * Así el historial explica qué pasó: quién cargó qué, cuándo, y qué
         * se dio de baja. Editar la fila original borraría esa explicación.
         */
        fun anulacionDe(original: EventoConteo, reloj: Reloj) = EventoConteo(
            uuid = UUID.randomUUID().toString(),
            codigo = original.codigo,
            cantidad = 0,
            timestampDispositivo = reloj.ahora(),
            anulaUuid = original.uuid,
        )
    }
}
