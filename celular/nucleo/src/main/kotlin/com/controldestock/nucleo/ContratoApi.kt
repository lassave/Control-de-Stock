package com.controldestock.nucleo

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Los tipos que viajan entre el celular y el servidor.
 *
 * Los nombres en el JSON son los del servidor (snake_case) y se mapean con
 * @SerialName: cambiar uno de los dos lados sin el otro rompe los tests de
 * contrato en la PC, que es exactamente lo que se busca.
 *
 * Ninguna respuesta trae `stock_sistema` ni `costo_unitario`: el conteo es a
 * ciegas y el dato no debe existir en el dispositivo.
 */

@Serializable
data class OperarioRemoto(val id: Int, val nombre: String)

@Serializable
data class SesionRemota(val id: Int, val nombre: String)

@Serializable
data class PasadaRemota(
    val id: Int,
    val numero: Int,
    val etiqueta: String,
)

@Serializable
data class RespuestaVinculacion(
    val operario: OperarioRemoto,
    val sesion: SesionRemota,
    val pasada: PasadaRemota,
)

@Serializable
data class ArticuloRemoto(
    val id: Int,
    @SerialName("id_orden") val idOrden: Int,
    val tipo: String? = null,
    val material: String? = null,
    val sku: String,
    val descripcion: String,
    val grupo: String? = null,
    val ubicacion: String? = null,
    val unidad: String,
)

@Serializable
data class CodigoRemoto(
    val codigo: String,
    @SerialName("articulo_id") val articuloId: Int,
)

@Serializable
data class UnidadRemota(
    val codigo: String,
    val nombre: String,
    @SerialName("admite_decimales") val admiteDecimales: Int,
)

@Serializable
data class RespuestaMaestro(
    @SerialName("sesion_id") val sesionId: Int,
    val articulos: List<ArticuloRemoto>,
    val codigos: List<CodigoRemoto>,
    val unidades: List<UnidadRemota>,
)

@Serializable
data class ConteoRechazado(
    val uuid: String,
    val motivo: String,
    val reintentable: Boolean,
)

@Serializable
data class RespuestaConteos(
    val registrados: Int,
    val duplicados: Int,
    val rechazados: List<ConteoRechazado>,
)

@Serializable
data class RespuestaAlta(
    val id: Int,
    @SerialName("id_orden") val idOrden: Int,
    val sku: String,
    val descripcion: String,
    val unidad: String,
    val ubicacion: String? = null,
    val tipo: String? = null,
    val material: String? = null,
    val grupo: String? = null,
    val creado: Boolean,
)

/** Un conteo tal como se manda: los nombres son los que espera el servidor. */
@Serializable
data class ConteoParaEnviar(
    val uuid: String,
    val codigo: String,
    val cantidad: Int,
    @SerialName("timestamp_dispositivo") val timestampDispositivo: String,
    @SerialName("ubicacion_real") val ubicacionReal: String? = null,
    val observaciones: String? = null,
    @SerialName("anula_uuid") val anulaUuid: String? = null,
)

@Serializable
data class LoteDeConteos(val conteos: List<ConteoParaEnviar>)

fun EventoConteo.paraEnviar() = ConteoParaEnviar(
    uuid = uuid,
    codigo = codigo,
    cantidad = cantidad,
    timestampDispositivo = timestampDispositivo,
    ubicacionReal = ubicacionReal,
    observaciones = observaciones,
    anulaUuid = anulaUuid,
)
