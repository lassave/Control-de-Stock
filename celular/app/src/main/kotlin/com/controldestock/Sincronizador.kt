package com.controldestock

import com.controldestock.datos.BaseLocal
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.PlanDeSincronizacion
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor

/**
 * Un código que el servidor ya conocía, con el nombre que tenía.
 *
 * Lleva el código y no solo el nombre porque el aviso habla de *ese* código:
 * varias altas pueden subir juntas cuando vuelve la señal, y sin el código no
 * hay forma de saber si el choque es del producto que el operario tiene en la
 * mano o de uno que escaneó hace media hora.
 */
data class CodigoYaExistente(val codigo: String, val descripcion: String)

data class ResultadoDeSync(
    val enviados: Int = 0,
    val rechazados: Int = 0,
    val huboError: Boolean = false,
    /**
     * Los códigos que el servidor ya conocía, con el nombre que tenía.
     *
     * El operario escribió una descripción que se descarta —manda la del
     * servidor— así que si sigue mirando hay que decírselo: «ese código ya
     * estaba: Tornillo». Sin esto se entera recién cuando baja el maestro, o
     * nunca.
     */
    val yaExistian: List<CodigoYaExistente> = emptyList(),
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

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, altas.uuidsRetenidos)
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

    /** Cómo quedaron las altas: qué conteos esperan y qué código ya existía. */
    private data class Altas(
        val uuidsRetenidos: Set<String> = emptySet(),
        val huboError: Boolean = false,
        val yaExistian: List<CodigoYaExistente> = emptyList(),
    )

    /**
     * Los uuid de los conteos de un artículo.
     *
     * Se pregunta por artículo y no por código porque un código puede
     * pertenecer a dos artículos a la vez: el alta local que todavía no subió
     * y el del maestro que ya lo trae, porque otro operario lo dio de alta
     * antes de que este celular tuviera red. Los conteos del segundo son
     * válidos y no tienen nada que ver con el alta trabada.
     */
    private suspend fun conteosDe(articuloId: Int): Set<String> =
        base.conteoDao().deArticulo(articuloId).map { it.uuid }.toSet()

    private suspend fun subirAltas(cliente: ClienteServidor): Altas {
        val retenidos = mutableSetOf<String>()
        val yaExistian = mutableListOf<CodigoYaExistente>()
        var huboError = false

        val pendientes = base.maestroDao().altasPendientes()

        for ((indice, alta) in pendientes.withIndex()) {
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
                if (!respuesta.creado) {
                    yaExistian += CodigoYaExistente(codigo, respuesta.descripcion)
                }
                base.maestroDao().marcarAlta(alta.id, EstadoSync.ENVIADO.name, null)
            } catch (error: ErrorDeServidor) {
                if (!error.contenidoRechazado) {
                    // No se pudo hablar bien con el servidor: no hay señal, el
                    // token se revocó, contestó el portal cautivo de una WiFi
                    // ajena. Nadie leyó este artículo todavía, así que no hay
                    // nada que dar por perdido — lo pendiente sigue pendiente.
                    //
                    // Y se corta acá: lo que falló no es de este artículo, así
                    // que las altas que siguen van a fallar igual. Sin cortar,
                    // cada conteo confirmado dispara un pedido por alta
                    // pendiente, en serie y con diez segundos de timeout cada
                    // uno, justo cuando el operario se fue de la zona de
                    // cobertura y sigue contando.
                    huboError = true
                    pendientes.drop(indice).forEach { retenidos += conteosDe(it.id) }
                    break
                }

                // Acá sí: el servidor leyó el artículo y lo rechazó por lo que
                // es —una unidad que no está en su catálogo—. Ese artículo no
                // va a existir nunca, sus conteos no tienen a dónde llegar, y
                // dejarlos pendientes deja la cola girando para siempre.
                val motivo = error.message.orEmpty()
                base.maestroDao().marcarAlta(alta.id, EstadoSync.RECHAZADO.name, motivo)

                val locales = base.conteoDao().todos().map { it.aLocal() }
                PlanDeSincronizacion
                    .cerradosPorAltaRechazada(locales, conteosDe(alta.id), motivo)
                    .forEach {
                        base.conteoDao().marcar(
                            it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo,
                        )
                    }
            }
        }

        return Altas(retenidos, huboError, yaExistian)
    }
}
