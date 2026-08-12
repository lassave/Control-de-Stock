package com.controldestock

import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.ConteoEntidad
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj

sealed class Hallazgo {
    data class Encontrado(
        val articulo: ArticuloEntidad,
        val admiteDecimales: Boolean,
        val codigo: String,
    ) : Hallazgo()

    data class Desconocido(val codigo: String) : Hallazgo()
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

        val evento = EventoConteo.nuevo(
            codigo = codigo,
            cantidad = milesimas,
            reloj = reloj,
            ubicacionReal = ubicacionReal,
            observaciones = observaciones,
        )

        base.conteoDao().guardar(
            ConteoEntidad.de(evento, articulo.id, articulo.sesionId),
        )
    }
}
