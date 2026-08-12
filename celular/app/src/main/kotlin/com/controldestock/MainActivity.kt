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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.nucleo.RelojDelSistema
import com.controldestock.red.ClienteServidor
import com.controldestock.ui.AvisoSonoro
import com.controldestock.ui.FichaDelArticulo
import com.controldestock.ui.Pantalla
import com.controldestock.ui.PantallaEscaneo
import com.controldestock.ui.PantallaVinculacion
import com.controldestock.ui.Tema
import com.controldestock.ui.pantallaSegun
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val base = BaseLocal.de(this)
        TrabajoDeSincronizacion.programar(this)

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
    var hallazgo by remember { mutableStateOf<Hallazgo?>(null) }
    var avisoDesconocido by remember { mutableStateOf<String?>(null) }
    var pendientes by remember { mutableStateOf(0) }
    var ubicaciones by remember { mutableStateOf<List<String>>(emptyList()) }
    val vinculacion = remember { mutableStateOf<VinculacionEntidad?>(null) }
    val contexto = LocalContext.current
    val avisos = remember { AvisoSonoro(contexto) }
    val contador = remember { Contador(base, RelojDelSistema.DEL_SISTEMA) }
    val sincronizador = remember {
        Sincronizador(base) { url, token -> ClienteServidor(url, token) }
    }

    DisposableEffect(Unit) { onDispose { avisos.cerrar() } }

    LaunchedEffect(Unit) {
        vinculacion.value = base.vinculacionDao().actual()
        pantalla = pantallaSegun(vinculacion.value)
        pendientes = base.conteoDao().cantidadPendientes()
        ubicaciones = contador.ubicaciones()
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
                        is ResultadoDeVinculacion.Vinculado -> {
                            // Recién acá existen el operario y el maestro: sin
                            // releerlos, la pantalla de escaneo arranca sin
                            // nombre, sin pasada y sin ubicaciones para
                            // corregir hasta que se reabra la app.
                            vinculacion.value = base.vinculacionDao().actual()
                            ubicaciones = contador.ubicaciones()
                            pantalla = Pantalla.Escaneando
                        }
                        is ResultadoDeVinculacion.Fallo -> error = r.mensaje
                    }
                    vinculando = false
                }
            }
        }

        Pantalla.Escaneando -> {
            val quien = vinculacion.value
            PantallaEscaneo(
                operario = quien?.operarioNombre.orEmpty(),
                pasada = quien?.pasadaEtiqueta.orEmpty(),
                pendientes = pendientes,
                fichaAbierta = hallazgo is Hallazgo.Encontrado,
                avisoDeDesconocido = avisoDesconocido,
                alLeer = { codigo ->
                    // La cámara avisa una lectura por cuadro: sin esta guarda
                    // se abrirían decenas de fichas del mismo código.
                    if (hallazgo == null) {
                        alcance.launch {
                            when (val h = contador.buscar(codigo)) {
                                is Hallazgo.Encontrado -> {
                                    avisos.leido()
                                    avisoDesconocido = null
                                    hallazgo = h
                                }
                                is Hallazgo.Desconocido -> {
                                    avisos.desconocido()
                                    avisoDesconocido =
                                        "Este código no está en el conteo: ${h.codigo}"
                                }
                            }
                        }
                    }
                },
            ) {
                (hallazgo as? Hallazgo.Encontrado)?.let { encontrado ->
                    FichaDelArticulo(
                        articulo = encontrado.articulo,
                        admiteDecimales = encontrado.admiteDecimales,
                        ubicaciones = ubicaciones,
                        // Provisorio hasta la Task 7, que lo reemplaza por
                        // `contador.conteosDe(encontrado.articulo)`. Con la
                        // lista vacía el aviso de repetido no se dispara nunca
                        // en la app: la ficha lo tiene y sus tests lo cubren,
                        // pero el operario todavía no lo ve.
                        previos = emptyList(),
                        alCancelar = { hallazgo = null },
                    ) { milesimas, ubicacionReal, observaciones ->
                        alcance.launch {
                            contador.registrar(
                                encontrado.articulo, milesimas, ubicacionReal, observaciones,
                            )
                            avisos.cargado()
                            hallazgo = null
                            pendientes = base.conteoDao().cantidadPendientes()

                            // Intento inmediato: con señal, el tablero se
                            // entera en el momento. Sin señal no pasa nada y
                            // el trabajo periódico lo sube más tarde. Va
                            // después de cerrar la ficha a propósito: al
                            // revés, el operario esperaría a la red para
                            // poder seguir contando.
                            sincronizador.sincronizar()
                            pendientes = base.conteoDao().cantidadPendientes()
                        }
                    }
                }
            }
        }
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
