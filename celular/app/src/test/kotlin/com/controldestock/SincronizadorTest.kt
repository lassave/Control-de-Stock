package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.ConteoEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.EstadoSync
import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import com.controldestock.red.ClienteServidor
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

class RelojDeSync(private val instante: String) : Reloj {
    override fun ahora() = instante
}

@RunWith(RobolectricTestRunner::class)
class SincronizadorTest {

    private lateinit var base: BaseLocal
    private lateinit var servidor: MockWebServer
    private val reloj = RelojDeSync("2026-08-12T10:00:00Z")

    @Before
    fun preparar() = runTest {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
        servidor = MockWebServer()
        servidor.start()

        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = servidor.url("/").toString().trimEnd('/'), token = "token",
                operarioId = 1, operarioNombre = "Juan", sesionId = 1,
                pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )
        base.maestroDao().reemplazarMaestro(
            listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", "P-1"),
                ),
            ),
            listOf(CodigoEntidad("7790001", 1)),
            emptyList(),
        )
    }

    @After
    fun terminar() {
        base.close()
        servidor.shutdown()
    }

    private fun responder(cuerpo: String, codigo: Int = 200) {
        servidor.enqueue(
            MockResponse().setResponseCode(codigo)
                .setHeader("Content-Type", "application/json").setBody(cuerpo),
        )
    }

    private fun sincronizador() =
        Sincronizador(base) { url, token -> ClienteServidor(url, token) }

    private suspend fun guardarPendiente(codigo: String = "7790001") {
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo(codigo, 1000, reloj), 1, 1),
        )
    }

    private suspend fun guardarAlta(
        codigo: String = "7790999",
        descripcion: String = "Pack por 6",
        unidad: String = "UN",
    ) {
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = codigo, descripcion = descripcion,
                    unidad = unidad, pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda(descripcion, codigo, null),
                    estadoAlta = EstadoSync.PENDIENTE.name,
                ),
            ),
        )
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad(codigo, -1)))
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo(codigo, 6000, reloj), -1, 1),
        )
    }

    @Test
    fun `manda los pendientes y los marca como enviados`() = runTest {
        guardarPendiente()
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(1, resultado.enviados)
        assertEquals(0, base.conteoDao().cantidadPendientes())
        assertEquals(EstadoSync.ENVIADO, base.conteoDao().todos().single().estadoSync)
    }

    @Test
    fun `sin pendientes no molesta al servidor`() = runTest {
        val resultado = sincronizador().sincronizar()

        assertEquals(0, resultado.enviados)
        assertEquals(0, servidor.requestCount)
    }

    @Test
    fun `sin vinculacion no hace nada`() = runTest {
        base.vinculacionDao().borrar()
        guardarPendiente()

        val resultado = sincronizador().sincronizar()

        assertEquals(0, servidor.requestCount)
        assertEquals(1, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `un rechazo definitivo queda marcado con su motivo`() = runTest {
        guardarPendiente("no-existe")
        val uuid = base.conteoDao().todos().single().uuid
        responder(
            """{"registrados":0,"duplicados":0,"rechazados":[
                {"uuid":"$uuid","motivo":"Código desconocido","reintentable":false}]}""",
        )

        val resultado = sincronizador().sincronizar()

        assertEquals(1, resultado.rechazados)
        val guardado = base.conteoDao().todos().single()
        assertEquals(EstadoSync.RECHAZADO, guardado.estadoSync)
        assertEquals("Código desconocido", guardado.motivoRechazo)
    }

    @Test
    fun `si el servidor no contesta el conteo sigue pendiente`() = runTest {
        // Es el caso normal del depósito: nada se pierde, se reintenta.
        guardarPendiente()
        servidor.shutdown()

        val resultado = sincronizador().sincronizar()

        assertTrue(resultado.huboError)
        assertEquals(1, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `un duplicado no vuelve a quedar pendiente`() = runTest {
        // El servidor ya lo tenía: reenviar fue inofensivo y no hay nada que
        // arreglar de este lado.
        guardarPendiente()
        responder("""{"registrados":0,"duplicados":1,"rechazados":[]}""")

        sincronizador().sincronizar()

        assertEquals(0, base.conteoDao().cantidadPendientes())
    }

    @Test
    fun `la anulacion de un conteo rechazado no se reintenta para siempre`() = runTest {
        // Sin esto la cola nunca se vacía: el servidor rechaza la anulación
        // como reintentable porque el conteo que anula nunca le llegó.
        guardarPendiente("no-existe")
        val original = base.conteoDao().todos().single()
        base.conteoDao().marcar(original.uuid, EstadoSync.RECHAZADO, "Código desconocido")
        base.conteoDao().guardar(
            ConteoEntidad.de(
                EventoConteo.anulacionDe(original.aEvento(), reloj), 1, 1,
            ),
        )

        val resultado = sincronizador().sincronizar()

        assertEquals(0, servidor.requestCount)
        assertEquals(0, base.conteoDao().cantidadPendientes())
        assertEquals(0, resultado.enviados)
    }

    @Test
    fun `el articulo dado de alta sube antes que su conteo`() = runTest {
        // Al reves el conteo se pierde: el servidor rechaza para siempre un
        // codigo que no conoce.
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Pack por 6","unidad":"UN","creado":true}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        sincronizador().sincronizar()

        assertEquals("/api/dispositivo/articulos", servidor.takeRequest().path)
        assertEquals("/api/dispositivo/conteos", servidor.takeRequest().path)
        assertEquals(0, base.conteoDao().cantidadPendientes())
        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
    }

    @Test
    fun `sin red el alta y su conteo siguen esperando`() = runTest {
        guardarAlta()
        servidor.shutdown()

        val resultado = sincronizador().sincronizar()

        assertTrue(resultado.huboError)
        assertEquals(1, base.conteoDao().cantidadPendientes())
        assertEquals(1, base.maestroDao().altasPendientes().size)
    }

    @Test
    fun `un alta rechazada para siempre cierra sus conteos`() = runTest {
        // Sin esto la cola nunca se vacia: el articulo no va a existir jamas,
        // asi que sus conteos se reintentarian para siempre.
        guardarAlta(unidad = "XX")
        responder("""{"detail":"La unidad «XX» no está en el catálogo"}""", codigo = 400)

        sincronizador().sincronizar()

        assertEquals(0, base.conteoDao().cantidadPendientes())
        val conteo = base.conteoDao().todos().single()
        assertEquals(EstadoSync.RECHAZADO, conteo.estadoSync)
        assertEquals("La unidad «XX» no está en el catálogo", conteo.motivoRechazo)
        assertEquals(
            "La unidad «XX» no está en el catálogo",
            base.maestroDao().porId(-1)?.motivoRechazo,
        )
    }

    @Test
    fun `un codigo que ya existia no es un error`() = runTest {
        // Otro operario lo dio de alta hace un minuto, o coincide con el SKU
        // de uno del maestro: el conteo entra igual contra ese articulo.
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Tornillo","unidad":"UN","creado":false}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(1, resultado.enviados)
        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
    }

    @Test
    fun `cuando el codigo ya existia se reporta con que nombre`() = runTest {
        // Para poder decirle al operario «ese codigo ya era: Tornillo». Sin
        // eso escribio una descripcion que se descarto y nunca se entera.
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Tornillo","unidad":"UN","creado":false}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(listOf("Tornillo"), resultado.yaExistian)
    }

    @Test
    fun `un alta nueva no reporta ningun nombre`() = runTest {
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Pack por 6","unidad":"UN","creado":true}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(emptyList<String>(), resultado.yaExistian)
    }

    @Test
    fun `un alta trabada no frena a los conteos de los demas articulos`() = runTest {
        // El operario conto cincuenta del maestro y uno nuevo: los cincuenta
        // no esperan al que falta.
        guardarAlta()
        guardarPendiente()
        responder("""{"detail":"algo pasajero"}""", codigo = 500)
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        sincronizador().sincronizar()

        assertEquals(1, base.conteoDao().cantidadPendientes())
        assertEquals(1, base.maestroDao().altasPendientes().size)
    }
}
