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

        val locales = base.conteoDao().todos().map { it.aLocal() }

        // Las anulaciones de conteos que el servidor nunca aceptó se cierran
        // acá: mandarlas deja la cola girando para siempre.
        val sinDestino = PlanDeSincronizacion.anulacionesSinDestino(locales)
        sinDestino.forEach {
            base.conteoDao().marcar(
                it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo,
            )
        }

        val aEnviar = PlanDeSincronizacion.aEnviar(locales)
        if (aEnviar.isEmpty()) return ResultadoDeSync()

        val cliente = crearCliente(vinculacion.url, vinculacion.token)

        return try {
            val respuesta = cliente.enviarConteos(aEnviar)
            val resueltos = PlanDeSincronizacion.aplicar(aEnviar, respuesta)

            resueltos.forEach {
                base.conteoDao().marcar(it.evento.uuid, it.estadoSync, it.motivoRechazo)
            }

            ResultadoDeSync(
                enviados = resueltos.count { it.estadoSync == EstadoSync.ENVIADO },
                rechazados = resueltos.count { it.estadoSync == EstadoSync.RECHAZADO },
            )
        } catch (error: ErrorDeServidor) {
            // Lo pendiente sigue pendiente. No se toca nada.
            ResultadoDeSync(huboError = true)
        }
    }
}
