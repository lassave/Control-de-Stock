package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.controldestock.camara.VistaDeCamara

/** En qué anda la subida de lo que todavía no viajó. */
sealed class EstadoDeSubida {
    /** Nada en curso: el indicador dice cuántos faltan. */
    object Quieto : EstadoDeSubida()

    object Subiendo : EstadoDeSubida()

    /** El último intento no pudo. Se toca para reintentar. */
    object NoPudo : EstadoDeSubida()
}

/**
 * Cuántos conteos faltan subir, y el botón para subirlos.
 *
 * Informa y resuelve en el mismo lugar a propósito: es donde el operario ya
 * mira para saber si le falta algo, así que es donde tiene que poder tocar
 * para resolverlo. Antes de esto, la única forma de que subiera lo pendiente
 * era confirmar un conteo: el que terminaba de contar y volvía a la zona con
 * señal tenía que inventarse un escaneo, o esperar sin saber cuánto.
 *
 * Vive aparte de `PantallaEscaneo` para poder probarse: la pantalla monta la
 * cámara y CameraX no arranca sin celular.
 */
@Composable
internal fun IndicadorDePendientes(
    pendientes: Int,
    estado: EstadoDeSubida,
    alSubir: () -> Unit,
) {
    val texto = when {
        estado is EstadoDeSubida.Subiendo -> "Subiendo…"
        estado is EstadoDeSubida.NoPudo -> "No se pudo subir"
        pendientes == 0 -> "Todo al día"
        else -> "$pendientes sin subir"
    }

    val color = when {
        estado is EstadoDeSubida.NoPudo -> MaterialTheme.colorScheme.error
        estado is EstadoDeSubida.Subiendo -> Ambar
        pendientes == 0 -> Verde
        else -> Ambar
    }

    // Tocar mientras ya está subiendo no haría nada, y un botón que no hace
    // nada enseña a desconfiar del botón.
    val tocable = when (estado) {
        is EstadoDeSubida.Subiendo -> false
        is EstadoDeSubida.NoPudo -> true
        is EstadoDeSubida.Quieto -> pendientes > 0
    }

    if (tocable) {
        // Con forma de botón: un texto suelto en el encabezado no parece
        // tocable, y este es el único lugar donde el operario puede pedir
        // que suba lo que falta.
        OutlinedButton(
            onClick = alSubir,
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
        ) {
            Text(texto, style = MaterialTheme.typography.bodySmall, color = color)
        }
    } else {
        Text(texto, style = MaterialTheme.typography.bodySmall, color = color)
    }
}

/**
 * La pantalla principal: la cámara siempre activa.
 *
 * El operario apunta y lee, no aprieta botones. Mientras la ficha está
 * abierta el escaneo se pausa, que es lo que evita la lectura duplicada
 * cuando el celular sigue apuntando al mismo código.
 */
@Composable
fun PantallaEscaneo(
    operario: String,
    pasada: String,
    pendientes: Int,
    fichaAbierta: Boolean,
    avisoDeDesconocido: String?,
    /** Qué hacer con el código desconocido. Nulo si no hay ninguno. */
    alDarDeAlta: (() -> Unit)?,
    alLeer: (String) -> Unit,
    estadoDeSubida: EstadoDeSubida,
    alSubir: () -> Unit,
    /** Si el operario puede abrir el ingreso de código a mano ahora mismo. */
    puedeIngresarAMano: Boolean,
    alIngresarAMano: () -> Unit,
    /** Si el operario puede abrir la búsqueda por texto ahora mismo. */
    puedeBuscar: Boolean,
    alBuscar: () -> Unit,
    /**
     * Vuelve a la lista de lo asignado. Sin valor por defecto a propósito:
     * es la única forma de volver, y que falte tiene que notarse al
     * compilar, no en el depósito.
     */
    alVolver: () -> Unit,
    /**
     * La cámara. Se reemplaza en los tests: CameraX no arranca sin celular,
     * y sin este hueco la pantalla entera queda sin cubrir, incluido el botón
     * que es el único camino al alta.
     */
    camara: @Composable (activo: Boolean, alLeer: (String) -> Unit) -> Unit =
        { activo, leer ->
            VistaDeCamara(activo = activo, alLeer = leer, modifier = Modifier.fillMaxSize())
        },
    ficha: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // La izquierda se achica primero: un nombre de operario largo no
            // puede empujar «A mano» fuera de la pantalla, porque es el único
            // camino al ingreso manual.
            Row(
                modifier = Modifier.weight(1f, fill = false),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(
                    onClick = alVolver,
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                ) {
                    Text("←", style = MaterialTheme.typography.titleLarge)
                }
                Column {
                    Text(
                        pasada,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        operario,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(
                    onClick = alIngresarAMano,
                    enabled = puedeIngresarAMano,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                ) {
                    Text("A mano", style = MaterialTheme.typography.bodySmall)
                }
                OutlinedButton(
                    onClick = alBuscar,
                    enabled = puedeBuscar,
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                ) {
                    Text("Buscar", style = MaterialTheme.typography.bodySmall)
                }
                IndicadorDePendientes(
                    pendientes = pendientes,
                    estado = estadoDeSubida,
                    alSubir = alSubir,
                )
            }
        }

        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            camara(!fichaAbierta, alLeer)

            avisoDeDesconocido?.let {
                FranjaDeDesconocido(
                    aviso = it,
                    alDarDeAlta = alDarDeAlta,
                    modifier = Modifier.align(Alignment.BottomCenter),
                )
            }
        }

        if (fichaAbierta) {
            Surface(tonalElevation = 4.dp, modifier = Modifier.fillMaxWidth()) {
                ficha()
            }
        }
    }
}

/**
 * La franja roja del codigo que no esta en el maestro.
 *
 * Vive aparte de `PantallaEscaneo` para poder probarse: la pantalla monta la
 * camara y CameraX no arranca sin celular, asi que adentro el boton no lo
 * cubriria ningun test. Y es el unico camino de entrada al alta: si el boton
 * desaparece, la ficha queda inalcanzable y el codigo desconocido se pierde.
 */
@Composable
internal fun FranjaDeDesconocido(
    aviso: String,
    /** Que hacer con el codigo desconocido. Nulo si no hay a donde ir. */
    alDarDeAlta: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    Surface(
        color = MaterialTheme.colorScheme.error,
        modifier = modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                aviso,
                color = MaterialTheme.colorScheme.onError,
                modifier = Modifier.weight(1f),
            )
            // Dar de alta es un acto deliberado: la ficha no se abre sola
            // porque un codigo mal leido tambien llega como desconocido.
            alDarDeAlta?.let { darDeAlta ->
                Button(onClick = darDeAlta) { Text("Darlo de alta") }
            }
        }
    }
}
