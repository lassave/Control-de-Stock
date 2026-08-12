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
import com.controldestock.datos.UnidadEntidad
import com.controldestock.nucleo.ReglasDeCarga
import com.controldestock.nucleo.ResultadoDeCarga

/**
 * La unidad con la que se da de alta cuando no hay catálogo en el celular.
 *
 * No es una suposición: el servidor siembra «UN» en su esquema y usa esa
 * misma unidad como valor por defecto cuando el alta llega sin ninguna, así
 * que es la única que se puede mandar sabiendo que la va a aceptar. Un
 * celular sin catálogo es uno que todavía no sincronizó el maestro; bloquear
 * el alta ahí lo dejaría sin forma de registrar lo que tiene en la mano.
 */
private const val UNIDAD_POR_DEFECTO = "UN"

/**
 * El alta de un código que no está en el maestro.
 *
 * Se llega a propósito, desde el botón de la franja roja: una lectura al
 * pasar no crea un artículo. Un código mal leído, o el de la caja en vez del
 * producto, también llega como desconocido, y si cada uno creara una fila el
 * inventario se llenaría de fantasmas que alguien tiene que limpiar después.
 *
 * El código se muestra arriba y en grande: el operario tiene que poder
 * verificar que la app leyó la etiqueta que él ve.
 *
 * Acá viven las guardas del alta y no río abajo: `darDeAlta` guarda lo que le
 * den, así que una descripción vacía o una cantidad que nadie tecleó llegan
 * al servidor si esta pantalla no las ataja.
 */
@Composable
fun FichaDeAlta(
    codigo: String,
    unidades: List<UnidadEntidad>,
    ubicaciones: List<String>,
    alCancelar: () -> Unit,
    // Última para que quede como lambda final en la llamada. Los parámetros
    // van con nombre: son cinco posicionales y dos `String` pegados, así que
    // una descripción cambiada por la unidad compila igual y recién se
    // descubre cuando el servidor rechaza el alta.
    alConfirmar: (
        descripcion: String,
        unidad: String,
        ubicacion: String?,
        milesimas: Int,
        observaciones: String?,
    ) -> Unit,
) {
    var descripcion by remember { mutableStateOf("") }
    var unidad by remember {
        mutableStateOf(
            unidades.firstOrNull { it.codigo == UNIDAD_POR_DEFECTO } ?: unidades.firstOrNull(),
        )
    }
    var ubicacion by remember { mutableStateOf<String?>(null) }
    var texto by remember { mutableStateOf("") }
    var observaciones by remember { mutableStateOf("") }
    var aviso by remember { mutableStateOf<String?>(null) }
    var confirmarDecimal by remember {
        mutableStateOf<ResultadoDeCarga.PideConfirmacion?>(null)
    }
    var eligiendoUbicacion by remember { mutableStateOf(false) }
    var eligiendoUnidad by remember { mutableStateOf(false) }

    // Una sola vez y para todo: lo que se muestra tiene que ser exactamente lo
    // que se manda, o el operario confirma una unidad y se guarda otra.
    val codigoDeUnidad = unidad?.codigo ?: UNIDAD_POR_DEFECTO

    fun cargar(milesimas: Int) = alConfirmar(
        descripcion.trim(),
        codigoDeUnidad,
        ubicacion,
        milesimas,
        observaciones.ifBlank { null },
    )

    fun confirmar() {
        if (descripcion.isBlank()) {
            // Sin descripción, la fila que queda no la puede resolver nadie
            // después: el servidor también la exige.
            aviso = "Escribí qué es el producto"
            return
        }

        when (val r = ReglasDeCarga.validar(texto, unidad?.admiteDecimales == 1)) {
            is ResultadoDeCarga.Valida -> cargar(r.milesimas)
            is ResultadoDeCarga.PideConfirmacion -> confirmarDecimal = r
            is ResultadoDeCarga.Invalida -> aviso = r.motivo
        }
    }

    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Producto nuevo", fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Text(codigo, fontSize = 24.sp, fontWeight = FontWeight.Bold)

        OutlinedTextField(
            value = descripcion,
            onValueChange = { descripcion = it; aviso = null },
            label = { Text("¿Qué es?") },
            modifier = Modifier.fillMaxWidth(),
        )

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Unidad: $codigoDeUnidad")
            TextButton(onClick = { eligiendoUnidad = true }) { Text("Cambiar") }
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Ubicación: ${ubicacion ?: "sin ubicación"}")
            TextButton(onClick = { eligiendoUbicacion = true }) { Text("Elegir") }
        }

        Text(
            "${texto.ifEmpty { "0" }} $codigoDeUnidad",
            fontSize = 40.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        )

        TecladoNumerico(
            alTocar = { tecla ->
                aviso = null
                texto = if (tecla == "C") "" else texto + tecla
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
                Text("Dar de alta", fontSize = 18.sp)
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
                    cargar(pregunta.milesimas)
                }) { Text("Sí, cargar") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarDecimal = null }) { Text("Corregir") }
            },
        )
    }

    if (eligiendoUnidad) {
        AlertDialog(
            onDismissRequest = { eligiendoUnidad = false },
            title = { Text("¿Cómo se cuenta?") },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    unidades.forEach { u ->
                        TextButton(onClick = { unidad = u; eligiendoUnidad = false }) {
                            Text("${u.nombre} (${u.codigo})")
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { eligiendoUnidad = false }) { Text("Listo") }
            },
        )
    }

    if (eligiendoUbicacion) {
        ElegirUbicacion(
            ubicaciones = ubicaciones,
            alElegir = { ubicacion = it; eligiendoUbicacion = false },
            alCerrar = { eligiendoUbicacion = false },
        )
    }
}
