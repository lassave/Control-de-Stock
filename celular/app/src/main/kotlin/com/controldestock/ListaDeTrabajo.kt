package com.controldestock

import com.controldestock.datos.BaseLocal
import com.controldestock.nucleo.ArticuloParaLista
import com.controldestock.nucleo.ConteoParaLista
import com.controldestock.nucleo.ListaAsignada
import com.controldestock.nucleo.RespuestaMisUbicaciones
import com.controldestock.nucleo.UbicacionAsignada

/**
 * Arma la lista de trabajo del operario y guarda lo que el servidor reparte.
 *
 * Sin lógica propia: solo traduce las entidades de Room a los tipos de
 * `nucleo`, que es donde vive la decisión de qué mostrar y en qué orden.
 * Del mismo tamaño que `Contador`, por el mismo motivo.
 */
class ListaDeTrabajo(private val base: BaseLocal) {

    suspend fun armar(): List<UbicacionAsignada> {
        val asignadas = base.asignacionDao().todas()
        val articulos = base.maestroDao().deUbicacionesAsignadas()
        val codigosPorArticulo = base.maestroDao().codigosDeUbicacionesAsignadas()
            .groupBy({ it.articuloId }, { it.codigo })

        val paraLista = articulos.map { articulo ->
            ArticuloParaLista(
                id = articulo.id,
                idOrden = articulo.idOrden,
                sku = articulo.sku,
                descripcion = articulo.descripcion,
                ubicacion = articulo.ubicacion,
                unidad = articulo.unidad,
                // Sin código propio, el SKU hace de código: es el mismo
                // respaldo que usa `Contador.registrar` al mandar el conteo.
                codigos = codigosPorArticulo[articulo.id] ?: listOf(articulo.sku),
            )
        }

        val vinculacion = base.vinculacionDao().actual()
        val conteos = base.conteoDao().todos().map {
            ConteoParaLista(it.articuloId, it.uuid, it.cantidad, it.anulaUuid, it.estadoSync, it.pasadaId)
        }
        val permitidos = base.pasadaItemDao().todos().toSet()

        return ListaAsignada.armar(
            asignadas, paraLista, conteos,
            pasadaActivaId = vinculacion?.pasadaId ?: 0,
            esParcial = vinculacion?.esParcial ?: false,
            articulosPermitidos = permitidos,
        )
    }

    /**
     * Guarda lo que reparte el servidor: las ubicaciones, los SKU permitidos
     * si la pasada activa es un recuento, y el estado de esa pasada.
     *
     * Es lo que le permite al celular enterarse de un recuento nuevo sin
     * volver a vincularse: el mismo refresco de siempre ahora también
     * actualiza en qué etapa está.
     */
    suspend fun guardar(respuesta: RespuestaMisUbicaciones) {
        base.asignacionDao().reemplazar(respuesta.ubicaciones)
        base.pasadaItemDao().reemplazar(respuesta.articulosPermitidos)

        base.vinculacionDao().actual()?.let { actual ->
            base.vinculacionDao().guardar(
                actual.copy(
                    pasadaId = respuesta.pasadaId,
                    pasadaNumero = respuesta.pasadaNumero,
                    pasadaEtiqueta = respuesta.pasadaEtiqueta,
                    esParcial = respuesta.esParcial,
                ),
            )
        }
    }
}
