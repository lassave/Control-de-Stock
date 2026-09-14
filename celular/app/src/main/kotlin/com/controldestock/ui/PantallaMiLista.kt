package com.controldestock.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
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
 * su propio resumen. Cada una se puede colapsar: con muchas ubicaciones
 * asignadas, desplazarse por todas para llegar a la de abajo cansa.
 */
@Composable
fun PantallaMiLista(
    ubicaciones: List<UbicacionAsignada>,
    pasada: String,
    operario: String,
    actualizando: Boolean,
    avisoDeActualizacion: String?,
    pendientes: Int,
    estadoDeSubida: EstadoDeSubida,
    oscuro: Boolean,
    version: String,
    alActualizar: () -> Unit,
    alSubir: () -> Unit,
    alContar: () -> Unit,
    alCambiarTema: () -> Unit,
    alTocarProducto: (Int) -> Unit,
    alIdentificarse: () -> Unit,
) {
    // Por defecto, todas expandidas: una ubicación ausente acá vale «true»,
    // no «false» — si no, cada una nueva que baje el reparto arrancaría
    // colapsada y el operario tendría que ir abriéndolas una por una.
    val expandidas = remember { mutableStateMapOf<String, Boolean>() }

    Column(modifier = Modifier.fillMaxSize()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        "INVENTARIO",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
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
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            operario,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        TextButton(onClick = alIdentificarse) {
                            Text("Cambiar", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                BotonDeTema(oscuro = oscuro, alTocar = alCambiarTema)
            }
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
                    .padding(horizontal = 16.dp)
                    .testTag("lista-de-productos"),
            ) {
                item(key = "encabezado-listado") { EncabezadoDeListado() }

                ubicaciones.forEach { ubicacion ->
                    val expandida = expandidas[ubicacion.ubicacion] ?: true

                    item(key = "tarjeta-${ubicacion.ubicacion}") {
                        TarjetaUbicacion(
                            ubicacion = ubicacion,
                            expandida = expandida,
                            alTocarFlecha = {
                                expandidas[ubicacion.ubicacion] = !expandida
                            },
                        )
                    }

                    if (expandida) {
                        item(key = "metricas-${ubicacion.ubicacion}") {
                            FilaDeMetricas(ubicacion)
                        }
                        items(
                            ubicacion.renglones,
                            key = { "${ubicacion.ubicacion}-${it.sku}" },
                        ) { renglon -> TarjetaProducto(renglon, alTocar = { alTocarProducto(renglon.articuloId) }) }
                    }
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

        // Para diagnosticar «se cerró al abrir» sin depender de conectar el
        // celular por USB: ver la deuda conocida del cierre por versión vieja.
        Text(
            version,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        )
    }
}

@Composable
private fun BotonDeTema(oscuro: Boolean, alTocar: () -> Unit) {
    TextButton(onClick = alTocar) {
        Text(if (oscuro) "🌙" else "☀️", style = MaterialTheme.typography.titleLarge)
    }
}

@Composable
private fun EncabezadoDeListado() {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "LISTADO DE PRODUCTOS",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            "ID | SKU",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun TarjetaUbicacion(
    ubicacion: UbicacionAsignada,
    expandida: Boolean,
    alTocarFlecha: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Con peso: sin esto, una ubicación con nombre largo empuja la
            // flecha fuera de la tarjeta en vez de ajustar el propio ancho.
            // Verificado en un celular real.
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "UBICACIÓN ASIGNADA:",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    ubicacion.ubicacion,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
            }
            TextButton(onClick = alTocarFlecha) {
                Text(if (expandida) "▾" else "▸", style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Composable
private fun FilaDeMetricas(ubicacion: UbicacionAsignada) {
    val sinContar = ubicacion.total - ubicacion.contados

    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        TarjetaDeMetrica("TOTAL", ubicacion.total, modifier = Modifier.weight(1f))
        TarjetaDeMetrica(
            "CONTADOS", ubicacion.contados, Verde, modifier = Modifier.weight(1f),
        )
        TarjetaDeMetrica(
            "SIN CONTAR", sinContar, Ambar, modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun TarjetaDeMetrica(
    etiqueta: String,
    valor: Int,
    color: Color? = null,
    modifier: Modifier = Modifier,
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = modifier,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                color?.let {
                    Box(modifier = Modifier.size(8.dp).background(it, CircleShape))
                }
                Text(
                    etiqueta,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                "$valor",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = color ?: MaterialTheme.colorScheme.onSurface,
            )
        }
    }
}

@Composable
private fun TarjetaProducto(renglon: RenglonAsignado, alTocar: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp).clickable(onClick = alTocar),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    "ID: ${"%03d".format(renglon.idOrden)} | SKU: ${renglon.sku}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                Column(horizontalAlignment = Alignment.End) {
                    if (renglon.fueContado) Etiqueta("CONTADO", Verde) else Etiqueta("PENDIENTE", Ambar)
                    if (renglon.agregado) Etiqueta("AGREGADO", Violeta)
                }
            }
            Text(
                renglon.descripcion,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(top = 4.dp),
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    renglon.codigos,
                    style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                CantidadDelRenglon(renglon)
            }
        }
    }
}

@Composable
private fun CantidadDelRenglon(renglon: RenglonAsignado) {
    // Un pendiente muestra el guion y la unidad, nunca un número: ni el que
    // cargó el operario —no cargó nada— ni ningún otro, porque insinuaría el
    // stock del sistema, que el celular tiene prohibido exponer.
    val texto = if (renglon.fueContado) {
        "${Cantidades.aTexto(renglon.contado!!)} ${renglon.unidad}"
    } else {
        "- ${renglon.unidad}"
    }
    Surface(shape = RoundedCornerShape(50), color = MaterialTheme.colorScheme.surface) {
        Text(
            texto,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
        )
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
            TextButton(
                onClick = alActualizar,
                enabled = !actualizando,
                contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
            ) {
                Text(if (actualizando) "ACTUALIZANDO…" else "ACTUALIZAR")
            }
            // El único camino a la cámara desde acá: siempre habilitado,
            // aunque no haya nada asignado, porque sin reparto el operario
            // puede contar cualquier cosa, como antes de que esta pantalla
            // existiera.
            FilledIconButton(onClick = alContar) {
                Text("+", style = MaterialTheme.typography.headlineSmall)
            }
        }
    }
}
