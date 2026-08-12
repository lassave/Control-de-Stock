package com.controldestock

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.controldestock.datos.BaseLocal
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.red.ClienteServidor
import com.controldestock.ui.Pantalla
import com.controldestock.ui.PantallaVinculacion
import com.controldestock.ui.Tema
import com.controldestock.ui.pantallaSegun
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val base = BaseLocal.de(this)

        setContent {
            Tema {
                Surface(modifier = Modifier.fillMaxSize()) {
                    App(base)
                }
            }
        }
    }
}

@Composable
private fun App(base: BaseLocal) {
    val alcance = rememberCoroutineScope()
    var pantalla by remember { mutableStateOf<Pantalla>(Pantalla.Cargando) }
    var vinculando by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        pantalla = pantallaSegun(base.vinculacionDao().actual())
    }

    when (pantalla) {
        Pantalla.Cargando -> Aviso("Un momento…")

        Pantalla.Vinculando -> PantallaVinculacion(
            vinculando = vinculando,
            error = error,
        ) { url, token ->
            // La cámara avisa una lectura por cuadro: sin esta guarda, el
            // mismo QR dispara veinte vinculaciones en un segundo.
            if (!vinculando) {
                vinculando = true
                error = null
                alcance.launch {
                    val vinculador = Vinculador(base) { u, t -> ClienteServidor(u, t) }
                    when (val r = vinculador.vincular(DatosDelQr(url, token))) {
                        is ResultadoDeVinculacion.Vinculado -> pantalla = Pantalla.Escaneando
                        is ResultadoDeVinculacion.Fallo -> error = r.mensaje
                    }
                    vinculando = false
                }
            }
        }

        Pantalla.Escaneando -> Aviso("Listo para contar.")
    }
}

@Composable
private fun Aviso(texto: String) {
    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            texto,
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )
    }
}
