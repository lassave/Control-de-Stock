package com.controldestock

import com.controldestock.datos.BaseLocal
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.PlanDeSincronizacion
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor

data class ResultadoDeSync(
    val enviados: Int = 0,
    val rechazados: Int = 0,
    val huboError: Boolean = false,
    /**
     * Los códigos que el servidor ya conocía, con el nombre que tenía.
     *
     * El operario escribió una descripción que se descarta —manda la del
     * servidor— así que si sigue mirando hay que decírselo: «ese código ya
     * era: Tornillo». Sin esto se entera recién cuando baja el maestro, o
     * nunca.
     */
    val yaExistian: List<String> = emptyList(),
)

/**
 * Empuja al servidor los conteos que todavía no subieron.
 *
 * Nunca borra ni edita un conteo local: solo cambia su estado. Si algo sale
 * mal, lo pendiente sigue pendiente y se reintenta más tarde — perder un
 * conteo es peor que mandarlo dos veces, y el `uuid` hace que mandarlo dos
 * veces sea inofensivo.
 */
class Sincronizador(
    private val base: BaseLocal,
    private val crearCliente: (String, String) -> ClienteServidor,
) {

    suspend fun sincronizar(): ResultadoDeSync {
        val vinculacion = base.vinculacionDao().actual() ?: return ResultadoDeSync()
        val cliente = crearCliente(vinculacion.url, vinculacion.token)

        // Primero los artículos que nacieron en el celular: un conteo cuyo
        // código el servidor no conoce se rechaza para siempre, no se
        // reintenta. Mandarlo antes que su artículo es tirarlo.
        val altas = subirAltas(cliente)

        val locales = base.conteoDao().todos().map { it.aLocal() }

        // Las anulaciones de conteos que el servidor nunca aceptó se cierran
        // acá: mandarlas deja la cola girando para siempre.
        PlanDeSincronizacion.anulacionesSinDestino(locales).forEach {
            base.conteoDao().marcar(it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo)
        }

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, altas.codigos)
        if (aEnviar.isEmpty()) {
            return ResultadoDeSync(
                huboError = altas.huboError,
                yaExistian = altas.yaExistian,
            )
        }

        return try {
            val respuesta = cliente.enviarConteos(aEnviar)
            val resueltos = PlanDeSincronizacion.aplicar(aEnviar, respuesta)

            resueltos.forEach {
                base.conteoDao().marcar(it.evento.uuid, it.estadoSync, it.motivoRechazo)
            }

            ResultadoDeSync(
                enviados = resueltos.count { it.estadoSync == EstadoSync.ENVIADO },
                rechazados = resueltos.count { it.estadoSync == EstadoSync.RECHAZADO },
                huboError = altas.huboError,
                yaExistian = altas.yaExistian,
            )
        } catch (error: ErrorDeServidor) {
            // Lo pendiente sigue pendiente. No se toca nada.
            ResultadoDeSync(huboError = true, yaExistian = altas.yaExistian)
        }
    }

    /** Cómo quedaron las altas: qué se trabó y qué código ya existía. */
    private data class Altas(
        val codigos: Set<String> = emptySet(),
        val huboError: Boolean = false,
        val yaExistian: List<String> = emptyList(),
    )

    private suspend fun subirAltas(cliente: ClienteServidor): Altas {
        val codigos = mutableSetOf<String>()
        val yaExistian = mutableListOf<String>()
        var huboError = false

        for (alta in base.maestroDao().altasPendientes()) {
            val codigo = base.maestroDao().codigoDe(alta.id) ?: alta.sku

            try {
                // La respuesta trae `creado`, que distingue el alta nueva de
                // la que ya existía. Las dos son buenas noticias: en las dos,
                // el código ya identifica a un artículo y sus conteos pueden
                // entrar. La diferencia es que en la segunda el operario
                // escribió una descripción que se descarta, y merece
                // enterarse.
                val respuesta =
                    cliente.altaRapida(codigo, alta.descripcion, alta.unidad, alta.ubicacion)
                if (!respuesta.creado) yaExistian += respuesta.descripcion
                base.maestroDao().marcarAlta(alta.id, EstadoSync.ENVIADO.name, null)
            } catch (error: ErrorDeServidor) {
                if (error.reintentable) {
                    // Se cayó la red o el servidor tosió: el alta sigue
                    // pendiente y sus conteos esperan con ella.
                    huboError = true
                    codigos += codigo
                } else {
                    val motivo = error.message.orEmpty()
                    base.maestroDao().marcarAlta(alta.id, EstadoSync.RECHAZADO.name, motivo)

                    // Ese artículo no va a existir nunca: sus conteos no
                    // tienen a dónde llegar, y dejarlos pendientes deja la
                    // cola girando para siempre.
                    val locales = base.conteoDao().todos().map { it.aLocal() }
                    PlanDeSincronizacion
                        .cerradosPorAltaRechazada(locales, codigo, motivo)
                        .forEach {
                            base.conteoDao().marcar(
                                it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo,
                            )
                        }
                }
            }
        }

        return Altas(codigos, huboError, yaExistian)
    }
}
