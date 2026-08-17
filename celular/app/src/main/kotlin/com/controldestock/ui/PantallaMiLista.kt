package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.controldestock.nucleo.Cantidades
import com.controldestock.nucleo.RenglonAsignado
import com.controldestock.nucleo.UbicacionAsignada

/**
 * La pantalla de inicio: dónde arranca el día, siempre.
 *
 * Todo lo que muestra —el tilde, la cantidad, el avance— sale de la base
 * local del celular, no del servidor: tiene que andar sin señal, que es el
 * caso normal del depósito. Lo único que pide al servidor es la lista de
 * ubicaciones asignadas, con el botón «Actualizar» de acá arriba.
 */
@Composable
fun PantallaMiLista(
    ubicaciones: List<UbicacionAsignada>,
    actualizando: Boolean,
    avisoDeActualizacion: String?,
    pendientes: Int,
    estadoDeSubida: EstadoDeSubida,
    alActualizar: () -> Unit,
    alSubir: () -> Unit,
    alContar: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        // El título en mayúsculas es ancho: compartir renglón con los
        // botones los apretaba hasta dejarlos sin lugar («Actualizar»
        // partido en dos líneas y el indicador de pendientes sin espacio
        // para dibujarse). Cada uno en su propio renglón no tiene ese techo.
        Text("PRODUCTOS ASIGNADOS", style = MaterialTheme.typography.titleLarge)
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedButton(
                onClick = alActualizar,
                enabled = !actualizando,
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
            ) {
                Text(if (actualizando) "Actualizando…" else "Actualizar")
            }
            IndicadorDePendientes(
                pendientes = pendientes,
                estado = estadoDeSubida,
                alSubir = alSubir,
            )
        }

        // Discreto y nunca el texto crudo del servidor: no hay nada que el
        // operario tenga que resolver acá, solo saber que se sigue mostrando
        // lo último que bajó.
        avisoDeActualizacion?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = Ambar,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        if (ubicaciones.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "Todavía no te asignaron ninguna ubicación",
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
        } else {
            LazyColumn(modifier = Modifier.fillMaxWidth().weight(1f)) {
                ubicaciones.forEach { ubicacion ->
                    item(key = "cabecera-${ubicacion.ubicacion}") {
                        Text(
                            "Ubicación: ${ubicacion.avance}",
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(vertical = 12.dp),
                        )
                    }
                    items(
                        ubicacion.renglones,
                        key = { "${ubicacion.ubicacion}-${it.sku}" },
                    ) { renglon -> Renglon(renglon) }
                }
            }
        }

        // Siempre habilitado, aunque no haya nada asignado: sin reparto el
        // operario puede contar cualquier cosa, como antes de que esta
        // pantalla existiera.
        Button(
            onClick = alContar,
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        ) {
            Text("Contar")
        }
    }
}

@Composable
private fun Renglon(renglon: RenglonAsignado) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(renglon.descripcion, style = MaterialTheme.typography.bodyLarge)
            Text(
                "${renglon.sku} · ${renglon.codigos} · ${renglon.unidad}",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (renglon.fueContado) {
            Text(
                "✓ ${Cantidades.aTexto(renglon.contado!!)}",
                color = Verde,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(start = 8.dp),
            )
        }
    }
}
