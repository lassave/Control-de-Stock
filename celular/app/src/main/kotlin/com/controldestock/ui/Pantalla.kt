package com.controldestock.ui

import com.controldestock.Hallazgo
import com.controldestock.datos.VinculacionEntidad

/**
 * En qué pantalla está la app.
 *
 * Son cuatro. La decisión entre `Cargando`, `Vinculando` y las otras dos
 * sigue siendo una sola pregunta —si el celular está vinculado—, y entre
 * `EnLaLista` y `Escaneando` decide el operario con un botón: por eso sigue
 * alcanzando un `when` y no hace falta una librería con su propio grafo y su
 * propio ciclo de vida.
 */
sealed class Pantalla {
    /** Todavía no se leyó la base local. */
    object Cargando : Pantalla()

    /** Falta escanear el QR del panel. */
    object Vinculando : Pantalla()

    /** La lista de lo asignado: dónde arranca el día, siempre. */
    object EnLaLista : Pantalla()

    /** La cámara, lista para contar. */
    object Escaneando : Pantalla()
}

/**
 * A qué pantalla lleva estar (o no) vinculado.
 *
 * Antes iba directo a `Escaneando`: «el operario abre la app para contar, no
 * para ver un menú». Con el reparto por ubicación esa premisa cambió — ahora
 * hay algo que mirar antes de escanear, así que la app abre siempre en
 * `EnLaLista`, y de ahí el operario pasa a contar con un toque.
 */
fun pantallaSegun(vinculacion: VinculacionEntidad?): Pantalla =
    if (vinculacion == null) Pantalla.Vinculando else Pantalla.EnLaLista

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
        is Hallazgo.FueraDePasada -> hallazgo.codigo != codigoEnLaFranja
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

/**
 * Si hay algo en pantalla que tiene que pausar la cámara.
 *
 * Tres causas compiten por la misma atención: la ficha de un artículo, el
 * alta de uno nuevo, o el código que el operario está escribiendo a mano.
 * Ninguna convive con una lectura de cámara que llegue en el medio. Antes
 * de sumar la tercera esto se armaba en línea en `MainActivity.kt` con dos
 * variables sueltas; agregar una tercera ahí sin una función que la cubra
 * repite el patrón que ya costó tres defectos parecidos (ver
 * `docs/superpowers/deuda-conocida.md`).
 *
 * Un `Hallazgo.Desconocido` no cuenta: la franja roja se dibuja al lado de
 * la cámara, no la tapa.
 */
fun fichaAbierta(
    hallazgo: Hallazgo?,
    altaDe: String?,
    ingresandoAMano: Boolean,
    // Con valor por defecto a propósito: son más de una decena de llamadas
    // existentes, ninguna sabe de búsqueda, y agregar un cuarto booleano acá
    // no cambia ninguna de ellas — «false» es exactamente el comportamiento
    // que ya tenían.
    buscando: Boolean = false,
): Boolean = hallazgo is Hallazgo.Encontrado || altaDe != null || ingresandoAMano || buscando

/** Qué cierra el botón atrás, estando en la pantalla de escaneo. */
sealed class Atras {
    object CierraIngresoAMano : Atras()
    object CierraBusqueda : Atras()
    object CierraAlta : Atras()
    object CierraFicha : Atras()
    object VuelveALaLista : Atras()
}

/**
 * Decide qué hace el botón atrás de Android en la pantalla de escaneo.
 *
 * El orden es al revés de `fichaAbierta`: ahí cualquiera de las causas
 * alcanza para pausar la cámara, acá hay que elegir una sola cosa para
 * cerrar. «A mano» va antes que la búsqueda porque a ese diálogo se puede
 * llegar *desde* la búsqueda (el botón «Ingresarlo a mano»), así que puede
 * haber dos abiertos a la vez y hay que cerrar el de encima primero.
 */
fun atrasCierra(
    hallazgo: Hallazgo?,
    altaDe: String?,
    ingresandoAMano: Boolean,
    buscando: Boolean = false,
): Atras = when {
    ingresandoAMano -> Atras.CierraIngresoAMano
    buscando -> Atras.CierraBusqueda
    altaDe != null -> Atras.CierraAlta
    hallazgo is Hallazgo.Encontrado -> Atras.CierraFicha
    else -> Atras.VuelveALaLista
}

/**
 * Lo que se muestra al operario para identificar qué versión tiene instalada.
 *
 * Con el mismo `versionName` que ya escribe `app.apk.txt` al publicar y el
 * `versionCode` que Android rechaza si es menor al ya instalado: son los dos
 * datos que hacen falta para diagnosticar «se cerró al abrir» sin depender
 * de conectar el celular por USB.
 */
fun textoDeVersion(versionName: String, versionCode: Int): String =
    "v$versionName (build $versionCode)"
