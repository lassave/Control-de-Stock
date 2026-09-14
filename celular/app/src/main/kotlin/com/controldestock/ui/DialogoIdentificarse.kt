package com.controldestock.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.controldestock.nucleo.OperarioParaIdentificar

/**
 * Identificarse en un celular ya vinculado, sin volver a escanear el QR.
 *
 * Pide el PIN solo si ese operario lo tiene cargado desde el panel: la
 * mayoría entra con solo elegir su nombre, a propósito.
 */
@Composable
fun DialogoIdentificarse(
    operarios: List<OperarioParaIdentificar>,
    cargando: Boolean,
    error: String?,
    alElegir: (nombre: String, pin: String?) -> Unit,
    alCerrar: () -> Unit,
) {
    var elegido by remember { mutableStateOf<OperarioParaIdentificar?>(null) }
    var pin by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text(elegido?.let { "PIN de ${it.nombre}" } ?: "¿Quién sos?") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                when {
                    cargando -> Text("Cargando…")
                    elegido == null -> operarios.forEach { o ->
                        TextButton(onClick = {
                            if (o.tienePin) elegido = o else alElegir(o.nombre, null)
                        }) { Text(o.nombre) }
                    }
                    else -> OutlinedTextField(
                        value = pin,
                        onValueChange = { pin = it },
                        label = { Text("PIN") },
                    )
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            elegido?.let { o ->
                TextButton(onClick = { alElegir(o.nombre, pin) }) { Text("Entrar") }
            }
        },
        dismissButton = { TextButton(onClick = alCerrar) { Text("Cancelar") } },
    )
}
