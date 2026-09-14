package com.controldestock.nucleo

/**
 * La lista de trabajo del operario: sus ubicaciones asignadas, con los
 * artículos de cada una y lo que ya contó.
 *
 * Todo sale de la base local — nada de esto consulta al servidor — porque
 * tiene que andar sin señal, que es el caso normal del depósito. Es lógica
 * pura a propósito: es la parte de la app con más valor en tener tests
 * rápidos, porque hoy casi nada de la pantalla se puede probar.
 */

/** Un artículo tal como lo tiene guardado el celular. */
data class ArticuloParaLista(
    val id: Int,
    val idOrden: Int,
    val sku: String,
    val descripcion: String,
    val ubicacion: String?,
    val unidad: String,
    val codigos: List<String>,
    // 'importado' o 'alta_rapida'. Por defecto «importado»: es lo que vale
    // para casi todos los tests existentes, que no le importa este campo.
    val origen: String = "importado",
)

/** Un conteo local, con solo lo que hace falta para saber si cuenta. */
data class ConteoParaLista(
    val articuloId: Int,
    val uuid: String,
    val cantidad: Int,
    val anulaUuid: String?,
    val estadoSync: EstadoSync,
    // A qué pasada pertenece. Antes de que existieran los recuentos, todos
    // los conteos eran del Conteo 1 y esto no hacía falta distinguirlo; con
    // recuentos concurrentes, un tilde del Conteo 1 no puede contar como
    // avance de un recuento que se abrió después sobre el mismo artículo.
    val pasadaId: Int = 0,
)

/** Un artículo dentro de la lista, con lo que el operario ya cargó. */
data class RenglonAsignado(
    val idOrden: Int,
    val sku: String,
    val descripcion: String,
    val codigos: String,
    val unidad: String,
    val contado: Int?,
    val articuloId: Int,
    // Nace de una alta rápida y no del maestro original.
    val agregado: Boolean = false,
) {
    val fueContado: Boolean get() = contado != null
}

data class UbicacionAsignada(val ubicacion: String, val renglones: List<RenglonAsignado>) {
    val contados: Int get() = renglones.count { it.fueContado }
    val total: Int get() = renglones.size
    val avance: String get() = "$ubicacion — $contados de $total"
}

object ListaAsignada {

    /**
     * Cuánto contó el operario de cada artículo, sumando lo vigente.
     *
     * La misma definición de «vigente» que usa el servidor: se descarta la
     * anulación —tiene `anulaUuid`— y el conteo anulado —su `uuid` es el
     * `anulaUuid` de otro—, y se descarta lo `RECHAZADO`. Lo `PENDIENTE`
     * cuenta: el tilde dice «yo ya lo conté», no «ya subió», porque tiene
     * que andar sin señal.
     */
    fun contadoPorArticulo(conteos: List<ConteoParaLista>): Map<Int, Int> {
        val anulados = conteos.mapNotNull { it.anulaUuid }.toSet()
        val vigentes = conteos.filter {
            it.estadoSync != EstadoSync.RECHAZADO &&
                it.anulaUuid == null &&
                it.uuid !in anulados
        }
        return vigentes
            .groupBy { it.articuloId }
            .mapValues { (_, propios) -> propios.sumOf { it.cantidad } }
    }

    /**
     * Arma la lista, una entrada por ubicación asignada.
     *
     * Una ubicación asignada sin artículos aparece igual, con «0 de 0»:
     * esconderla le haría creer al operario que no se la asignaron. Un
     * artículo de una ubicación no asignada no aparece, aunque lo haya
     * contado —la lista es el plan de trabajo, no el historial—.
     */
    fun armar(
        asignadas: List<String>,
        articulos: List<ArticuloParaLista>,
        conteos: List<ConteoParaLista>,
        pasadaActivaId: Int = 0,
        esParcial: Boolean = false,
        articulosPermitidos: Set<Int> = emptySet(),
    ): List<UbicacionAsignada> {
        // Un tilde de otra pasada no cuenta como avance de esta: un Conteo 1
        // ya cargado no puede maquillar el progreso de un recuento que se
        // abrió después sobre el mismo artículo.
        val contado = contadoPorArticulo(conteos.filter { it.pasadaId == pasadaActivaId })
        val porUbicacion = articulos
            .filter { it.ubicacion != null && it.ubicacion in asignadas }
            // Fuera de un recuento parcial, no hay recorte: aparece todo lo
            // asignado, como siempre.
            .filter { !esParcial || it.id in articulosPermitidos }
            .groupBy { it.ubicacion!! }

        return asignadas.sorted().map { ubicacion ->
            val renglones = porUbicacion[ubicacion].orEmpty()
                .sortedBy { it.idOrden }
                .map { articulo ->
                    RenglonAsignado(
                        idOrden = articulo.idOrden,
                        sku = articulo.sku,
                        descripcion = articulo.descripcion,
                        codigos = articulo.codigos.joinToString(", "),
                        unidad = articulo.unidad,
                        contado = contado[articulo.id],
                        articuloId = articulo.id,
                        agregado = articulo.origen == "alta_rapida",
                    )
                }
            UbicacionAsignada(ubicacion, renglones)
        }
    }
}
