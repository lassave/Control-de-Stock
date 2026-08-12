package com.controldestock.nucleo

/**
 * Si ese artículo ya se contó en esa misma ubicación.
 *
 * Un SKU se cuenta una sola vez por ubicación: todo lo que hay de ese
 * producto en ese estante se cuenta junto y se carga junto. Un segundo
 * escaneo en el mismo lugar no es un estante nuevo, es que el operario
 * perdió la cuenta, y si entra callado el inventario termina con unidades de
 * más que nadie va a poder explicar.
 *
 * Entre ubicaciones distintas no avisa: el mismo producto sí puede estar en
 * dos estantes, y ahí los conteos suman.
 *
 * Es lógica pura a propósito: la pantalla la consulta al confirmar, sin
 * tocar la red ni esperar a nadie.
 */
object Repeticion {

    data class YaContado(
        val milesimas: Int,
        /** Cuándo se cargó, en UTC. Se muestra en hora local. */
        val cuando: String,
    )

    /**
     * @param previos los conteos de ese mismo artículo en este celular.
     * @param ubicacionDelArticulo la que trae el maestro.
     * @param ubicacionElegida la que el operario corrigió, si corrigió alguna.
     */
    fun buscar(
        previos: List<ConteoLocal>,
        ubicacionDelArticulo: String?,
        ubicacionElegida: String?,
    ): YaContado? {
        val donde = ubicacionElegida ?: ubicacionDelArticulo

        return previos
            .filter { it.estadoSync != EstadoSync.RECHAZADO }
            .filter { it.evento.anulaUuid == null }
            .lastOrNull { (it.evento.ubicacionReal ?: ubicacionDelArticulo) == donde }
            ?.let { YaContado(it.evento.cantidad, it.evento.timestampDispositivo) }
    }
}
