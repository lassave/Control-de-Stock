package com.controldestock.red

import com.controldestock.nucleo.EventoConteo
import com.controldestock.nucleo.Reloj
import java.io.File
import java.net.HttpURLConnection
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class RelojFijoDeRed(private val instante: String) : Reloj {
    override fun ahora() = instante
}

class ClienteServidorTest {

    private lateinit var servidor: MockWebServer
    private lateinit var cliente: ClienteServidor

    @Before
    fun levantar() {
        servidor = MockWebServer()
        servidor.start()
        cliente = ClienteServidor(servidor.url("/").toString().trimEnd('/'), "token-de-prueba")
    }

    @After
    fun bajar() = servidor.shutdown()

    /** Las respuestas reales capturadas del servidor, no JSON inventado. */
    private fun contrato(nombre: String) = File("../contrato/$nombre.json").readText()

    private fun responder(cuerpo: String, codigo: Int = 200) {
        servidor.enqueue(
            MockResponse().setResponseCode(codigo)
                .setHeader("Content-Type", "application/json")
                .setBody(cuerpo),
        )
    }

    @Test
    fun `vincular manda el token en el encabezado`() = runTest {
        responder(contrato("vinculacion"))

        val respuesta = cliente.vincular()

        val pedido = servidor.takeRequest()
        assertEquals("/api/dispositivo/vincular", pedido.path)
        assertEquals("token-de-prueba", pedido.getHeader("X-Token"))
        assertEquals("Contrato", respuesta.operario.nombre)
    }

    @Test
    fun `descarga el maestro`() = runTest {
        responder(contrato("maestro"))

        val respuesta = cliente.maestro()

        assertEquals("/api/dispositivo/maestro", servidor.takeRequest().path)
        assertEquals(2, respuesta.articulos.size)
    }

    @Test
    fun `manda los conteos con los nombres que espera el servidor`() = runTest {
        responder(contrato("conteos-respuesta"))
        val evento = EventoConteo.nuevo(
            "7790001001234", 48000, RelojFijoDeRed("2026-08-11T10:00:00Z"),
            ubicacionReal = "P-9",
        )

        cliente.enviarConteos(listOf(evento))

        val cuerpo = servidor.takeRequest().body.readUtf8()
        assertTrue(cuerpo.contains("\"timestamp_dispositivo\""))
        assertTrue(cuerpo.contains("\"ubicacion_real\""))
        assertTrue(cuerpo.contains("\"conteos\""))
    }

    @Test
    fun `la respuesta de conteos trae los rechazos`() = runTest {
        responder(contrato("conteos-respuesta"))

        val respuesta = cliente.enviarConteos(
            listOf(EventoConteo.nuevo("A", 1000, RelojFijoDeRed("2026-08-11T10:00:00Z"))),
        )

        assertEquals(1, respuesta.registrados)
        assertEquals(1, respuesta.rechazados.size)
    }

    @Test
    fun `el alta rapida dice si creo el articulo`() = runTest {
        responder(contrato("alta-rapida"))

        val respuesta = cliente.altaRapida("7790009999999", "Sin etiqueta", "UN", "P-9")

        assertEquals("/api/dispositivo/articulos", servidor.takeRequest().path)
        assertTrue(respuesta.creado)
    }

    @Test
    fun `pide las ubicaciones asignadas`() = runTest {
        responder(contrato("mis-ubicaciones"))

        val respuesta = cliente.misUbicaciones()

        assertEquals("/api/dispositivo/mis-ubicaciones", servidor.takeRequest().path)
        assertTrue(respuesta.ubicaciones.isNotEmpty())
    }

    @Test
    fun `sin conteo abierto avisa y no rompe`() = runTest {
        // Nadie pudo contestar el reparto: la app no toca lo que ya tenía
        // guardado, así que alcanza con que esto llegue como un error
        // manejable y no como una excepción cruda.
        responder(
            """{"detail":"El conteo no está abierto en este momento."}""",
            HttpURLConnection.HTTP_CONFLICT,
        )

        val error = try {
            cliente.misUbicaciones(); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.message!!.isNotEmpty())
    }

