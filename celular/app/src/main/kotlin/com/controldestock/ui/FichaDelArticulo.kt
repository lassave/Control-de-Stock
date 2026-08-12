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
import com.controldestock.nucleo.Cantidades
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.ReglasDeCarga
import com.controldestock.nucleo.Repeticion
import com.controldestock.nucleo.ResultadoDeCarga
import com.controldestock.nucleo.horaLocal

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
    /** Los conteos que este celular ya hizo de este artículo. */
    previos: List<ConteoLocal>,
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
    var confirmarRepetido by remember {
        mutableStateOf<Pair<Int, Repeticion.YaContado>?>(null)
    }
    var eligiendoUbicacion by remember { mutableStateOf(false) }

    fun cargar(milesimas: Int) =
        alConfirmar(milesimas, ubicacionReal, observaciones.ifBlank { null })

    /**
     * El último filtro antes de cargar: ¿ya se contó acá?
     *
     * Va después de la pregunta por el decimal y no antes: preguntar dos
     * cosas a la vez no se entiende, y la cantidad tiene que estar resuelta
     * para poder decir cuánto se está sumando.
     */
    fun preguntarOCargar(milesimas: Int) {
        val repetido = Repeticion.buscar(previos, articulo.ubicacion, ubicacionReal)
        if (repetido == null) cargar(milesimas) else confirmarRepetido = milesimas to repetido
    }

    fun confirmar() {
        when (val r = ReglasDeCarga.validar(texto, admiteDecimales)) {
            is ResultadoDeCarga.Valida -> preguntarOCargar(r.milesimas)
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
                    preguntarOCargar(pregunta.milesimas)
                }) { Text("Sí, cargar") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarDecimal = null }) { Text("Corregir") }
            },
        )
    }

    confirmarRepetido?.let { (milesimas, repetido) ->
        // Sin ubicación la frase se corta antes del «en»: «en sin ubicación»
        // no es castellano. Detrás de dos puntos, como en el encabezado de la
        // ficha, el mismo literal se lee bien; adentro de una oración no.
        val donde = (ubicacionReal ?: articulo.ubicacion)?.let { " en $it" }.orEmpty()

        AlertDialog(
            onDismissRequest = { confirmarRepetido = null },
            title = { Text("¿Ya lo contaste acá?") },
            text = {
                Text(
                    "Ya cargaste ${Cantidades.aTexto(repetido.milesimas)} ${articulo.unidad} " +
                        "de este producto$donde a las ${horaLocal(repetido.cuando)}. " +
                        "¿Sumás otra carga?",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmarRepetido = null
                    cargar(milesimas)
                }) { Text("Cargar igual") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarRepetido = null }) { Text("Cancelar") }
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
