package com.controldestock.red

import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.LoteDeConteos
import com.controldestock.nucleo.RespuestaAlta
import com.controldestock.nucleo.RespuestaConteos
import com.controldestock.nucleo.RespuestaMaestro
import com.controldestock.nucleo.RespuestaVinculacion
import com.controldestock.nucleo.jsonDelContrato
import com.controldestock.nucleo.paraEnviar
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Un error que la app puede mostrar y decidir qué hacer con él.
 *
 * `reintentable` distingue lo que puede andar más tarde —el celular salió
 * del alcance del wifi— de lo que nunca va a andar —el token se revocó—.
 * Sin esa distinción, la app reintenta para siempre o descarta trabajo.
 */
class ErrorDeServidor(
    mensaje: String,
    val reintentable: Boolean,
) : Exception(mensaje)

private val TIPO_JSON = "application/json; charset=utf-8".toMediaType()

@Serializable
private data class PedidoDeAlta(
    val codigo: String,
    val descripcion: String,
    val unidad: String,
    val ubicacion: String?,
)

@Serializable
private data class DetalleDeError(val detail: String? = null)

/**
 * El cliente HTTP del servidor de inventario.
 *
 * Los mensajes de error son de pantalla, no de registro: el operario los lee
 * en el depósito, así que van en castellano llano y dicen qué hacer.
 */
class ClienteServidor(
    private val url: String,
    private val token: String,
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build(),
) {

    // El mismo parser que fija el contrato: tolera los campos que el servidor
    // manda de más, que son varios.
    private val json = jsonDelContrato

    suspend fun vincular(): RespuestaVinculacion =
        interpretar(traer("/api/dispositivo/vincular", cuerpo = "{}"))

    suspend fun maestro(): RespuestaMaestro =
        interpretar(traer("/api/dispositivo/maestro"))

    suspend fun enviarConteos(eventos: List<EventoConteo>): RespuestaConteos {
        val lote = LoteDeConteos(eventos.map { it.paraEnviar() })
        return interpretar(
            traer("/api/dispositivo/conteos", cuerpo = json.encodeToString(lote)),
        )
    }

    suspend fun altaRapida(
        codigo: String,
        descripcion: String,
        unidad: String,
        ubicacion: String?,
    ): RespuestaAlta {
        val pedido = json.encodeToString(
            PedidoDeAlta(codigo, descripcion, unidad, ubicacion),
        )
        return interpretar(traer("/api/dispositivo/articulos", cuerpo = pedido))
    }

    /** Hace el pedido y devuelve el texto de la respuesta, o lanza. */
    private suspend fun traer(ruta: String, cuerpo: String? = null): String =
        withContext(Dispatchers.IO) {
            val pedido = Request.Builder()
                .url("$url$ruta")
                .header("X-Token", token)
                .apply { if (cuerpo != null) post(cuerpo.toRequestBody(TIPO_JSON)) }
                .build()

            val respuesta = try {
                http.newCall(pedido).execute()
            } catch (error: IOException) {
                // El caso normal en un depósito: el celular salió del alcance
                // del wifi. No se pierde nada, se reintenta más tarde.
                throw ErrorDeServidor(
                    "Sin conexión con el servidor. Se va a reintentar solo.",
                    reintentable = true,
                )
            }

            respuesta.use {
                val texto = it.body?.string().orEmpty()
                if (!it.isSuccessful) throw traducir(it.code, texto)
                texto
            }
        }

    private inline fun <reified T> interpretar(texto: String): T = try {
        json.decodeFromString<T>(texto)
    } catch (error: Exception) {
        // Reintentar contra algo que no es el servidor esperado no arregla
        // nada: puede ser el portal de una WiFi pública, por ejemplo.
        throw ErrorDeServidor(
            "El servidor contestó algo que no se entiende.",
            reintentable = false,
        )
    }

    fun traducir(codigo: Int, cuerpo: String): ErrorDeServidor = when (codigo) {
        401 -> ErrorDeServidor(
            "Este celular ya no está vinculado. Escaneá de nuevo el QR del panel.",
            reintentable = false,
        )
        409 -> ErrorDeServidor(
            "El inventario está cerrado. No se pueden cargar más conteos.",
            reintentable = false,
        )
        // El servidor explica en castellano por qué rechazó el pedido, y esa
        // explicación es más útil que cualquier mensaje genérico.
        400 -> ErrorDeServidor(detalle(cuerpo) ?: "El servidor rechazó el pedido.", false)
        in 500..599 -> ErrorDeServidor(
            "El servidor tuvo un problema. Se va a reintentar solo.",
            reintentable = true,
        )
        else -> ErrorDeServidor(detalle(cuerpo) ?: "No se pudo completar la operación.", false)
    }

    private fun detalle(cuerpo: String): String? = try {
        json.decodeFromString<DetalleDeError>(cuerpo).detail
    } catch (error: Exception) {
        null
    }
}
