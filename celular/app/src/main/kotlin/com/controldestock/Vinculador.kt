package com.controldestock

import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor

sealed class ResultadoDeVinculacion {
    data class Vinculado(val operario: String, val sesion: String) : ResultadoDeVinculacion()
    data class Fallo(val mensaje: String) : ResultadoDeVinculacion()
}

/**
 * Vincula el celular y le deja el maestro listo para contar sin señal.
 *
 * Las dos cosas van juntas a propósito: un celular vinculado sin maestro
 * abre la cámara y rechaza todo lo que se escanee, que es peor que no estar
 * vinculado, porque parece que funciona.
 */
class Vinculador(
    private val base: BaseLocal,
    private val crearCliente: (String, String) -> ClienteServidor,
) {

    suspend fun vincular(datos: DatosDelQr): ResultadoDeVinculacion {
        val cliente = crearCliente(datos.url, datos.token)

        return try {
            // Las dos llamadas van antes de cualquier escritura: si el
            // servidor no contesta, el celular queda como estaba.
            val quien = cliente.vincular()
            val maestro = cliente.maestro()

            base.vincularA(
                VinculacionEntidad(
                    url = datos.url,
                    token = datos.token,
                    operarioId = quien.operario.id,
                    operarioNombre = quien.operario.nombre,
                    sesionId = quien.sesion.id,
                    pasadaId = quien.pasada.id,
                    pasadaNumero = quien.pasada.numero,
                    pasadaEtiqueta = quien.pasada.etiqueta,
                ),
            )

            base.maestroDao().reemplazarMaestro(
                articulos = maestro.articulos.map {
                    ArticuloEntidad(
                        id = it.id, idOrden = it.idOrden, tipo = it.tipo,
                        material = it.material, sku = it.sku,
                        descripcion = it.descripcion, grupo = it.grupo,
                        ubicacion = it.ubicacion, unidad = it.unidad,
                        pasadaNumero = quien.pasada.numero,
                        sesionId = quien.sesion.id,
                        busqueda = textoDeBusqueda(it.descripcion, it.sku, it.ubicacion),
                    )
                },
                codigos = maestro.codigos.map { CodigoEntidad(it.codigo, it.articuloId) },
                unidades = maestro.unidades.map {
                    UnidadEntidad(it.codigo, it.nombre, it.admiteDecimales)
                },
            )

            ResultadoDeVinculacion.Vinculado(quien.operario.nombre, quien.sesion.nombre)
        } catch (error: ErrorDeServidor) {
            ResultadoDeVinculacion.Fallo(error.message.orEmpty())
        }
    }
}
