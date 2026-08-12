package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.controldestock.datos.ArticuloEntidad
import com.controldestock.nucleo.ReglasDeCarga
import com.controldestock.nucleo.ResultadoDeCarga

/**
 * La ficha que sube al leer un código.
 *
 * La descripción domina la pantalla: el operario tiene que confirmar de un
 * vistazo que tiene el producto correcto en la mano. El teclado es propio y
 * con teclas grandes, porque se usa con apuro y a veces con guantes.
 */
@Composable
fun FichaDelArticulo(
    articulo: ArticuloEntidad,
    admiteDecimales: Boolean,
    ubicaciones: List<String>,
    alCancelar: () -> Unit,
    // Último para que quede como lambda final en la llamada.
    alConfirmar: (Int, String?, String?) -> Unit,
) {
    var texto by remember { mutableStateOf("") }
    var ubicacionReal by remember { mutableStateOf<String?>(null) }
    var observaciones by remember { mutableStateOf("") }
    var aviso by remember { mutableStateOf<String?>(null) }
    // La pregunta por el decimal viaja entera adentro del cartel y no por
    // `aviso`: si no, el mismo texto se ve dos veces a la vez —en el cartel
    // y en rojo abajo del teclado— y queda colgado al elegir corregir, como
    // si además del cartel hubiera algo mal.
    var confirmarDecimal by remember {
        mutableStateOf<ResultadoDeCarga.PideConfirmacion?>(null)
    }
    var eligiendoUbicacion by remember { mutableStateOf(false) }

    fun confirmar() {
        when (val r = ReglasDeCarga.validar(texto, admiteDecimales)) {
            is ResultadoDeCarga.Valida ->
                alConfirmar(r.milesimas, ubicacionReal, observaciones.ifBlank { null })
            is ResultadoDeCarga.PideConfirmacion -> confirmarDecimal = r
            is ResultadoDeCarga.Invalida -> aviso = r.motivo
        }
    }

    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            articulo.descripcion,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "SKU ${articulo.sku} · #${articulo.idOrden}",
            style = MaterialTheme.typography.bodyMedium,
        )
        listOfNotNull(articulo.grupo, articulo.material).takeIf { it.isNotEmpty() }?.let {
            Text(it.joinToString(" · "), style = MaterialTheme.typography.bodySmall)
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Ubicación: ${ubicacionReal ?: articulo.ubicacion ?: "sin ubicación"}")
            TextButton(onClick = { eligiendoUbicacion = true }) { Text("Corregir") }
        }

        Text(
            "${texto.ifEmpty { "0" }} ${articulo.unidad}",
            fontSize = 40.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        )

        TecladoNumerico(
            alTocar = { tecla ->
                aviso = null
                texto = when (tecla) {
                    "C" -> ""
                    else -> texto + tecla
                }
            },
            alBorrar = { texto = texto.dropLast(1) },
        )

        OutlinedTextField(
            value = observaciones,
            onValueChange = { observaciones = it },
            label = { Text("Observaciones (opcional)") },
            modifier = Modifier.fillMaxWidth(),
        )

        aviso?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            TextButton(onClick = alCancelar, modifier = Modifier.weight(1f)) {
                Text("Cancelar")
            }
            Button(
                onClick = { confirmar() },
                modifier = Modifier.weight(2f).height(56.dp),
            ) {
                Text("Confirmar", fontSize = 18.sp)
            }
        }
    }

    confirmarDecimal?.let { pregunta ->
        AlertDialog(
            onDismissRequest = { confirmarDecimal = null },
            title = { Text("¿Va con decimales?") },
            text = { Text(pregunta.motivo) },
            confirmButton = {
                TextButton(onClick = {
                    confirmarDecimal = null
                    alConfirmar(
                        pregunta.milesimas, ubicacionReal, observaciones.ifBlank { null },
                    )
                }) { Text("Sí, cargar") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarDecimal = null }) { Text("Corregir") }
            },
        )
    }

    if (eligiendoUbicacion) {
        ElegirUbicacion(
            ubicaciones = ubicaciones,
            alElegir = { ubicacionReal = it; eligiendoUbicacion = false },
            alCerrar = { eligiendoUbicacion = false },
        )
    }
}

@Composable
private fun TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit) {
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

@Composable
private fun ElegirUbicacion(
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
