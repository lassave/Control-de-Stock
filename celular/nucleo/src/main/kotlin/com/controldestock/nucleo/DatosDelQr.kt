package com.controldestock.nucleo

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Lo que el panel mete adentro del QR de vinculación. */
@Serializable
data class DatosDelQr(
    @SerialName("u") val url: String,
    @SerialName("t") val token: String,
)

/**
 * Lee el QR del panel, o devuelve null si es cualquier otra cosa.
 *
 * La cámara está siempre activa, así que va a leer etiquetas de productos,
 * QR de wifi y lo que haya en la pared. Nada de eso puede vincular ni
 * romper la app: solo se acepta lo que tiene las dos cosas que hacen falta.
 */
fun leerQr(texto: String): DatosDelQr? = try {
    jsonDelContrato.decodeFromString<DatosDelQr>(texto)
        .takeIf { it.url.isNotBlank() && it.token.isNotBlank() }
} catch (error: Exception) {
    null
}
