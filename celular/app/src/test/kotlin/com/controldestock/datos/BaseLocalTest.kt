package com.controldestock.datos

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

class RelojFijoDeDatos(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class BaseLocalTest {

    private lateinit var base: BaseLocal
    private val reloj = RelojFijoDeDatos("2026-08-11T10:00:00Z")

    @Before
    fun abrir() {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
    }

    @After
    fun cerrar() = base.close()

    private fun articulo(id: Int, sku: String, unidad: String = "UN") = ArticuloEntidad(
        id = id, idOrden = id, sku = sku, descripcion = "Artículo $sku",
        unidad = unidad, ubicacion = "P-1", pasadaNumero = 1,
    )

    @Test
    fun `guarda el maestro y lo devuelve ordenado por numero de orden`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(2, "B"), articulo(1, "A")),
            codigos = emptyList(),
            unidades = emptyList(),
        )

        val guardados = base.maestroDao().articulos()

        assertEquals(listOf("A", "B"), guardados.map { it.sku })
    }

    @Test
    fun `encuentra un articulo por su codigo de barras`() = runTest {
        base.maestroDao().reemplazarMaestro(
            articulos = listOf(articulo(1, "A")),
            codigos = listOf(CodigoEntidad("7790001001234", 1)),
            unidades = emptyList(),
        )

        val encontrado = base.maestroDao().porCodigo("7790001001234")

        assertEquals("A", encontrado?.sku)
    }

    @Test
    fun `un codigo que no esta devuelve null`() = runTest {
        assertNull(base.maestroDao().porCodigo("no-existe"))
    }

    @Test
    fun `reemplazar el maestro no deja restos del anterior`() = runTest {
        // Al reimportar, un artículo que ya no está en el maestro no puede
        // seguir apareciendo en la búsqueda del operario.
        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "VIEJO")), emptyList(), emptyList())

        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "NUEVO")), emptyList(), emptyList())

        assertEquals(listOf("NUEVO"), base.maestroDao().articulos().map { it.sku })
    }

    @Test
    fun `busca por descripcion sku y ubicacion sin distinguir mayusculas`() = runTest {
        // Es lo que destraba la etiqueta rota: el operario busca a mano.
        base.maestroDao().reemplazarMaestro(
            listOf(
                ArticuloEntidad(1, 1, sku = "10453", descripcion = "Tornillo hexagonal",
                    unidad = "UN", ubicacion = "A-03", pasadaNumero = 1),
                ArticuloEntidad(2, 2, sku = "10454", descripcion = "Tuerca",
                    unidad = "UN", ubicacion = "B-01", pasadaNumero = 1),
            ),
            emptyList(), emptyList(),
        )

        assertEquals(listOf("10453"), base.maestroDao().buscar("torni").map { it.sku })
        assertEquals(listOf("10453"), base.maestroDao().buscar("10453").map { it.sku })
        assertEquals(listOf("10454"), base.maestroDao().buscar("b-01").map { it.sku })
    }

    @Test
    fun `guarda un conteo como pendiente`() = runTest {
        val evento = EventoConteo.nuevo("7790001001234", 48000, reloj)

        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 1))

        val guardado = base.conteoDao().todos().single()
        assertEquals(EstadoSync.PENDIENTE, guardado.estadoSync)
        assertEquals(48000, guardado.cantidad)
        assertEquals(0, guardado.fueraAsignacion)
    }

    @Test
    fun `lo guardado sobrevive con la misma clave`() = runTest {
        // El uuid es la clave: guardar dos veces el mismo evento no puede
        // duplicar el conteo.
        val evento = EventoConteo.nuevo("A", 1000, reloj)

        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 1))
        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 1))

        assertEquals(1, base.conteoDao().todos().size)
    }

    @Test
    fun `devuelve los conteos del mas nuevo al mas viejo`() = runTest {
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo("A", 1000, RelojFijoDeDatos("2026-08-11T10:00:00Z")), 1),
        )
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo("B", 1000, RelojFijoDeDatos("2026-08-11T11:00:00Z")), 2),
        )

        assertEquals(listOf("B", "A"), base.conteoDao().todos().map { it.codigo })
    }

    @Test
    fun `cuenta los pendientes para el indicador`() = runTest {
        base.conteoDao().guardar(ConteoEntidad.de(EventoConteo.nuevo("A", 1000, reloj), 1))
        val enviado = ConteoEntidad.de(EventoConteo.nuevo("B", 1000, reloj), 2)
            .copy(estadoSync = EstadoSync.ENVIADO)
        base.conteoDao().guardar(enviado)

        assertEquals(1, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `marca un conteo como rechazado con su motivo`() = runTest {
        val evento = EventoConteo.nuevo("A", 1000, reloj)
        base.conteoDao().guardar(ConteoEntidad.de(evento, 1))

        base.conteoDao().marcar(evento.uuid, EstadoSync.RECHAZADO, "Código desconocido")

        val guardado = base.conteoDao().todos().single()
        assertEquals(EstadoSync.RECHAZADO, guardado.estadoSync)
        assertEquals("Código desconocido", guardado.motivoRechazo)
    }

    @Test
    fun `devuelve solo los pendientes en orden de carga`() = runTest {
        base.conteoDao().guardar(ConteoEntidad.de(EventoConteo.nuevo("A", 1000, reloj), 1))
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo("B", 1000, reloj), 2)
                .copy(estadoSync = EstadoSync.ENVIADO),
        )
        base.conteoDao().guardar(ConteoEntidad.de(EventoConteo.nuevo("C", 1000, reloj), 3))

        val pendientes = base.conteoDao().porEstado(EstadoSync.PENDIENTE)

        assertEquals(listOf("A", "C"), pendientes.map { it.codigo })
    }

    @Test
    fun `un conteo ida y vuelta conserva todos sus campos`() = runTest {
        // La entidad es la que cruza el límite con el núcleo: si pierde un
        // campo en el camino, el conteo llega incompleto al servidor.
        val evento = EventoConteo.nuevo(
            "A", 3500, reloj,
            ubicacionReal = "P-9", observaciones = "Estaba en otro estante",
        )

        base.conteoDao().guardar(ConteoEntidad.de(evento, articuloId = 7))

        assertEquals(evento, base.conteoDao().todos().single().aEvento())
    }

    @Test
    fun `guarda y devuelve la vinculacion`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = "http://172.16.11.12:8000", token = "abc",
                operarioId = 1, operarioNombre = "Juan",
                sesionId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )

        val guardada = base.vinculacionDao().actual()

        assertEquals("Juan", guardada?.operarioNombre)
        assertEquals("Conteo 1", guardada?.pasadaEtiqueta)
    }

    @Test
    fun `vincular de nuevo reemplaza la vinculacion anterior`() = runTest {
        // Un celular que se revincula con otro operario no puede quedar con
        // los dos: los conteos se atribuirían a quien no contó.
        val primera = VinculacionEntidad(
            url = "http://a", token = "t1", operarioId = 1, operarioNombre = "Juan",
            sesionId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
        )
        base.vinculacionDao().guardar(primera)

        base.vinculacionDao().guardar(primera.copy(token = "t2", operarioNombre = "Ana"))

        assertEquals("Ana", base.vinculacionDao().actual()?.operarioNombre)
        assertEquals("t2", base.vinculacionDao().actual()?.token)
    }

    @Test
    fun `sin vincular no hay vinculacion`() = runTest {
        assertNull(base.vinculacionDao().actual())
    }
}
