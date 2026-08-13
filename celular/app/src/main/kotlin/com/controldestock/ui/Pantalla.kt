package com.controldestock.ui

import com.controldestock.Hallazgo
import com.controldestock.datos.VinculacionEntidad

/**
 * En qué pantalla está la app.
 *
 * Son tres y la decisión entre ellas es una sola pregunta —si el celular
 * está vinculado—, así que la navegación es un `when` y no una librería con
 * su propio grafo y su propio ciclo de vida.
 */
sealed class Pantalla {
    /** Todavía no se leyó la base local. */
    object Cargando : Pantalla()

    /** Falta escanear el QR del panel. */
    object Vinculando : Pantalla()

    /** La cámara, lista para contar. */
    object Escaneando : Pantalla()
}

/**
 * El operario abre la app para contar, no para ver un menú: si ya está
 * vinculado, la cámara arranca sin que tenga que tocar nada.
 */
fun pantallaSegun(vinculacion: VinculacionEntidad?): Pantalla =
    if (vinculacion == null) Pantalla.Vinculando else Pantalla.Escaneando

/**
 * Si esta lectura hay que anunciarla con sonido y vibración.
 *
 * La cámara avisa una lectura por cuadro. Con un código que está en el
 * maestro eso no molesta: al abrirse su ficha el escaneo se pausa solo. Con
 * uno desconocido no se pausa nada, y la misma etiqueta quieta frente al
 * celular vuelve a sonar en cada cuadro. Un timbre repetido veinte veces
 * deja de avisar y pasa a estorbar, que es la forma más rápida de enseñarle
 * al operario a ignorarlo.
 *
 * No se pierde información al callarlo: la franja sigue mostrando el código.
 *
 * @param codigoEnLaFranja el desconocido que ya está en pantalla, si hay uno.
 */
fun hayQueAnunciar(hallazgo: Hallazgo, codigoEnLaFranja: String?): Boolean =
    when (hallazgo) {
        is Hallazgo.Encontrado -> true
        is Hallazgo.Desconocido -> hallazgo.codigo != codigoEnLaFranja
    }

/**
 * Cómo queda el indicador después de intentar subir.
 *
 * El error se muestra solo si la subida la pidió el operario. Cada conteo
 * dispara una sincronización, así que contando sin señal —el caso normal del
 * depósito— todas fallan: mostrar «No se pudo subir» ahí taparía el dato que
 * él necesita, cuántos lleva sin subir, para decirle algo que ya sabe.
 *
 * Cuando lo pidió, en cambio, el silencio sería peor: tocó un botón y tiene
 * que saber en qué quedó.
 */
fun estadoTrasSubir(huboError: Boolean, loPidioElOperario: Boolean): EstadoDeSubida =
    if (huboError && loPidioElOperario) EstadoDeSubida.NoPudo else EstadoDeSubida.Quieto
