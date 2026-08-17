package com.controldestock.nucleo

import java.io.File
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject

/**
 * La app se prueba contra las respuestas reales del servidor, capturadas en
 * `celular/contrato/`. Del otro lado, `servidor/tests/test_contrato.py`
 * verifica que el servidor las siga cumpliendo.
 */
class ContratoApiTest {

    // El mismo parser que usa la app, no uno configurado para el test: si
    // `jsonDelContrato` deja de tolerar campos desconocidos, esto se pone rojo
    // en vez de fallar recién en el celular.
    private val json = jsonDelContrato

    private fun leer(nombre: String): String =
        File("../contrato/$nombre.json").readText()

    @Test
    fun `parsea la vinculacion`() {
        val respuesta = json.decodeFromString<RespuestaVinculacion>(leer("vinculacion"))

        assertEquals("Contrato", respuesta.operario.nombre)
        assertTrue(respuesta.pasada.etiqueta.startsWith("Conteo"))
    }

    @Test
    fun `parsea el maestro completo`() {
        val respuesta = json.decodeFromString<RespuestaMaestro>(leer("maestro"))

        assertEquals(2, respuesta.articulos.size)
        assertEquals(2, respuesta.codigos.size)
        assertTrue(respuesta.unidades.isNotEmpty())

        val fideos = respuesta.articulos.first { it.sku == "7790001001234" }
        assertEquals("Fideos guisero 500g", fideos.descripcion)
        assertEquals("UN", fideos.unidad)
        assertEquals("P-1", fideos.ubicacion)
    }

    @Test
    fun `las unidades dicen si admiten decimales`() {
        val respuesta = json.decodeFromString<RespuestaMaestro>(leer("maestro"))

        val unidad = respuesta.unidades.first { it.codigo == "KG" }
        assertEquals(1, unidad.admiteDecimales)
    }

    @Test
    fun `parsea la respuesta de conteos y distingue lo reintentable`() {
        val respuesta = json.decodeFromString<RespuestaConteos>(leer("conteos-respuesta"))

        assertEquals(1, respuesta.registrados)
        assertEquals(1, respuesta.rechazados.size)
        assertFalse(respuesta.rechazados[0].reintentable)
        assertTrue(respuesta.rechazados[0].motivo.isNotEmpty())
    }

    @Test
    fun `parsea el alta rapida y sabe si creo`() {
        val respuesta = json.decodeFromString<RespuestaAlta>(leer("alta-rapida"))

        assertTrue(respuesta.creado)
        assertEquals("7790009999999", respuesta.sku)
    }

    @Test
    fun `lo que la app manda tiene los nombres que el servidor lee`() {
        // La otra mitad del contrato, y la más peligrosa: un typo en un
        // @SerialName compila, pasa todos los demás tests, y hace que el
        // servidor rechace cada conteo del lote. Recién se descubre contando.
        val lote = LoteDeConteos(
            listOf(
                ConteoParaEnviar(
                    uuid = "contrato-1",
                    codigo = "7790001001234",
                    cantidad = 48000,
                    timestampDispositivo = "2026-08-11T10:00:00Z",
                    ubicacionReal = "P-9",
                    observaciones = "Estaba en otro estante",
                ),
                ConteoParaEnviar(
                    uuid = "contrato-2",
                    codigo = "no-existe",
                    cantidad = 1000,
                    timestampDispositivo = "2026-08-11T10:01:00Z",
                ),
            ),
        )

        val queManda = json.parseToJsonElement(json.encodeToString(lote)).jsonObject
        val queEspera = json.parseToJsonElement(leer("conteos-pedido")).jsonObject

        assertEquals(queEspera.keys, queManda.keys)
        assertEquals(
            queEspera["conteos"]!!.jsonArray[0].jsonObject.keys,
            queManda["conteos"]!!.jsonArray[0].jsonObject.keys,
        )
        assertEquals(
            queEspera["conteos"]!!.jsonArray[1].jsonObject.keys,
            queManda["conteos"]!!.jsonArray[1].jsonObject.keys,
        )
    }

    @Test
    fun `la anulacion viaja con el nombre que el servidor lee`() {
        val anulacion = EventoConteo(
            uuid = "u-2", codigo = "A", cantidad = 0,
            timestampDispositivo = "2026-08-11T10:05:00Z", anulaUuid = "u-1",
        ).paraEnviar()

        val texto = json.encodeToString(anulacion)

        assertTrue(texto.contains("\"anula_uuid\":\"u-1\""))
    }

    @Test
    fun `parsea las ubicaciones asignadas`() {
        val respuesta = json.decodeFromString<RespuestaMisUbicaciones>(leer("mis-ubicaciones"))

        assertTrue(respuesta.ubicaciones.isNotEmpty())
        assertTrue(respuesta.pasadaId > 0)
    }

    @Test
    fun `un campo nuevo del servidor no rompe el parseo`() {
        // El servidor puede agregar campos sin coordinar una versión de la
        // app. Ignorarlos es lo que permite actualizar de a un lado por vez.
        val conExtra = leer("alta-rapida").trimEnd().dropLast(1) + ""","campo_nuevo":1}"""

        val respuesta = json.decodeFromString<RespuestaAlta>(conExtra)

        assertTrue(respuesta.creado)
    }
}
