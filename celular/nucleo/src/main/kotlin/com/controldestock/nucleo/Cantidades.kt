package com.controldestock.nucleo

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * Conversión entre texto y enteros escalados.
 *
 * Las cantidades viajan y se guardan en milésimas. Sumar punto flotante
 * acumula error, y un inventario suma miles de veces.
 *
 * Es la contraparte exacta de `servidor/app/cantidades.py`: los dos lados
 * comparten la tabla de casos de prueba.
 */
object Cantidades {

    private const val MILESIMAS = 1000
    private val SOLO_DIGITOS = Regex("^-?\\d+$")

    fun aMilesimas(texto: String): Int {
        val limpio = texto.trim()
        require(limpio.isNotEmpty()) { "La cantidad está vacía" }

        val (entero, decimal) = partir(limpio)

        val valor = try {
            BigDecimal("$entero.${decimal.ifEmpty { "0" }}")
        } catch (error: NumberFormatException) {
            throw IllegalArgumentException("Cantidad inválida: «$texto»", error)
        }

        // Redondeo y no truncamiento: truncar sesgaría todas las cantidades a
        // la baja de forma sistemática.
        return valor.multiply(BigDecimal(MILESIMAS))
            .setScale(0, RoundingMode.HALF_UP)
            .toInt()
    }

    fun aTexto(milesimas: Int): String {
        val signo = if (milesimas < 0) "-" else ""
        val absoluto = Math.abs(milesimas)
        val entero = absoluto / MILESIMAS
        val resto = absoluto % MILESIMAS

        if (resto == 0) return "$signo$entero"

        val decimales = resto.toString().padStart(3, '0').trimEnd('0')
        return "$signo$entero,$decimales"
    }

    /**
     * Separa parte entera y decimal resolviendo el formato del origen.
     *
     * Los ERP exportan indistintamente 1.234,56 y 1,234.56. Cuando conviven
     * los dos caracteres, el último es el decimal y el otro agrupa miles.
     * Cuando hay uno solo repetido (1.234.567) solo puede agrupar miles.
     */
    private fun partir(limpio: String): Pair<String, String> {
        val coma = limpio.lastIndexOf(',')
        val punto = limpio.lastIndexOf('.')

        if (coma == -1 && punto == -1) {
            require(SOLO_DIGITOS.matches(limpio)) { "Cantidad inválida: «$limpio»" }
            return limpio to ""
        }

        val separadorDecimal: Char
        if (coma >= 0 && punto >= 0) {
            separadorDecimal = if (coma > punto) ',' else '.'
        } else {
            val unico = if (coma >= 0) ',' else '.'
            if (limpio.count { it == unico } > 1) {
                require(agrupacionValida(limpio, unico)) { "Cantidad inválida: «$limpio»" }
                return limpio.replace(unico.toString(), "") to ""
            }
            separadorDecimal = unico
        }

        val separadorMiles = if (separadorDecimal == ',') '.' else ','
        val corte = limpio.lastIndexOf(separadorDecimal)
        var entero = limpio.substring(0, corte)
        val decimal = limpio.substring(corte + 1)

        // Un separador suelto no es cero: es una celda rota. Devolver cero
        // sería lo peor posible, porque un cero pasa por un conteo real.
        require(decimal.isNotEmpty() && decimal.all { it.isDigit() }) {
            "Cantidad inválida: «$limpio»"
        }

        if (entero.isEmpty() || entero == "-") entero += "0"
        require(agrupacionValida(entero, separadorMiles)) { "Cantidad inválida: «$limpio»" }

        return entero.replace(separadorMiles.toString(), "") to decimal
    }

    /**
     * Verifica que los grupos de miles tengan tres dígitos.
     *
     * Sin esto «1,2,3» se leería como 123 en vez de rechazarse, y un número
     * inventado es peor que un error: pasa por una cantidad real.
     */
    private fun agrupacionValida(entero: String, separadorMiles: Char): Boolean {
        if (!entero.contains(separadorMiles)) return SOLO_DIGITOS.matches(entero)
        val escapado = Regex.escape(separadorMiles.toString())
        return Regex("^-?\\d{1,3}($escapado\\d{3})+$").matches(entero)
    }
}
