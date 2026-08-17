package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
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
 * ubicaciones asignadas, con el botón «Actualizar» de la franja inferior.
 *
 * Una tarjeta por ubicación asignada, no una sola: a diferencia de un
 * operario con un único sector, acá puede tener varias, y cada una necesita
 * su propio resumen.
 */
@Composable
fun PantallaMiLista(
    ubicaciones: List<UbicacionAsignada>,
    pasada: String,
    actualizando: Boolean,
    avisoDeActualizacion: String?,
    pendientes: Int,
    estadoDeSubida: EstadoDeSubida,
    alActualizar: () -> Unit,
    alSubir: () -> Unit,
    alContar: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text(
                "PRODUCTOS ASIGNADOS",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                pasada,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            avisoDeActualizacion?.let {
                Text(
                    it,
                    style = MaterialTheme.typography.bodySmall,
                    color = Ambar,
                    modifier = Modifier.padding(top = 4.dp),
                )
            }
        }

        if (ubicaciones.isEmpty()) {
            Box(
                modifier = Modifier.fillMaxWidth().weight(1f).padding(16.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "Todavía no te asignaron ninguna ubicación",
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxWidth().weight(1f)
                    .padding(horizontal = 16.dp),
            ) {
                ubicaciones.forEach { ubicacion ->
                    item(key = "tarjeta-${ubicacion.ubicacion}") {
                        TarjetaUbicacion(ubicacion)
                    }
                    items(
                        ubicacion.renglones,
                        key = { "${ubicacion.ubicacion}-${it.sku}" },
                    ) { renglon -> Renglon(renglon) }
                }
            }
        }

        BarraInferior(
            pendientes = pendientes,
            estadoDeSubida = estadoDeSubida,
            actualizando = actualizando,
            alActualizar = alActualizar,
            alSubir = alSubir,
            alContar = alContar,
        )
    }
}

@Composable
private fun TarjetaUbicacion(ubicacion: UbicacionAsignada) {
    val sinContar = ubicacion.total - ubicacion.contados

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                "UBICACIÓN ASIGNADA",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                ubicacion.ubicacion,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.SpaceEvenly,
            ) {
                Estadistica("TOTAL", ubicacion.total)
                Estadistica("CONTADOS", ubicacion.contados, Verde)
                Estadistica("SIN CONTAR", sinContar, Ambar)
            }
        }
    }
}

@Composable
private fun Estadistica(etiqueta: String, valor: Int, color: Color? = null) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            etiqueta,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            "$valor",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            color = color ?: MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
private fun Renglon(renglon: RenglonAsignado) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                renglon.descripcion,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
            )
            Text(
                "SKU: ${renglon.sku} · ${renglon.codigos} · ${renglon.unidad}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Column(horizontalAlignment = Alignment.End, modifier = Modifier.padding(start = 8.dp)) {
            if (renglon.fueContado) {
                Etiqueta("CONTADO", Verde)
                Text(
                    "${Cantidades.aTexto(renglon.contado!!)} ${renglon.unidad}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp),
                )
            } else {
                // Sin cantidad a propósito: un pendiente no tiene nada propio
                // que mostrar todavía, y mostrar cualquier otro número ahí
                // insinuaría el stock del sistema, que el celular tiene
                // prohibido exponer.
                Etiqueta("PENDIENTE", Ambar)
            }
        }
    }
}

@Composable
private fun Etiqueta(texto: String, color: Color) {
    Surface(shape = RoundedCornerShape(50), color = color) {
        Text(
            texto,
            style = MaterialTheme.typography.labelSmall,
            color = Color.White,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
        )
    }
}

@Composable
private fun BarraInferior(
    pendientes: Int,
    estadoDeSubida: EstadoDeSubida,
    actualizando: Boolean,
    alActualizar: () -> Unit,
    alSubir: () -> Unit,
    alContar: () -> Unit,
) {
    Surface(shadowElevation = 8.dp, color = MaterialTheme.colorScheme.surface) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IndicadorDePendientes(
                pendientes = pendientes,
                estado = estadoDeSubida,
                alSubir = alSubir,
            )
            OutlinedButton(
                onClick = alActualizar,
                enabled = !actualizando,
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
            ) {
                Text(if (actualizando) "Actualizando…" else "Actualizar")
            }
            Spacer(modifier = Modifier.width(8.dp))
            // El único camino a la cámara desde acá: siempre habilitado,
            // aunque no haya nada asignado, porque sin reparto el operario
            // puede contar cualquier cosa, como antes de que esta pantalla
            // existiera. Con palabra y no solo un símbolo, para que no haga
            // falta adivinar qué hace.
            Button(
                onClick = alContar,
                shape = RoundedCornerShape(50),
                colors = ButtonDefaults.buttonColors(),
            ) {
                Text("Contar")
            }
        }
    }
}
