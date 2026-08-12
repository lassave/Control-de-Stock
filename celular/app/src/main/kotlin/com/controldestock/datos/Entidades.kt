package com.controldestock.datos

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo

/**
 * La base local del celular.
 *
 * Es la fuente de verdad mientras se cuenta: la app nunca consulta al
 * servidor para trabajar, solo para sincronizar. Con o sin señal se comporta
 * igual.
 *
 * Las cantidades se guardan como enteros en milésimas, igual que en el
 * servidor y por el mismo motivo: sumar decimales en punto flotante acumula
 * error y un inventario suma miles de veces.
 */

@Entity(tableName = "vinculacion")
data class VinculacionEntidad(
    // Una sola vinculación por dispositivo: revincular con otro operario
    // reemplaza la anterior, para que los conteos no se atribuyan a quien no
    // contó.
    @PrimaryKey val id: Int = 1,
    val url: String,
    val token: String,
    val operarioId: Int,
    val operarioNombre: String,
    val sesionId: Int,
    val pasadaId: Int,
    val pasadaNumero: Int,
    val pasadaEtiqueta: String,
)

@Entity(tableName = "articulo")
data class ArticuloEntidad(
    @PrimaryKey val id: Int,
    val idOrden: Int,
    val tipo: String? = null,
    val material: String? = null,
    val sku: String,
    val descripcion: String,
    val grupo: String? = null,
    val ubicacion: String? = null,
    val unidad: String,
    // A qué pasada pertenece. Hoy siempre 1: cuando existan las pasadas
    // sucesivas, agregar la columna obligaría a migrar la base de cada
    // dispositivo en medio de un inventario.
    val pasadaNumero: Int,
    // De qué sesión es. Un celular que se revincula a otro inventario no
    // puede seguir mostrando el maestro del anterior.
    val sesionId: Int = 0,
    // Descripción, SKU y ubicación juntos, en minúscula y sin acentos.
    // El LIKE de SQLite solo pliega mayúsculas en ASCII, así que buscar
    // «caño» no encontraría «CAÑO galvanizado» — y los maestros de ERP
    // vienen en mayúsculas, con el castellano lleno de eñes.
    val busqueda: String = "",
)

/** Minúsculas y sin acentos, para que la búsqueda encuentre lo que se ve. */
fun plegar(texto: String): String =
    java.text.Normalizer.normalize(texto.lowercase(), java.text.Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "")

/** El texto contra el que busca el operario. */
fun textoDeBusqueda(descripcion: String, sku: String, ubicacion: String?): String =
    plegar(listOfNotNull(descripcion, sku, ubicacion).joinToString(" "))

@Entity(
    tableName = "codigo",
    primaryKeys = ["codigo", "articuloId"],
    indices = [Index("codigo")],
)
data class CodigoEntidad(
    val codigo: String,
    val articuloId: Int,
)

@Entity(tableName = "unidad")
data class UnidadEntidad(
    @PrimaryKey val codigo: String,
    val nombre: String,
    val admiteDecimales: Int,
)

@Entity(tableName = "conteo")
data class ConteoEntidad(
    @PrimaryKey val uuid: String,
    val articuloId: Int,
    // De qué sesión es este conteo. Sin esto, un pendiente que quedó de un
    // inventario cerrado se sincroniza contra la sesión abierta hoy: el
    // servidor resuelve por «la» sesión abierta, así que el conteo de ayer
    // entra al inventario de hoy sin que nada lo señale.
    val sesionId: Int = 0,
    val codigo: String,
    val cantidad: Int,
    val ubicacionReal: String? = null,
    val observaciones: String? = null,
    // Si el conteo cayó fuera de lo asignado. Hoy siempre 0, por el mismo
    // motivo que pasadaNumero.
    val fueraAsignacion: Int = 0,
    val timestampDispositivo: String,
    val anulaUuid: String? = null,
    val estadoSync: EstadoSync = EstadoSync.PENDIENTE,
    val motivoRechazo: String? = null,
) {
    fun aEvento() = EventoConteo(
        uuid = uuid,
        codigo = codigo,
        cantidad = cantidad,
        timestampDispositivo = timestampDispositivo,
        ubicacionReal = ubicacionReal,
        observaciones = observaciones,
        anulaUuid = anulaUuid,
    )

    fun aLocal() = ConteoLocal(aEvento(), estadoSync, motivoRechazo)

    companion object {
        fun de(evento: EventoConteo, articuloId: Int, sesionId: Int = 0) = ConteoEntidad(
            uuid = evento.uuid,
            articuloId = articuloId,
            sesionId = sesionId,
            codigo = evento.codigo,
            cantidad = evento.cantidad,
            ubicacionReal = evento.ubicacionReal,
            observaciones = evento.observaciones,
            timestampDispositivo = evento.timestampDispositivo,
            anulaUuid = evento.anulaUuid,
        )
    }
}
