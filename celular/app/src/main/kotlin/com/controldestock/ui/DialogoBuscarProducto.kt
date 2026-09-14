package com.controldestock.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.controldestock.Hallazgo

/**
 * Buscar un producto por SKU o descripción, para cuando la etiqueta está
 * rota y ni la cámara ni «A mano» sirven.
 *
 * Sin resultado propio de alta: si no aparece nada, ofrece «A mano», el
 * mismo camino que ya sabe decir «desconocido» y dar de alta sin
 * duplicar artículos.
 */
@Composable
fun DialogoBuscarProducto(
    resultados: List<Hallazgo.Encontrado>,
    alCambiarTexto: (String) -> Unit,
    alElegir: (Hallazgo.Encontrado) -> Unit,
    alIngresarAMano: () -> Unit,
    alCerrar: () -> Unit,
) {
    var texto by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("Buscar producto") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = texto,
                    onValueChange = { texto = it; alCambiarTexto(it) },
                    label = { Text("SKU o descripción") },
                    modifier = Modifier.fillMaxWidth(),
                )
                if (texto.isNotBlank() && resultados.isEmpty()) {
                    Text("No se encontró ningún producto con ese texto.")
                    TextButton(onClick = alIngresarAMano) { Text("Ingresarlo a mano") }
                }
                resultados.forEach { hallazgo ->
                    TextButton(onClick = { alElegir(hallazgo) }) {
                        Text("${hallazgo.articulo.sku} — ${hallazgo.articulo.descripcion}")
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = alCerrar) { Text("Cerrar") } },
    )
}
