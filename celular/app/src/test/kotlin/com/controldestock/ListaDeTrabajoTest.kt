package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.ConteoEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

private class RelojFijo(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class ListaDeTrabajoTest {

    private lateinit var base: BaseLocal
    private lateinit var lista: ListaDeTrabajo
    private val reloj = RelojFijo("2026-08-17T10:00:00Z")

    @Before
    fun abrir() {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
        lista = ListaDeTrabajo(base)
    }

    @After
    fun cerrar() = base.close()

    private fun articulo(id: Int, sku: String, ubicacion: String?) = ArticuloEntidad(
        id = id, idOrden = id, sku = sku, descripcion = "Producto $sku",
        unidad = "UN", ubicacion = ubicacion, pasadaNumero = 1, sesionId = 1,
        busqueda = textoDeBusqueda("Producto $sku", sku, ubicacion),
    )

    @Test
    fun `arma la lista con lo asignado, sus codigos y lo contado`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(1, "A", "P-1"), articulo(2, "B", "P-9")),
            codigos = listOf(CodigoEntidad("111", 1), CodigoEntidad("222", 1)),
            unidades = emptyList(),
        )
        base.asignacionDao().reemplazar(listOf("P-1"))
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo("111", 5000, reloj), articuloId = 1),
        )

        val armada = lista.armar()

        assertEquals(1, armada.size)
        val renglon = armada.single().renglones.single()
        assertEquals("A", renglon.sku)
        assertEquals("111, 222", renglon.codigos)
        assertEquals(5000, renglon.contado)
    }

    @Test
    fun `un articulo sin codigo propio usa el sku`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(1, "A", "P-1")), codigos = emptyList(), unidades = emptyList(),
        )
        base.asignacionDao().reemplazar(listOf("P-1"))

        assertEquals("A", lista.armar().single().renglones.single().codigos)
    }

    @Test
    fun `guardar reemplaza el reparto`() = runTest {
        lista.guardar(listOf("P-1", "P-2"))

        lista.guardar(listOf("P-3"))

        assertEquals(listOf("P-3"), base.asignacionDao().todas())
    }
}
