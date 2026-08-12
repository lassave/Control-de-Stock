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
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.nucleo.RelojDelSistema
import com.controldestock.red.ClienteServidor
import com.controldestock.ui.AvisoSonoro
import com.controldestock.ui.FichaDeAlta
import com.controldestock.ui.FichaDelArticulo
import com.controldestock.ui.Pantalla
import com.controldestock.ui.PantallaEscaneo
import com.controldestock.ui.PantallaVinculacion
import com.controldestock.ui.Tema
import com.controldestock.ui.pantallaSegun
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

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
    var codigoDesconocido by remember { mutableStateOf<String?>(null) }
    var dandoDeAlta by remember { mutableStateOf(false) }
    var pendientes by remember { mutableStateOf(0) }
    var ubicaciones by remember { mutableStateOf<List<String>>(emptyList()) }
    var unidades by remember { mutableStateOf<List<UnidadEntidad>>(emptyList()) }
    var previos by remember { mutableStateOf<List<ConteoLocal>>(emptyList()) }
    val vinculacion = remember { mutableStateOf<VinculacionEntidad?>(null) }
    // Bandera común y no estado de Compose: no tiene nada que redibujar, y
    // tiene que valer en el instante en que se toma, no en el próximo cuadro.
    val leyendo = remember { AtomicBoolean(false) }
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
        unidades = contador.unidades()
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
                            unidades = contador.unidades()
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
                fichaAbierta = hallazgo is Hallazgo.Encontrado || dandoDeAlta,
                avisoDeDesconocido = avisoDesconocido,
                alDarDeAlta = codigoDesconocido?.let { { dandoDeAlta = true } },
                alLeer = { codigo ->
                    // La cámara avisa una lectura por cuadro, y esta guarda
                    // sola no alcanza: decide acá, pero el estado se escribe
                    // recién cuando la corrutina vuelve de la base. En esa
                    // ventana entra el barrido que hace el operario al bajar
                    // el celular para tocar «Darlo de alta», y la lectura de
                    // otro estante se aplica encima de lo que ya tocó.
                    //
                    // La bandera se toma en el mismo golpe que la lectura,
                    // así hay una sola búsqueda en vuelo por vez y no un
                    // chorro de consultas por cuadro.
                    val laToma = hallazgo == null && !dandoDeAlta &&
                        leyendo.compareAndSet(false, true)

                    if (laToma) {
                        alcance.launch {
                            try {
                                // Todo lo que consulta la base va primero:
                                // después de revalidar no puede quedar ninguna
                                // suspensión, o la ventana se vuelve a abrir
                                // entre el control y la escritura.
                                val h = contador.buscar(codigo)
                                val previosDelArticulo = (h as? Hallazgo.Encontrado)
                                    ?.let { contador.conteosDe(it.articulo) }

                                // Lo que valía al leer puede no valer más: si
                                // mientras tanto se abrió una ficha o el alta,
                                // esta lectura llegó tarde y se descarta. Sin
                                // esto queda `dandoDeAlta` en true con el
                                // código ya borrado, y la app se traba con una
                                // ficha vacía que nadie puede cerrar.
                                if (hallazgo != null || dandoDeAlta) return@launch

                                when (h) {
                                    is Hallazgo.Encontrado -> {
                                        avisos.leido()
                                        avisoDesconocido = null
                                        codigoDesconocido = null
                                        previos = previosDelArticulo.orEmpty()
                                        hallazgo = h
                                    }
                                    is Hallazgo.Desconocido -> {
                                        avisos.desconocido()
                                        codigoDesconocido = h.codigo
                                        avisoDesconocido =
                                            "Este código no está en el conteo: ${h.codigo}"
                                    }
                                }
                            } finally {
                                leyendo.set(false)
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
                        previos = previos,
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

                if (dandoDeAlta) {
                    codigoDesconocido?.let { codigo ->
                        FichaDeAlta(
                            codigo = codigo,
                            unidades = unidades,
                            ubicaciones = ubicaciones,
                            alCancelar = { dandoDeAlta = false },
                        ) { descripcion, unidad, ubicacion, milesimas, observaciones ->
                            alcance.launch {
                                // Con nombre: son dos `String` pegados y un
                                // alta con la unidad en la descripción compila
                                // igual, y se descubre cuando el servidor la
                                // rechaza y el conteo ya está hecho.
                                contador.darDeAlta(
                                    codigo = codigo,
                                    descripcion = descripcion,
                                    unidad = unidad,
                                    ubicacion = ubicacion,
                                    milesimas = milesimas,
                                    observaciones = observaciones,
                                )
                                avisos.cargado()
                                dandoDeAlta = false
                                codigoDesconocido = null
                                avisoDesconocido = null
                                // La ubicación nueva pasa a estar disponible
                                // para corregir en las fichas siguientes.
                                ubicaciones = contador.ubicaciones()
                                pendientes = base.conteoDao().cantidadPendientes()

                                val resultado = sincronizador.sincronizar()
                                pendientes = base.conteoDao().cantidadPendientes()

                                // El servidor ya conocía ese código: lo dio de
                                // alta otro operario hace un minuto, o coincide
                                // con el SKU de uno del maestro. La descripción
                                // que escribió este operario se descartó, así
                                // que merece enterarse mientras sigue mirando.
                                // Se busca por código porque en la misma subida
                                // pueden viajar varias altas juntas, y el aviso
                                // habla del producto que acaba de tener en la
                                // mano.
                                resultado.yaExistian
                                    .firstOrNull { it.codigo == codigo }
                                    ?.let {
                                        avisoDesconocido =
                                            "Ese código ya estaba: ${it.descripcion}"
                                    }
                            }
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
