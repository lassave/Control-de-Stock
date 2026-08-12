package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class DatosDelQrTest {

    @Test
    fun `lee el QR que genera el panel`() {
        val texto = """{"u":"http://172.16.11.12:8000","t":"abc123"}"""

        val datos = leerQr(texto)

        assertEquals("http://172.16.11.12:8000", datos?.url)
        assertEquals("abc123", datos?.token)
    }

    @Test
    fun `un QR de otra cosa no vincula nada`() {
        // El operario puede apuntar sin querer a la etiqueta de un producto,
        // o a un QR de wifi. Tiene que decirlo, no romperse.
        assertNull(leerQr("https://www.google.com"))
        assertNull(leerQr("7790001001234"))
        assertNull(leerQr(""))
    }

    @Test
    fun `un JSON sin los campos que hacen falta no vincula`() {
        assertNull(leerQr("""{"u":"http://a"}"""))
        assertNull(leerQr("""{"t":"abc"}"""))
        assertNull(leerQr("""{"u":"","t":"abc"}"""))
        assertNull(leerQr("""{"u":"http://a","t":""}"""))
    }

    @Test
    fun `un JSON con campos de mas igual se lee`() {
        // El panel puede agregar un campo sin coordinar una versión de la app.
        val texto = """{"u":"http://a:8000","t":"abc","v":2}"""

        assertEquals("abc", leerQr(texto)?.token)
    }

    @Test
    fun `lee el QR real que sirve el servidor`() {
        // El formato exacto que arma servicios/vinculacion.py, con un token
        // de los de verdad: 43 caracteres.
        val texto = """{"u":"http://172.16.242.92:8000",""" +
            """"t":"dsvDgRqPY-gh9gMh90kuyjGinb1GAxqddsoDG4y4AXk"}"""

        val datos = leerQr(texto)

        assertEquals("dsvDgRqPY-gh9gMh90kuyjGinb1GAxqddsoDG4y4AXk", datos?.token)
    }
}
