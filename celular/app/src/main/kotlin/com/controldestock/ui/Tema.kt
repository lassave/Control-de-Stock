package com.controldestock.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Los mismos que panel/estilos.css: un color significa lo mismo en las dos
// interfaces, que es lo que pide el diseño general.
val Acento = Color(0xFF1F5FA9)
val Verde = Color(0xFF1B7A3D)
val Rojo = Color(0xFFB3261E)
val Ambar = Color(0xFF9A5B12)

private val Claro = lightColorScheme(
    primary = Acento,
    error = Rojo,
)

private val Oscuro = darkColorScheme(
    primary = Color(0xFF7FB0E6),
    error = Color(0xFFE08B84),
)

/**
 * Qué tema mostrar: el que el operario eligió a mano, o si nunca tocó nada,
 * el que ya trae el celular.
 */
fun esOscuro(preferencia: Boolean?, sistemaOscuro: Boolean): Boolean =
    preferencia ?: sistemaOscuro

@Composable
fun Tema(oscuro: Boolean, contenido: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (oscuro) Oscuro else Claro,
        content = contenido,
    )
}
