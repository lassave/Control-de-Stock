package com.controldestock.ui

import com.controldestock.Hallazgo
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.datos.textoDeBusqueda
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PantallaTest {

    private val vinculacion = VinculacionEntidad(
        url = "http://172.16.11.12:8000", token = "abc",
        operarioId = 1, operarioNombre = "Juan",
        sesionId = 1, pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
    )

    private val tornillos = ArticuloEntidad(
        id = 1, idOrden = 1, sku = "A-1", descripcion = "Tornillos",
        unidad = "UN", ubicacion = "P-1", pasadaNumero = 1, sesionId = 1,
        busqueda = textoDeBusqueda("Tornillos", "A-1", "P-1"),
    )

    @Test
    fun `sin vincular va a la pantalla de vinculacion`() {
        assertEquals(Pantalla.Vinculando, pantallaSegun(null))
    }

    @Test
    fun `vinculado cae en la lista de lo asignado`() {
        // La lista es la casa de la app: el operario ve qué le toca antes de
        // ir a contar, y de ahí pasa a la cámara con un toque.
        assertEquals(Pantalla.EnLaLista, pantallaSegun(vinculacion))
    }

    @Test
    fun `un codigo desconocido nuevo se anuncia`() {
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = null))
    }

    @Test
    fun `el desconocido que ya esta en la franja no se vuelve a anunciar`() {
        // La cámara avisa una lectura por cuadro: sin esto, una etiqueta
        // quieta frente al celular suena varias veces por segundo hasta que
        // el operario la saca de encima.
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertFalse(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }

    @Test
    fun `otro desconocido distinto si se anuncia`() {
        // Cambió el producto: es información nueva y el operario tiene que
        // enterarse.
        val hallazgo = Hallazgo.Desconocido("7790111")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }

    @Test
    fun `un articulo fuera de la pasada activa nuevo se anuncia`() {
        val hallazgo = Hallazgo.FueraDePasada("7790999", "Tornillos")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = null))
    }

    @Test
    fun `el fuera de pasada que ya esta en la franja no se vuelve a anunciar`() {
        val hallazgo = Hallazgo.FueraDePasada("7790999", "Tornillos")

        assertFalse(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }

    @Test
    fun `una subida que salio bien deja el indicador contando`() {
        assertEquals(
            EstadoDeSubida.Quieto,
            estadoTrasSubir(huboError = false, loPidioElOperario = true),
        )
    }

    @Test
    fun `el error solo se muestra si lo pidio el operario`() {
        assertEquals(
            EstadoDeSubida.NoPudo,
            estadoTrasSubir(huboError = true, loPidioElOperario = true),
        )
    }

    @Test
    fun `una sincronizacion automatica que falla no reprocha nada`() {
        // Contando sin señal, cada conteo dispara una sincronización que va a
        // fallar. Mostrar «No se pudo subir» ahí taparía el dato que el
        // operario necesita —cuántos lleva sin subir— para decirle algo que
        // ya sabe: que no hay WiFi.
        assertEquals(
            EstadoDeSubida.Quieto,
            estadoTrasSubir(huboError = true, loPidioElOperario = false),
        )
    }

    @Test
    fun `un codigo que esta en el maestro se anuncia siempre`() {
        // No necesita la excepción: al abrirse su ficha el escaneo se pausa
        // solo, así que no hay repetición que evitar.
        val hallazgo = Hallazgo.Encontrado(tornillos, admiteDecimales = false, codigo = "7790999")

        assertTrue(hayQueAnunciar(hallazgo, codigoEnLaFranja = "7790999"))
    }

    @Test
    fun `sin nada abierto no hay ficha`() {
        assertFalse(fichaAbierta(hallazgo = null, altaDe = null, ingresandoAMano = false))
    }

    @Test
    fun `un articulo encontrado abre la ficha`() {
        val hallazgo = Hallazgo.Encontrado(tornillos, admiteDecimales = false, codigo = "7790999")

        assertTrue(fichaAbierta(hallazgo, altaDe = null, ingresandoAMano = false))
    }

    @Test
    fun `un desconocido no abre ninguna ficha`() {
        // La franja roja no es una ficha: se dibuja al lado de la cámara,
        // no la tapa. Si esto diera true, la cámara se pausaría con cada
        // código desconocido, y no hay forma de que se reanude sola.
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertFalse(fichaAbierta(hallazgo, altaDe = null, ingresandoAMano = false))
    }

    @Test
    fun `el alta de un codigo cuenta como ficha abierta`() {
        assertTrue(fichaAbierta(hallazgo = null, altaDe = "7790999", ingresandoAMano = false))
    }

    @Test
    fun `ingresar el codigo a mano tambien pausa la camara`() {
        // Sin esto, una lectura de cámara en el medio le pisa el código que
        // el operario está tipeando.
        assertTrue(fichaAbierta(hallazgo = null, altaDe = null, ingresandoAMano = true))
    }

    @Test
    fun `atras cierra el dialogo de codigo a mano primero`() {
        val hallazgo = Hallazgo.Encontrado(tornillos, admiteDecimales = false, codigo = "A-1")

        assertEquals(
            Atras.CierraIngresoAMano,
            atrasCierra(hallazgo, altaDe = "7790999", ingresandoAMano = true),
        )
    }

    @Test
    fun `atras cierra el alta abierta`() {
        assertEquals(
            Atras.CierraAlta,
            atrasCierra(hallazgo = null, altaDe = "7790999", ingresandoAMano = false),
        )
    }

    @Test
    fun `atras cierra la ficha de un articulo`() {
        val hallazgo = Hallazgo.Encontrado(tornillos, admiteDecimales = false, codigo = "A-1")

        assertEquals(
            Atras.CierraFicha,
            atrasCierra(hallazgo, altaDe = null, ingresandoAMano = false),
        )
    }

    @Test
    fun `sin nada abierto atras vuelve a la lista`() {
        assertEquals(
            Atras.VuelveALaLista,
            atrasCierra(hallazgo = null, altaDe = null, ingresandoAMano = false),
        )
    }

    @Test
    fun `un desconocido en pantalla no cuenta como algo abierto`() {
        // La franja roja no tapa la cámara: atrás puede volver a la lista
        // con un desconocido en pantalla.
        val hallazgo = Hallazgo.Desconocido("7790999")

        assertEquals(
            Atras.VuelveALaLista,
            atrasCierra(hallazgo, altaDe = null, ingresandoAMano = false),
        )
    }
}
