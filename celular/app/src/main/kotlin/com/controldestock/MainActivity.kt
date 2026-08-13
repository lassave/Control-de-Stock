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
import com.controldestock.ui.EstadoDeSubida
import com.controldestock.ui.FichaDeAlta
import com.controldestock.ui.FichaDelArticulo
import com.controldestock.ui.Pantalla
import com.controldestock.ui.PantallaEscaneo
import com.controldestock.ui.PantallaVinculacion
import com.controldestock.ui.Tema
import com.controldestock.ui.estadoTrasSubir
import com.controldestock.ui.hayQueAnunciar
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
    // El alta guarda el código y no un «sí, está abierta»: el toque se aplica
    // un cuadro después de la composición que lo dibujó, así que un dedo que
    // llega tarde puede tocar el botón cuando `codigoDesconocido` ya se
    // limpió. Guardando el código, el click se lo lleva desde la composición
    // y no queda forma de tener el alta abierta sin saber de qué código es.
    var altaDe by remember { mutableStateOf<String?>(null) }
    var pendientes by remember { mutableStateOf(0) }
    var ubicaciones by remember { mutableStateOf<List<String>>(emptyList()) }
    var unidades by remember { mutableStateOf<List<UnidadEntidad>>(emptyList()) }
    var previos by remember { mutableStateOf<List<ConteoLocal>>(emptyList()) }
    val vinculacion = remember { mutableStateOf<VinculacionEntidad?>(null) }
    // Bandera común y no estado de Compose: no tiene nada que redibujar, y
    // tiene que valer en el instante en que se toma, no en el próximo cuadro.
    val leyendo = remember { AtomicBoolean(false) }
    // Lo mismo para confirmar: entre el toque y el cierre de la ficha hay una
    // transacción y un cuadro de recomposición, y el toque se aplica antes de
    // que la ficha se vaya de la pantalla. Sin esto, un doble toque guarda dos
    // veces.
    val guardando = remember { AtomicBoolean(false) }
    var estadoDeSubida by remember {
        mutableStateOf<EstadoDeSubida>(EstadoDeSubida.Quieto)
    }
    // Lo mismo para subir: entre el toque y el cambio de estado hay un cuadro,
    // y el input se reparte antes de recomponer.
    val subiendo = remember { AtomicBoolean(false) }
    val contexto = LocalContext.current
    val avisos = remember { AvisoSonoro(contexto) }
    val contador = remember { Contador(base, RelojDelSistema.DEL_SISTEMA) }
    val sincronizador = remember {
        Sincronizador(base) { url, token -> ClienteServidor(url, token) }
    }

    DisposableEffect(Unit) { onDispose { avisos.cerrar() } }

    /**
     * Sube lo pendiente y deja el indicador contando lo que pasó.
     *
     * La usan las tres sincronizaciones —la del conteo, la del alta y la que
     * pide el operario— a propósito: con un estado por cada una, el operario
     * vería «3 sin subir» mientras esos tres están viajando.
     *
     * El error, en cambio, es solo de la que él pidió: ver `estadoTrasSubir`.
     */
    suspend fun subir(loPidioElOperario: Boolean = false): ResultadoDeSync {
        estadoDeSubida = EstadoDeSubida.Subiendo
        val resultado = sincronizador.sincronizar()
        pendientes = base.conteoDao().cantidadPendientes()
        estadoDeSubida = estadoTrasSubir(resultado.huboError, loPidioElOperario)
        return resultado
    }

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
                fichaAbierta = hallazgo is Hallazgo.Encontrado || altaDe != null,
                avisoDeDesconocido = avisoDesconocido,
                alDarDeAlta = codigoDesconocido?.let { codigo ->
                    {
                        // Si en el mismo cuadro entró una lectura y abrió una
                        // ficha, se descarta. No es tirar trabajo del operario:
                        // el botón solo existe mientras no hay ninguna ficha
                        // —al abrirse una, el aviso del desconocido se limpia y
                        // la franja desaparece—, así que esa ficha nació vacía
                        // en el cuadro anterior, debajo del dedo que ya iba al
                        // botón, de una lectura que él no pidió. Lo que quiso
                        // hacer es el alta.
                        hallazgo = null
                        altaDe = codigo
                    }
                },
                estadoDeSubida = estadoDeSubida,
                alSubir = {
                    // La bandera se toma en el toque, sincrónicamente: entre
                    // el toque y el cambio de estado hay un cuadro, y el
                    // input se reparte antes de recomponer.
                    if (subiendo.compareAndSet(false, true)) {
                        alcance.launch {
                            try {
                                subir(loPidioElOperario = true)
                            } finally {
                                subiendo.set(false)
                            }
                        }
                    }
                },
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
                    // Mira lo mismo que decide `fichaAbierta`: si mirara otra
                    // cosa, la cámara seguiría entregando lecturas con una
                    // ficha en pantalla.
                    val laToma = hallazgo == null && altaDe == null &&
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
                                // esta lectura llegó tarde y se descarta —si
                                // no, se aplica encima de lo que el operario
                                // ya eligió, que es lo único que él vio.
                                if (hallazgo != null || altaDe != null) return@launch

                                // El mismo desconocido, cuadro tras cuadro, no
                                // se vuelve a anunciar: la franja ya lo está
                                // mostrando.
                                val anunciar = hayQueAnunciar(h, codigoDesconocido)

                                when (h) {
                                    is Hallazgo.Encontrado -> {
                                        if (anunciar) avisos.leido()
                                        avisoDesconocido = null
                                        codigoDesconocido = null
                                        previos = previosDelArticulo.orEmpty()
                                        hallazgo = h
                                    }
                                    is Hallazgo.Desconocido -> {
                                        if (anunciar) avisos.desconocido()
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
                        if (guardando.compareAndSet(false, true)) {
                            alcance.launch {
                                try {
                                    contador.registrar(
                                        encontrado.articulo, milesimas, ubicacionReal,
                                        observaciones,
                                    )
                                    avisos.cargado()
                                    hallazgo = null
                                    pendientes = base.conteoDao().cantidadPendientes()
                                } finally {
                                    guardando.set(false)
                                }

                                // Intento inmediato: con señal, el tablero se
                                // entera en el momento. Sin señal no pasa nada y
                                // el trabajo periódico lo sube más tarde. Va
                                // después de cerrar la ficha a propósito: al
                                // revés, el operario esperaría a la red para
                                // poder seguir contando. Y fuera de la guarda
                                // por lo mismo: esperando treinta segundos de
                                // timeout, el conteo siguiente se perdería.
                                subir()
                            }
                        }
                    }
                }

                altaDe?.let { codigo ->
                    FichaDeAlta(
                        codigo = codigo,
                        unidades = unidades,
                        ubicaciones = ubicaciones,
                        alCancelar = { altaDe = null },
                    ) { descripcion, unidad, ubicacion, milesimas, observaciones ->
                        // Sin esta guarda, un toque repetido crea dos artículos
                        // locales con el mismo código: la tabla de códigos los
                        // acepta a los dos —su clave es (código, artículo)— y
                        // después `porCodigo` elige uno cualquiera de los dos.
                        // El aviso de repetido pasa a ver la mitad de la
                        // historia, y arriba el servidor junta las dos altas en
                        // un artículo con los dos conteos: el SKU queda contado
                        // dos veces, que es justo lo que el aviso existe para
                        // evitar.
                        if (guardando.compareAndSet(false, true)) {
                            alcance.launch {
                                try {
                                    // Con nombre: son dos `String` pegados y un
                                    // alta con la unidad en la descripción
                                    // compila igual, y se descubre cuando el
                                    // servidor la rechaza y el conteo ya está
                                    // hecho.
                                    contador.darDeAlta(
                                        codigo = codigo,
                                        descripcion = descripcion,
                                        unidad = unidad,
                                        ubicacion = ubicacion,
                                        milesimas = milesimas,
                                        observaciones = observaciones,
                                    )
                                    avisos.cargado()
                                    altaDe = null
                                    codigoDesconocido = null
                                    avisoDesconocido = null
                                    // La ubicación nueva pasa a estar disponible
                                    // para corregir en las fichas siguientes.
                                    ubicaciones = contador.ubicaciones()
                                    pendientes = base.conteoDao().cantidadPendientes()
                                } finally {
                                    // Antes de la red: si la guarda esperara al
                                    // sincronizado, el conteo siguiente se
                                    // perdería sin que el operario se entere.
                                    guardando.set(false)
                                }

                                val resultado = subir()

                                // El servidor ya conocía ese código: lo dio de
                                // alta otro operario hace un minuto, o coincide
                                // con el SKU de uno del maestro. La descripción
                                // que escribió este operario se descartó, así
                                // que merece enterarse mientras sigue mirando.
                                // Se busca por código porque en la misma subida
                                // pueden viajar varias altas juntas, y el aviso
                                // habla del producto que acaba de tener en la
                                // mano.
                                //
                                // Y solo si la pantalla sigue como la dejó el
                                // alta: sincronizar puede tardar treinta
                                // segundos contra una red que no contesta, y
                                // para entonces el operario ya está en otro
                                // producto. Una franja roja sobre la ficha de
                                // otra cosa no le dice nada, le hace desconfiar
                                // de lo que tiene adelante.
                                val siguePudiendoLeerse =
                                    hallazgo == null && altaDe == null &&
                                        avisoDesconocido == null

                                if (siguePudiendoLeerse) {
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
