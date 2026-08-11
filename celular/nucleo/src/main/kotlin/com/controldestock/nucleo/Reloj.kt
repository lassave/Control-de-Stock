package com.controldestock.nucleo

import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * La hora, detrás de una interfaz para poder fijarla en los tests.
 *
 * Es la única fuente del formato de fecha de la app, igual que
 * `servidor/app/reloj.py` lo es del lado del servidor.
 */
interface Reloj {
    fun ahora(): String
}

object RelojDelSistema : Reloj {
    private val FORMATO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'")

    override fun ahora(): String =
        ZonedDateTime.now(ZoneOffset.UTC).format(FORMATO)
}
