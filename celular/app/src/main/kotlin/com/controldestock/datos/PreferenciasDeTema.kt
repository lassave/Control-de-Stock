package com.controldestock.datos

import android.content.Context

private const val ARCHIVO = "preferencias"
private const val CLAVE_OSCURO = "tema_oscuro"

/**
 * La elección de tema del operario, si alguna vez tocó el botón.
 *
 * Un booleano suelto no justifica sumar una tabla a `BaseLocal` ni las
 * migraciones de Room que eso implica — ver la deuda conocida sobre lo
 * delicada que es esa carrera. `SharedPreferences` alcanza y sobra.
 */
class PreferenciasDeTema(contexto: Context) {
    private val prefs = contexto.getSharedPreferences(ARCHIVO, Context.MODE_PRIVATE)

    /** Nulo si el operario nunca tocó el botón de tema. */
    fun leer(): Boolean? =
        if (prefs.contains(CLAVE_OSCURO)) prefs.getBoolean(CLAVE_OSCURO, false) else null

    fun guardar(oscuro: Boolean) {
        prefs.edit().putBoolean(CLAVE_OSCURO, oscuro).apply()
    }
}
