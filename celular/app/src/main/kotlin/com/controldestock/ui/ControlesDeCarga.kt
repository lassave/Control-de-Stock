package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * El teclado de la carga: propio y con teclas grandes.
 *
 * Se usa con apuro y a veces con guantes, así que no sirve el teclado del
 * sistema. Lo comparten la ficha del artículo y la del alta rápida: dos
 * teclados distintos para lo mismo se desincronizan en cuanto uno cambia.
 */
@Composable
fun TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit) {
    val filas = listOf(
        listOf("1", "2", "3"),
        listOf("4", "5", "6"),
        listOf("7", "8", "9"),
        listOf("C", "0", ","),
    )

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        filas.forEach { fila ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                fila.forEach { tecla ->
                    Button(
                        onClick = { alTocar(tecla) },
                        modifier = Modifier.weight(1f).height(64.dp),
                    ) {
                        Text(tecla, fontSize = 22.sp)
                    }
                }
                if (fila == filas.last()) {
                    Button(
                        onClick = alBorrar,
                        modifier = Modifier.weight(1f).height(64.dp),
                    ) {
                        Text("←", fontSize = 22.sp)
                    }
                }
            }
        }
    }
}

/** Dónde estaba de verdad: la lista del maestro, o una escrita a mano. */
@Composable
fun ElegirUbicacion(
    ubicaciones: List<String>,
    alElegir: (String) -> Unit,
    alCerrar: () -> Unit,
) {
    var filtro by remember { mutableStateOf("") }
    var otra by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("¿Dónde estaba?") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = filtro,
                    onValueChange = { filtro = it },
                    label = { Text("Buscar ubicación") },
                )
                ubicaciones.filter { it.contains(filtro, ignoreCase = true) }
                    .take(20)
                    .forEach { u ->
                        TextButton(onClick = { alElegir(u) }) { Text(u) }
                    }
                OutlinedTextField(
                    value = otra,
                    onValueChange = { otra = it },
                    label = { Text("Otra…") },
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (otra.isNotBlank()) alElegir(otra.trim()) else alCerrar() },
            ) { Text("Listo") }
        },
        dismissButton = { TextButton(onClick = alCerrar) { Text("Cancelar") } },
    )
}
