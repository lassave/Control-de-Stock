package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.controldestock.camara.VistaDeCamara

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
    alLeer: (String) -> Unit,
    ficha: @Composable () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(pasada, style = MaterialTheme.typography.titleMedium)
            Text(operario, style = MaterialTheme.typography.bodyMedium)
            Text(
                if (pendientes == 0) "Todo al día" else "$pendientes sin subir",
                style = MaterialTheme.typography.bodySmall,
                color = if (pendientes == 0) Verde else Ambar,
            )
        }

        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            VistaDeCamara(
                activo = !fichaAbierta,
                alLeer = alLeer,
                modifier = Modifier.fillMaxSize(),
            )

            avisoDeDesconocido?.let {
                Surface(
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
                ) {
                    Text(
                        it,
                        color = MaterialTheme.colorScheme.onError,
                        modifier = Modifier.padding(12.dp),
                    )
                }
            }
        }

        if (fichaAbierta) {
            Surface(tonalElevation = 4.dp, modifier = Modifier.fillMaxWidth()) {
                ficha()
            }
        }
    }
}
