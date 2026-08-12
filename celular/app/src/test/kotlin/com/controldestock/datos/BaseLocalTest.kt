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
        unidad = unidad, ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
        busqueda = textoDeBusqueda("Artículo $sku", sku, "P-1"),
    )

    private fun vinculacionDe(sesionId: Int, operario: String = "Juan") = VinculacionEntidad(
        url = "http://172.16.11.12:8000", token = "t-$sesionId",
        operarioId = 1, operarioNombre = operario,
        sesionId = sesionId, pasadaId = sesionId,
        pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
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

    private fun paraBuscar(id: Int, sku: String, descripcion: String, ubicacion: String) =
        ArticuloEntidad(
            id = id, idOrden = id, sku = sku, descripcion = descripcion,
            unidad = "UN", ubicacion = ubicacion, pasadaNumero = 1, sesionId = 1,
            busqueda = textoDeBusqueda(descripcion, sku, ubicacion),
        )

    @Test
    fun `busca por descripcion sku y ubicacion sin distinguir mayusculas`() = runTest {
        // Es lo que destraba la etiqueta rota: el operario busca a mano.
        base.maestroDao().reemplazarMaestro(
            listOf(
                paraBuscar(1, "10453", "Tornillo hexagonal", "A-03"),
                paraBuscar(2, "10454", "Tuerca", "B-01"),
            ),
            emptyList(), emptyList(),
        )

        assertEquals(listOf("10453"), base.maestroDao().buscar("torni").map { it.sku })
        assertEquals(listOf("10453"), base.maestroDao().buscar("10453").map { it.sku })
        assertEquals(listOf("10454"), base.maestroDao().buscar("b-01").map { it.sku })
    }

    @Test
    fun `busca con eñes y acentos aunque el maestro venga en mayusculas`() = runTest {
        // Los maestros de ERP vienen en mayúsculas y el castellano está lleno
        // de CAÑO, TAMAÑO, ARTÍCULO. El LIKE de SQLite solo pliega mayúsculas
        // en ASCII, así que sin normalizar, «caño» no encuentra «CAÑO».
        base.maestroDao().reemplazarMaestro(
            listOf(
                paraBuscar(1, "A-1", "CAÑO GALVANIZADO 3/4", "P-1"),
                paraBuscar(2, "A-2", "ARTÍCULO DE LIMPIEZA", "P-2"),
            ),
            emptyList(), emptyList(),
        )

        assertEquals(listOf("A-1"), base.maestroDao().buscar("caño").map { it.sku })
        assertEquals(listOf("A-1"), base.maestroDao().buscar("cano").map { it.sku })
        assertEquals(listOf("A-2"), base.maestroDao().buscar("articulo").map { it.sku })
        assertEquals(listOf("A-2"), base.maestroDao().buscar("ARTÍCULO").map { it.sku })
    }

    @Test
    fun `devuelve un codigo de barras del articulo para poder contarlo`() = runTest {
        // El conteo viaja con el código, no con el id, y el servidor resuelve
        // solo por código. Sin esto, lo que el operario encuentra desde
        // «Buscar» no se puede cargar.
        base.maestroDao().reemplazarMaestro(
            listOf(articulo(1, "A")),
            listOf(CodigoEntidad("7790001001234", 1)),
            emptyList(),
        )

        assertEquals("7790001001234", base.maestroDao().codigoDe(1))
    }

    @Test
    fun `un articulo sin codigo asociado devuelve null`() = runTest {
        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "A")), emptyList(), emptyList())

        assertNull(base.maestroDao().codigoDe(1))
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
        val primera = vinculacionDe(sesionId = 1)
        base.vinculacionDao().guardar(primera)

        base.vinculacionDao().guardar(primera.copy(token = "t2", operarioNombre = "Ana"))

        assertEquals("Ana", base.vinculacionDao().actual()?.operarioNombre)
        assertEquals("t2", base.vinculacionDao().actual()?.token)
    }

    @Test
    fun `vincular a otra sesion borra el maestro y los conteos anteriores`() = runTest {
        // Un pendiente que quedó de un inventario cerrado se sincronizaría
        // contra la sesión abierta hoy: el servidor resuelve por «la» sesión
        // abierta, así que el conteo de ayer entraría al inventario de hoy sin
        // que nada lo señale.
        base.vincularA(vinculacionDe(sesionId = 1))
        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "VIEJO")), emptyList(), emptyList())
        base.conteoDao().guardar(ConteoEntidad.de(EventoConteo.nuevo("A", 1000, reloj), 1, 1))

        base.vincularA(vinculacionDe(sesionId = 2, operario = "Ana"))

        assertEquals(emptyList<ConteoEntidad>(), base.conteoDao().todos())
        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().articulos())
        assertEquals(2, base.vinculacionDao().actual()?.sesionId)
    }

    @Test
    fun `vincular a la misma sesion conserva los conteos pendientes`() = runTest {
        // Cambio de operario o token renovado dentro del mismo inventario: lo
        // que todavía no subió sigue siendo válido y no se puede tirar.
        base.vincularA(vinculacionDe(sesionId = 1))
        base.maestroDao().reemplazarMaestro(listOf(articulo(1, "A")), emptyList(), emptyList())
        base.conteoDao().guardar(ConteoEntidad.de(EventoConteo.nuevo("A", 1000, reloj), 1, 1))

        base.vincularA(vinculacionDe(sesionId = 1, operario = "Ana"))

        assertEquals(1, base.conteoDao().todos().size)
        assertEquals(1, base.maestroDao().articulos().size)
    }

    @Test
    fun `sin vincular no hay vinculacion`() = runTest {
        assertNull(base.vinculacionDao().actual())
    }

    @Test
    fun `reemplazar el maestro conserva el alta que no subio`() = runTest {
        // Si se la llevara, el conteo que ya cargó el operario quedaría
        // apuntando a un código que la base no conoce, y el servidor lo
        // rechaza para siempre.
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = "7790999", descripcion = "Pack por 6",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Pack por 6", "7790999", null),
                    estadoAlta = EstadoSync.PENDIENTE.name,
                ),
            ),
        )
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad("7790999", -1)))

        base.maestroDao().reemplazarMaestro(
            articulos = listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", null),
                ),
            ),
            codigos = listOf(CodigoEntidad("7790001", 1)),
            unidades = listOf(UnidadEntidad("UN", "Unidad", 0)),
        )

        assertEquals("Pack por 6", base.maestroDao().porCodigo("7790999")?.descripcion)
        assertEquals(1, base.maestroDao().altasPendientes().size)
    }

    @Test
    fun `reemplazar el maestro se lleva el alta que ya subio`() = runTest {
        // Esa ya existe del otro lado: si se quedara, el maestro nuevo la
        // traería otra vez con su id de verdad y el operario vería el mismo
        // producto dos veces.
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = "7790999", descripcion = "Pack por 6",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Pack por 6", "7790999", null),
                    estadoAlta = EstadoSync.ENVIADO.name,
                ),
            ),
        )

        base.maestroDao().reemplazarMaestro(emptyList(), emptyList(), emptyList())

        assertNull(base.maestroDao().porId(-1))
    }

    @Test
    fun `vincularse a otro inventario no deja ni las altas pendientes`() = runTest {
        base.vinculacionDao().guardar(vinculacionDe(sesionId = 1))
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = "7790999", descripcion = "Pack por 6",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Pack por 6", "7790999", null),
                    estadoAlta = EstadoSync.PENDIENTE.name,
                ),
            ),
        )

        base.vincularA(vinculacionDe(sesionId = 2))

        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
    }

    @Test
    fun `el id del articulo local es negativo y no pisa al maestro`() = runTest {
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", null),
                ),
            ),
        )

        assertEquals(-1, base.maestroDao().proximoIdLocal())
        assertEquals(2, base.maestroDao().proximoOrden())
    }
}
