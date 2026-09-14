package com.controldestock

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.red.ClienteServidor
import java.io.File
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class VinculadorTest {

    private lateinit var base: BaseLocal
    private lateinit var servidor: MockWebServer

    @Before
    fun preparar() {
        base = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            BaseLocal::class.java,
        ).build()
        servidor = MockWebServer()
        servidor.start()
    }

    @After
    fun terminar() {
        base.close()
        servidor.shutdown()
    }

    private fun contrato(nombre: String) = File("../contrato/$nombre.json").readText()

    private fun responder(cuerpo: String, codigo: Int = 200) {
        servidor.enqueue(
            MockResponse().setResponseCode(codigo)
                .setHeader("Content-Type", "application/json").setBody(cuerpo),
        )
    }

    private fun vinculador() = Vinculador(base) { url, token -> ClienteServidor(url, token) }

    private fun datos() = DatosDelQr(servidor.url("/").toString().trimEnd('/'), "token")

    @Test
    fun `vincular guarda el proyecto y descarga el maestro`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        val resultado = vinculador().vincular(datos())

        assertTrue(resultado is ResultadoDeVinculacion.Vinculado)
        assertEquals("Contrato", (resultado as ResultadoDeVinculacion.Vinculado).operario)
        assertNotNull(base.vinculacionDao().actual())
        assertEquals(2, base.maestroDao().articulos().size)
    }

    @Test
    fun `el maestro descargado se puede buscar por codigo`() = runTest {
        // Es lo único que importa del maestro para contar: que el escaneo
        // encuentre el artículo, sin señal.
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertNotNull(base.maestroDao().porCodigo("7790001001234"))
    }

    @Test
    fun `el maestro descargado guarda el texto de busqueda`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertTrue(base.maestroDao().buscar("fideos").isNotEmpty())
    }

    @Test
    fun `las unidades quedan guardadas para saber si admiten decimales`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertEquals(1, base.maestroDao().unidad("KG")?.admiteDecimales)
    }

    @Test
    fun `si el servidor no contesta no queda vinculado a medias`() = runTest {
        // Quedar vinculado sin maestro es peor que no vincular: la app abre
        // la cámara y rechaza todo lo que se escanee.
        servidor.shutdown()

        val resultado = vinculador().vincular(datos())

        assertTrue(resultado is ResultadoDeVinculacion.Fallo)
        assertNull(base.vinculacionDao().actual())
    }

    @Test
    fun `si falla la descarga del maestro tampoco queda vinculado`() = runTest {
        responder(contrato("vinculacion"))
        responder("""{"detail":"algo"}""", 500)

        val resultado = vinculador().vincular(datos())

        assertTrue(resultado is ResultadoDeVinculacion.Fallo)
        assertNull(base.vinculacionDao().actual())
    }

    @Test
    fun `un token invalido lo explica en castellano`() = runTest {
        responder("""{"detail":"Token de operario inválido"}""", 401)

        val resultado = vinculador().vincular(datos())

        val mensaje = (resultado as ResultadoDeVinculacion.Fallo).mensaje
        assertTrue(mensaje.contains("QR") || mensaje.contains("vinculado"))
    }

    @Test
    fun `el maestro queda atado al proyecto y a la pasada que dijo el servidor`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        val articulo = base.maestroDao().articulos().first()
        val vinculacion = base.vinculacionDao().actual()!!
        assertEquals(vinculacion.proyectoId, articulo.proyectoId)
        assertEquals(vinculacion.pasadaNumero, articulo.pasadaNumero)
    }

    @Test
    fun `el maestro descargado guarda el origen de cada articulo`() = runTest {
        responder(contrato("vinculacion"))
        responder(contrato("maestro"))

        vinculador().vincular(datos())

        assertEquals("importado", base.maestroDao().articulos().first().origen)
    }

    @Test
    fun `identificarse cambia de operario sin tocar el maestro`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = servidor.url("/").toString().trimEnd('/'), token = "token-viejo",
                operarioId = 1, operarioNombre = "Juan",
                proyectoId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )
        responder(contrato("identificacion"))

        val resultado = vinculador().identificar("Ana", null)

        assertTrue(resultado is ResultadoDeVinculacion.Vinculado)
        val actual = base.vinculacionDao().actual()!!
        assertEquals("Contrato", actual.operarioNombre)
        assertEquals("token-de-contrato-para-identificarse", actual.token)
    }

    @Test
    fun `identificarse sin estar vinculado antes falla`() = runTest {
        val resultado = vinculador().identificar("Ana", null)

        assertTrue(resultado is ResultadoDeVinculacion.Fallo)
    }

    @Test
    fun `identificarse manda el pin al servidor`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = servidor.url("/").toString().trimEnd('/'), token = "token-viejo",
                operarioId = 1, operarioNombre = "Juan",
                proyectoId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
            ),
        )
        responder("""{"detail":"El PIN no coincide"}""", 400)

        val resultado = vinculador().identificar("Ana", "0000")

        val mensaje = (resultado as ResultadoDeVinculacion.Fallo).mensaje
        assertTrue(mensaje.contains("PIN"))
    }
}
