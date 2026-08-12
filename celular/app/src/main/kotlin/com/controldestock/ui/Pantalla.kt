package com.controldestock.ui

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
