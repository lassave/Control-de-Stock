package com.controldestock.nucleo

/**
 * El resultado de validar lo que el operario tecleó.
 *
 * `PideConfirmacion` existe porque hay cargas raras que igual pueden ser
 * ciertas: medio tornillo suele ser un error, pero a veces no. Bloquear al
 * operario en esos casos lo deja sin forma de registrar lo que ve.
 */
sealed class ResultadoDeCarga {
    data class Valida(val milesimas: Int) : ResultadoDeCarga()
    data class PideConfirmacion(val milesimas: Int, val motivo: String) : ResultadoDeCarga()
    data class Invalida(val motivo: String) : ResultadoDeCarga()
}

object ReglasDeCarga {

    private const val MILESIMAS = 1000

    fun validar(texto: String, admiteDecimales: Boolean): ResultadoDeCarga {
        val milesimas = try {
            Cantidades.aMilesimas(texto)
        } catch (error: IllegalArgumentException) {
            // `aMilesimas` rechaza con el mismo tipo lo que no es una cantidad
            // y lo que no entra en un entero, pero al operario hay que decirle
            // cuál de las dos cosas pasó: si le pedimos que escriba una
            // cantidad, se pone a corregir un tipeo que no hizo. El desborde
            // es el único caso que viene envuelto sobre un ArithmeticException.
            return if (error.cause is ArithmeticException) {
                ResultadoDeCarga.Invalida("Esa cantidad es demasiado grande")
            } else {
                ResultadoDeCarga.Invalida("Escribí una cantidad, por ejemplo 24 o 3,5")
            }
        }

        if (milesimas < 0) {
            // Restar existe como anulación, no como cantidad negativa.
            return ResultadoDeCarga.Invalida("La cantidad no puede ser negativa")
        }

        val tieneDecimales = milesimas % MILESIMAS != 0
        if (tieneDecimales && !admiteDecimales) {
            return ResultadoDeCarga.PideConfirmacion(
                milesimas,
                "Esta unidad se cuenta entera. ¿Cargamos ${Cantidades.aTexto(milesimas)}?",
            )
        }

        return ResultadoDeCarga.Valida(milesimas)
    }
}