    @Test
    fun `un token invalido se explica y no se reintenta`() = runTest {
        // Reintentar con un token revocado no va a funcionar nunca: hay que
        // volver a escanear el QR.
        responder("""{"detail":"Token de operario inválido"}""", HttpURLConnection.HTTP_UNAUTHORIZED)

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.message!!.contains("vinculado"))
        assertEquals(false, error.reintentable)
        // Nadie leyó lo que se mandó: el pedido ni entró. Darlo por rechazado
        // haría que quien lo llamó tire el trabajo que dependía de él, por un
        // problema que el operario arregla revinculando.
        assertFalse(error.contenidoRechazado)
    }

    @Test
    fun `un proyecto cerrado se explica y no se reintenta`() = runTest {
        responder("""{"detail":"No hay ningún proyecto abierto"}""", HttpURLConnection.HTTP_CONFLICT)

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(false, error!!.reintentable)
        assertTrue(error.message!!.isNotEmpty())
        // Lo reabre quien maneja el panel. El celular no tiene por qué tirar
        // nada mientras tanto.
        assertFalse(error.contenidoRechazado)
    }

    @Test
    fun `un error del servidor si es reintentable`() = runTest {
        // Un 500 puede ser transitorio: la app conserva el conteo y reintenta.
        responder("""{"detail":"algo se rompio"}""", HttpURLConnection.HTTP_INTERNAL_ERROR)

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(true, error!!.reintentable)
    }

    @Test
    fun `si el servidor no contesta el error es reintentable`() = runTest {
        // Es el caso normal en un depósito: el celular salió del alcance del
        // wifi. No se pierde nada, se reintenta.
        servidor.shutdown()

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(true, error!!.reintentable)
        assertTrue(error.message!!.contains("conexión") || error.message!!.contains("servidor"))
    }

    @Test
    fun `un 400 muestra el motivo que da el servidor`() = runTest {
        // El servidor explica en castellano por qué rechazó el alta; taparlo
        // con un mensaje genérico deja al operario sin saber qué corregir.
        responder(
            """{"detail":"La unidad «CAJA» no está en el catálogo"}""",
            HttpURLConnection.HTTP_BAD_REQUEST,
        )

        val error = try {
            cliente.altaRapida("999", "Algo", "CAJA", null); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.message!!.contains("CAJA"))
        assertEquals(false, error.reintentable)
        // Acá sí: el servidor leyó el artículo y lo rechazó por lo que es. Es
        // el único caso en que lo que dependía de este pedido se puede dar
        // por perdido en vez de esperar.
        assertTrue(error.contenidoRechazado)
    }

    @Test
    fun `un pedido que llego cortado se reintenta`() = runTest {
        // El 422 del servidor dice que el cuerpo no llegó entero: la conexión
        // se cortó a mitad de envío, que en una WiFi de depósito pasa. Nadie
        // llegó a leer el artículo, así que mandarlo de nuevo funciona. Es la
        // diferencia con el 400, que sí es el servidor rechazando lo que leyó.
        responder("""{"detail":"El pedido llegó incompleto."}""", 422)

        val error = try {
            cliente.altaRapida("999", "Algo", "UN", null); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.reintentable)
        assertFalse(error.contenidoRechazado)
    }

    @Test
    fun `un 400 sin motivo legible no da el contenido por rechazado`() = runTest {
        // Traer el motivo del servidor es también lo que prueba que contestó
        // el servidor. Sin eso puede haber contestado cualquier intermediario,
        // y equivocarse para este lado solo cuesta un reintento: para el otro
        // cuesta los conteos del operario.
        responder("<html>Portal de invitados</html>", HttpURLConnection.HTTP_BAD_REQUEST)

        val error = try {
            cliente.altaRapida("999", "Algo", "UN", null); null
        } catch (e: ErrorDeServidor) { e }

        assertFalse(error!!.contenidoRechazado)
    }

    @Test
    fun `una direccion invalida se explica en vez de cerrar la app`() = runTest {
        // La dirección sale del QR, o sea de afuera: puede ser cualquier cosa.
        val conBasura = ClienteServidor("no es una url", "token")

        val error = try {
            conBasura.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertTrue(error!!.message!!.contains("QR"))
        assertEquals(false, error.reintentable)
    }

    @Test
    fun `una barra final en la direccion no rompe el pedido`() = runTest {
        // El QR puede traerla, y «.../ /api/...» daria 404.
        responder(contrato("maestro"))
        val conBarra = ClienteServidor(servidor.url("/").toString(), "token-de-prueba")

        conBarra.maestro()

        assertEquals("/api/dispositivo/maestro", servidor.takeRequest().path)
    }

    @Test
    fun `una respuesta que no se entiende no se reintenta`() = runTest {
        // Reintentar contra algo que no es el servidor esperado no arregla
        // nada; conviene decirlo y frenar.
        responder("esto no es json")

        val error = try {
            cliente.maestro(); null
        } catch (e: ErrorDeServidor) { e }

        assertEquals(false, error!!.reintentable)
        // El portal cautivo de una WiFi ajena entra por acá: contesta 200 con
        // HTML, así que el pedido «salió bien» y lo que falla es leerlo.
        assertFalse(error.contenidoRechazado)
    }
}
