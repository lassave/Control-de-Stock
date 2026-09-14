package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ListaAsignadaTest {

    private fun articulo(
        id: Int, idOrden: Int, sku: String, ubicacion: String?,
        codigos: List<String> = listOf(sku), descripcion: String = "Producto $sku",
    ) = ArticuloParaLista(id, idOrden, sku, descripcion, ubicacion, "UN", codigos)

    private fun conteo(
        articuloId: Int, cantidad: Int, uuid: String = "u-$articuloId-$cantidad",
        anula: String? = null, estado: EstadoSync = EstadoSync.PENDIENTE, pasadaId: Int = 0,
    ) = ConteoParaLista(articuloId, uuid, cantidad, anula, estado, pasadaId)

    // --- contadoPorArticulo --------------------------------------------------

    @Test
    fun `un conteo pendiente cuenta`() {
        val contado = ListaAsignada.contadoPorArticulo(listOf(conteo(1, 5000)))

        assertEquals(5000, contado[1])
    }

    @Test
    fun `un conteo rechazado no cuenta`() {
        val contado = ListaAsignada.contadoPorArticulo(
            listOf(conteo(1, 5000, estado = EstadoSync.RECHAZADO))
        )

        assertTrue(contado.isEmpty())
    }

    @Test
    fun `una anulacion descarta el par`() {
        val contado = ListaAsignada.contadoPorArticulo(listOf(
            conteo(1, 5000, uuid = "original"),
            conteo(1, 0, uuid = "anulacion", anula = "original"),
        ))

        assertTrue(contado.isEmpty())
    }

    @Test
    fun `la cantidad es la suma de los conteos vigentes`() {
        val contado = ListaAsignada.contadoPorArticulo(listOf(
            conteo(1, 5000, uuid = "u1"),
            conteo(1, 3000, uuid = "u2"),
        ))

        assertEquals(8000, contado[1])
    }

    // --- armar -----------------------------------------------------------------

    @Test
    fun `los renglones salen ordenados por id_orden`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 30, sku = "C", ubicacion = "P-1"),
                articulo(id = 2, idOrden = 10, sku = "A", ubicacion = "P-1"),
                articulo(id = 3, idOrden = 20, sku = "B", ubicacion = "P-1"),
            ),
            conteos = emptyList(),
        )

        assertEquals(listOf("A", "B", "C"), lista.single().renglones.map { it.sku })
    }

    @Test
    fun `un articulo con dos codigos los muestra separados por coma`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1",
                    codigos = listOf("111", "222")),
            ),
            conteos = emptyList(),
        )

        assertEquals("111, 222", lista.single().renglones.single().codigos)
    }

    @Test
    fun `una ubicacion asignada sin articulos igual aparece con 0 de 0`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-9"),
            articulos = emptyList(),
            conteos = emptyList(),
        )

        assertEquals(1, lista.size)
        assertEquals("P-9 — 0 de 0", lista.single().avance)
    }

    @Test
    fun `un articulo de una ubicacion no asignada no aparece`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-9")),
            conteos = emptyList(),
        )

        assertTrue(lista.single().renglones.isEmpty())
    }

    @Test
    fun `sin ninguna ubicacion asignada devuelve lista vacia`() {
        val lista = ListaAsignada.armar(
            asignadas = emptyList(),
            articulos = listOf(articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = emptyList(),
        )

        assertTrue(lista.isEmpty())
    }

    @Test
    fun `el texto del avance es exactamente P-3 — 12 de 40`() {
        val articulos = (1..40).map {
            articulo(id = it, idOrden = it, sku = "SKU$it", ubicacion = "P-3")
        }
        val conteos = (1..12).map { conteo(it, 1000, uuid = "u$it") }

        val lista = ListaAsignada.armar(listOf("P-3"), articulos, conteos)

        assertEquals("P-3 — 12 de 40", lista.single().avance)
    }

    @Test
    fun `el tilde marca solo lo contado`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1"),
                articulo(id = 2, idOrden = 2, sku = "B", ubicacion = "P-1"),
            ),
            conteos = listOf(conteo(1, 5000)),
        )

        val renglones = lista.single().renglones.associateBy { it.sku }
        assertTrue(renglones.getValue("A").fueContado)
        assertTrue(!renglones.getValue("B").fueContado)
    }

    @Test
    fun `un alta rapida cae en su ubicacion ya tildada`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-9"),
            articulos = listOf(
                articulo(id = -1, idOrden = 999, sku = "7790009999999", ubicacion = "P-9"),
            ),
            conteos = listOf(conteo(-1, 3000)),
        )

        assertTrue(lista.single().renglones.single().fueContado)
    }

    @Test
    fun `las ubicaciones salen ordenadas alfabeticamente`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-9", "P-1", "P-3"),
            articulos = emptyList(),
            conteos = emptyList(),
        )

        assertEquals(listOf("P-1", "P-3", "P-9"), lista.map { it.ubicacion })
    }

    // --- pasada activa -----------------------------------------------------------

    @Test
    fun `un tilde de otra pasada no cuenta como contado`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = listOf(conteo(1, 5000, pasadaId = 1)),
            pasadaActivaId = 2,
        )

        assertTrue(!lista.single().renglones.single().fueContado)
    }

    @Test
    fun `un tilde de la pasada activa si cuenta`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = listOf(conteo(1, 5000, pasadaId = 2)),
            pasadaActivaId = 2,
        )

        assertTrue(lista.single().renglones.single().fueContado)
    }

    @Test
    fun `en un recuento parcial solo aparecen los articulos permitidos`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1"),
                articulo(id = 2, idOrden = 2, sku = "B", ubicacion = "P-1"),
            ),
            conteos = emptyList(),
            pasadaActivaId = 2,
            esParcial = true,
            articulosPermitidos = setOf(1),
        )

        assertEquals(listOf("A"), lista.single().renglones.map { it.sku })
    }

    @Test
    fun `fuera de un recuento parcial aparecen todos los articulos asignados`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1"),
                articulo(id = 2, idOrden = 2, sku = "B", ubicacion = "P-1"),
            ),
            conteos = emptyList(),
            pasadaActivaId = 1,
        )

        assertEquals(listOf("A", "B"), lista.single().renglones.map { it.sku })
    }

    @Test
    fun `cada renglon lleva el id del articulo`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 42, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = emptyList(),
        )

        assertEquals(42, lista.single().renglones.single().articuloId)
    }

    @Test
    fun `un articulo de alta rapida se marca como agregado`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(
                articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")
                    .copy(origen = "alta_rapida"),
            ),
            conteos = emptyList(),
        )

        assertTrue(lista.single().renglones.single().agregado)
    }

    @Test
    fun `un articulo del maestro original no se marca como agregado`() {
        val lista = ListaAsignada.armar(
            asignadas = listOf("P-1"),
            articulos = listOf(articulo(id = 1, idOrden = 1, sku = "A", ubicacion = "P-1")),
            conteos = emptyList(),
        )

        assertFalse(lista.single().renglones.single().agregado)
    }
}
