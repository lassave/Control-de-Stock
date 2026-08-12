package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.Reloj
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

class RelojDeContador(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class ContadorTest {

    private lateinit var base: BaseLocal
    private val reloj = RelojDeContador("2026-08-12T10:00:00Z")

    @Before
    fun preparar() = runTest {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()

        base.maestroDao().reemplazarMaestro(
            articulos = listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", "P-1"),
                ),
                ArticuloEntidad(
                    id = 2, idOrden = 2, sku = "A-2", descripcion = "Harina",
                    unidad = "KG", ubicacion = "P-2", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Harina", "A-2", "P-2"),
                ),
            ),
            codigos = listOf(CodigoEntidad("7790001", 1), CodigoEntidad("7790002", 2)),
            unidades = listOf(
                UnidadEntidad("UN", "Unidad", 0),
                UnidadEntidad("KG", "Kilogramo", 1),
            ),
        )
    }

    @After
    fun terminar() = base.close()

    private fun contador() = Contador(base, reloj)

    @Test
    fun `encuentra el articulo por el codigo escaneado`() = runTest {
        val hallazgo = contador().buscar("7790001")

        assertTrue(hallazgo is Hallazgo.Encontrado)
        assertEquals("Fideos", (hallazgo as Hallazgo.Encontrado).articulo.descripcion)
    }

    @Test
    fun `dice si la unidad admite decimales`() = runTest {
        // Es lo que decide si medio kilo se carga sin preguntar o pide
        // confirmación.
        val fideos = contador().buscar("7790001") as Hallazgo.Encontrado
        val harina = contador().buscar("7790002") as Hallazgo.Encontrado

        assertEquals(false, fideos.admiteDecimales)
        assertEquals(true, harina.admiteDecimales)
    }

    @Test
    fun `un codigo que no esta en el maestro se reporta como desconocido`() = runTest {
        val hallazgo = contador().buscar("no-existe")

        assertEquals(Hallazgo.Desconocido("no-existe"), hallazgo)
    }

    @Test
    fun `una unidad que no esta en el catalogo no rompe el escaneo`() = runTest {
        // El maestro puede traer una unidad que no bajó: no se puede dejar al
        // operario sin poder contar por eso.
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = 3, idOrden = 3, sku = "A-3", descripcion = "Raro",
                    unidad = "XX", ubicacion = null, pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Raro", "A-3", null),
                ),
            ),
        )
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad("7790003", 3)))

        val hallazgo = contador().buscar("7790003") as Hallazgo.Encontrado

        assertEquals(false, hallazgo.admiteDecimales)
    }

    @Test
    fun `registrar guarda el conteo pendiente en la base local`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 48000, null, null)

        val guardado = base.conteoDao().todos().single()
        assertEquals(48000, guardado.cantidad)
        assertEquals("7790001", guardado.codigo)
        assertEquals(EstadoSync.PENDIENTE, guardado.estadoSync)
        assertEquals("2026-08-12T10:00:00Z", guardado.timestampDispositivo)
    }

    @Test
    fun `el conteo viaja con un codigo de barras real y no con el sku`() = runTest {
        // El servidor resuelve solo por código de barras. Mandar el SKU falla
        // en los artículos que tienen un código propio distinto.
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, null, null)

        assertEquals("7790001", base.conteoDao().todos().single().codigo)
    }

    @Test
    fun `guarda la ubicacion real y las observaciones cuando las hay`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, "P-9", "Estaba en otro estante")

        val guardado = base.conteoDao().todos().single()
        assertEquals("P-9", guardado.ubicacionReal)
        assertEquals("Estaba en otro estante", guardado.observaciones)
    }

    @Test
    fun `el conteo queda atado a la sesion del maestro`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, null, null)

        assertEquals(1, base.conteoDao().todos().single().sesionId)
    }

    @Test
    fun `dos escaneos del mismo articulo son dos conteos`() = runTest {
        // Dentro de una pasada los conteos suman: el mismo producto puede
        // estar en dos estantes.
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo

        contador().registrar(articulo, 1000, null, null)
        contador().registrar(articulo, 2000, null, null)

        assertEquals(2, base.conteoDao().todos().size)
    }

    @Test
    fun `las ubicaciones del maestro estan disponibles para corregir`() = runTest {
        assertEquals(listOf("P-1", "P-2"), contador().ubicaciones())
    }

    @Test
    fun `el alta deja el articulo, su codigo y su primer conteo`() = runTest {
        val articulo = contador().darDeAlta(
            codigo = "7790999", descripcion = "Pack por 6", unidad = "UN",
            ubicacion = "P-3", milesimas = 6000, observaciones = null,
        )

        assertEquals("Pack por 6", base.maestroDao().porCodigo("7790999")?.descripcion)
        val conteo = base.conteoDao().todos().single()
        assertEquals("7790999", conteo.codigo)
        assertEquals(6000, conteo.cantidad)
        assertEquals(articulo.id, conteo.articuloId)
    }

    @Test
    fun `el articulo dado de alta queda pendiente de crearse en el servidor`() = runTest {
        contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        val pendiente = base.maestroDao().altasPendientes().single()
        assertEquals("Pack por 6", pendiente.descripcion)
        assertEquals(EstadoSync.PENDIENTE.name, pendiente.estadoAlta)
    }

    @Test
    fun `el id del articulo dado de alta no pisa a ninguno del maestro`() = runTest {
        // Los del servidor son positivos. Sin esto, bajar el maestro de nuevo
        // reemplazaría el artículo nuevo por otro con el mismo número.
        val articulo = contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        assertTrue("el id tiene que ser negativo: ${articulo.id}", articulo.id < 0)
    }

    @Test
    fun `el segundo escaneo del producto recien dado de alta ya lo encuentra`() = runTest {
        // Es lo que hace que en una estantería de packs iguales el operario
        // escriba la descripción una sola vez.
        contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        val hallazgo = contador().buscar("7790999")

        assertTrue(hallazgo is Hallazgo.Encontrado)
        assertEquals("Pack por 6", (hallazgo as Hallazgo.Encontrado).articulo.descripcion)
    }

    @Test
    fun `el alta respeta la unidad elegida y si admite decimales`() = runTest {
        contador().darDeAlta("7790999", "Harina suelta", "KG", null, 3500, null)

        val hallazgo = contador().buscar("7790999") as Hallazgo.Encontrado

        assertEquals("KG", hallazgo.articulo.unidad)
        assertEquals(true, hallazgo.admiteDecimales)
    }

    @Test
    fun `el alta queda atada a la sesion y a la pasada del celular`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = "http://172.16.11.12:8000", token = "abc",
                operarioId = 1, operarioNombre = "Juan", sesionId = 7,
                pasadaId = 3, pasadaNumero = 2, pasadaEtiqueta = "Conteo 2",
            ),
        )

        val articulo = contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        assertEquals(7, articulo.sesionId)
        assertEquals(2, articulo.pasadaNumero)
        assertEquals(7, base.conteoDao().todos().single().sesionId)
    }

    @Test
    fun `los conteos de un articulo se pueden leer para avisar de repetidos`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo
        contador().registrar(articulo, 24000, null, null)

        val previos = contador().conteosDe(articulo)

        assertEquals(1, previos.size)
        assertEquals(24000, previos.single().evento.cantidad)
    }
}
