package com.controldestock.nucleo

import java.io.File
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * La app se prueba contra las respuestas reales del servidor, capturadas en
 * `celular/contrato/`. Del otro lado, `servidor/tests/test_contrato.py`
 * verifica que el servidor las siga cumpliendo.
 */
class ContratoApiTest {

    private val json = Json { ignoreUnknownKeys = true }

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
    fun `un campo nuevo del servidor no rompe el parseo`() {
        // El servidor puede agregar campos sin coordinar una versión de la
        // app. Ignorarlos es lo que permite actualizar de a un lado por vez.
        val conExtra = leer("alta-rapida").trimEnd().dropLast(1) + ""","campo_nuevo":1}"""

        val respuesta = json.decodeFromString<RespuestaAlta>(conExtra)

        assertTrue(respuesta.creado)
    }
}
