package com.controldestock.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * El código escrito a mano, para cuando la cámara no puede leer la
 * etiqueta —rota, tapada, mal impresa—.
 *
 * El mismo teclado grande que ya se usa para cargar cantidades: se usa con
 * apuro y a veces con guantes, así que el teclado chico del sistema no
 * sirve acá tampoco.
 *
 * No entrega el código por un camino propio: quien lo use lo pasa por el
 * mismo `alLeer` que ya recibe los códigos de la cámara, para heredar sin
 * duplicar el timbre, el aviso de repetido y el alta rápida.
 */
@Composable
fun DialogoCodigoAMano(alConfirmar: (String) -> Unit, alCancelar: () -> Unit) {
    var texto by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCancelar,
        title = { Text("Código a mano") },
        text = {
            Column(modifier = Modifier.fillMaxWidth()) {
                Text(
                    // No es "0" como en el visor de cantidad: un código
                    // vacío no es un código de valor cero, es que todavía
                    // no se escribió nada.
                    texto.ifEmpty { "…" },
                    fontSize = 32.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                )
                TecladoNumerico(
                    alTocar = { tecla ->
                        texto = when (tecla) {
                            "C" -> ""
                            "," -> texto
                            else -> texto + tecla
                        }
                    },
                    alBorrar = { texto = texto.dropLast(1) },
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { alConfirmar(texto) }, enabled = texto.isNotEmpty()) {
                Text("Confirmar")
            }
        },
        dismissButton = {
            TextButton(onClick = alCancelar) { Text("Cancelar") }
        },
    )
}
