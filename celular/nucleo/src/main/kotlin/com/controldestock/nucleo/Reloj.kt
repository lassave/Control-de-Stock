package com.controldestock.nucleo

import java.time.Clock
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

/**
 * La hora del sistema, siempre en UTC.
 *
 * El reloj es inyectable para que un test pueda fijarlo en otra zona y
 * verificar que la salida igual sale en UTC. Sin eso, la «Z» del formato es
 * apenas un carácter literal: cambiar esta clase por la zona local dejaría
 * todos los tests en verde y mandaría hora de Buenos Aires etiquetada como
 * UTC, tres horas de corrimiento en cada conteo, invisible hasta que alguien
 * concilie los números con el cliente.
 */
class RelojDelSistema(private val reloj: Clock = Clock.systemUTC()) : Reloj {

    override fun ahora(): String =
        ZonedDateTime.now(reloj).withZoneSameInstant(ZoneOffset.UTC).format(FORMATO)

    companion object {
        private val FORMATO = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'")

        /** El de siempre, para el código que no necesita fijar la hora. */
        val DEL_SISTEMA = RelojDelSistema()
    }
}
