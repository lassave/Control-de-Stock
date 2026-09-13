package com.controldestock

import androidx.room.withTransaction
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.ConteoEntidad
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj

sealed class Hallazgo {
    data class Encontrado(
        val articulo: ArticuloEntidad,
        val admiteDecimales: Boolean,
        val codigo: String,
    ) : Hallazgo()

    data class Desconocido(val codigo: String) : Hallazgo()

    /**
     * El artículo existe, pero la pasada activa es un recuento y no lo tiene
     * marcado. A diferencia de `Desconocido`, no ofrece «Darlo de alta»: el
     * artículo ya existe, solo no toca en esta pasada.
     */
    data class FueraDePasada(val codigo: String, val descripcion: String) : Hallazgo()
}

/**
 * Resuelve un código escaneado y guarda el conteo.
 *
 * Todo contra la base local: la pantalla confirma sin pedirle nada al
 * servidor, así el operario cuenta igual sin señal.
 */
class Contador(
    private val base: BaseLocal,
    private val reloj: Reloj,
) {

    suspend fun buscar(codigo: String): Hallazgo {
        val articulo = base.maestroDao().porCodigo(codigo)
            ?: return Hallazgo.Desconocido(codigo)

        // El bloqueo es local, sin ida y vuelta al servidor: la pasada activa
        // y sus SKU permitidos ya están guardados desde el último refresco.
        val vinculacion = base.vinculacionDao().actual()
        if (vinculacion?.esParcial == true && !base.pasadaItemDao().contiene(articulo.id)) {
            return Hallazgo.FueraDePasada(codigo, articulo.descripcion)
        }

        // Una unidad que no bajó en el maestro no puede dejar al operario sin
        // contar: se asume entera, que es el caso conservador.
        val admite = base.maestroDao().unidad(articulo.unidad)?.admiteDecimales == 1

        return Hallazgo.Encontrado(articulo, admite, codigo)
    }

    suspend fun ubicaciones(): List<String> = base.maestroDao().ubicaciones()

    suspend fun registrar(
        articulo: ArticuloEntidad,
        milesimas: Int,
        ubicacionReal: String?,
        observaciones: String?,
    ) {
        // El conteo viaja con el código de barras y no con el SKU: el
        // servidor resuelve solo por código, y un artículo con código propio
        // no tiene una fila donde el código sea su SKU.
        val codigo = base.maestroDao().codigoDe(articulo.id) ?: articulo.sku
        val vinculacion = base.vinculacionDao().actual()

        val evento = EventoConteo.nuevo(
            codigo = codigo,
            cantidad = milesimas,
            reloj = reloj,
            ubicacionReal = ubicacionReal,
            observaciones = observaciones,
        )

        base.conteoDao().guardar(
            ConteoEntidad.de(evento, articulo.id, articulo.proyectoId, vinculacion?.pasadaId ?: 0),
        )
    }

    /** El catálogo de unidades, para que el alta ofrezca dónde elegir. */
    suspend fun unidades(): List<UnidadEntidad> = base.maestroDao().unidades()

    /** Los conteos que este celular ya hizo de ese artículo. */
    suspend fun conteosDe(articulo: ArticuloEntidad): List<ConteoLocal> =
        base.conteoDao().deArticulo(articulo.id).map { it.aLocal() }

    /**
     * Da de alta un código que no está en el maestro, con su primer conteo.
     *
     * El artículo nace acá, con un id provisional, y queda pendiente de
     * crearse en el servidor. Que exista en la base local es lo que hace que
     * el segundo escaneo del mismo pack muestre su ficha en vez de volver a
     * decir «desconocido»: en una estantería de packs iguales eso se repite
     * diez veces seguidas.
     *
     * Va todo en una transacción: un artículo sin su código no se puede
     * contar nunca más, y un conteo sin su artículo lo rechaza el servidor
     * para siempre.
     */
    suspend fun darDeAlta(
        codigo: String,
        descripcion: String,
        unidad: String,
        ubicacion: String?,
        milesimas: Int,
        observaciones: String?,
    ): ArticuloEntidad = base.withTransaction {
        val vinculacion = base.vinculacionDao().actual()

        val articulo = ArticuloEntidad(
            id = base.maestroDao().proximoIdLocal(),
            idOrden = base.maestroDao().proximoOrden(),
            // El servidor usa el código escaneado como SKU de las altas
            // rápidas: el celular hace lo mismo para que las dos filas se
            // parezcan mientras el alta no subió.
            sku = codigo,
            descripcion = descripcion,
            ubicacion = ubicacion,
            unidad = unidad,
            pasadaNumero = vinculacion?.pasadaNumero ?: 1,
            proyectoId = vinculacion?.proyectoId ?: 0,
            busqueda = textoDeBusqueda(descripcion, codigo, ubicacion),
            estadoAlta = EstadoSync.PENDIENTE.name,
        )

        base.maestroDao().insertarArticulos(listOf(articulo))
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad(codigo, articulo.id)))

        // La ubicación del alta es la del artículo, así que el conteo no
        // lleva corrección: corregir sería corregirse a sí mismo.
        registrar(articulo, milesimas, null, observaciones)

        articulo
    }
}
