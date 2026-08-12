package com.controldestock.ui

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

/**
 * Los tres avisos, cada uno por sonido y por vibración a la vez.
 *
 * En un depósito ruidoso no se escucha; con el celular en movimiento no se
 * ve. Al menos uno de los dos siempre llega, y el color de la pantalla es
 * el tercero.
 */
class AvisoSonoro(contexto: Context) {

    private val tonos = ToneGenerator(AudioManager.STREAM_MUSIC, 100)

    private val vibrador: Vibrator? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            (contexto.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)
                ?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            contexto.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }

    /** Leído: corto y agudo. */
    fun leido() {
        tonos.startTone(ToneGenerator.TONE_PROP_BEEP, 120)
        vibrar(60)
    }

    /** Código que no está en el maestro: distinto, para no confundirlo. */
    fun desconocido() {
        tonos.startTone(ToneGenerator.TONE_PROP_BEEP2, 300)
        vibrar(200)
    }

    /** Error: el más largo. */
    fun error() {
        tonos.startTone(ToneGenerator.TONE_SUP_ERROR, 400)
        vibrar(400)
    }

    /** Confirmación de carga: apenas un golpecito. */
    fun cargado() {
        tonos.startTone(ToneGenerator.TONE_PROP_ACK, 100)
        vibrar(40)
    }

    private fun vibrar(milisegundos: Long) {
        val v = vibrador ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            v.vibrate(VibrationEffect.createOneShot(milisegundos, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            v.vibrate(milisegundos)
        }
    }

    fun cerrar() = tonos.release()
}
