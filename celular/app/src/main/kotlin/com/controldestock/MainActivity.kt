package com.controldestock

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
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
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import com.controldestock.datos.BaseLocal
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.VinculacionEntidad
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.DatosDelQr
import com.controldestock.nucleo.RelojDelSistema
import com.controldestock.nucleo.UbicacionAsignada
import com.controldestock.red.ClienteServidor
import com.controldestock.red.ErrorDeServidor
import com.controldestock.ui.Atras
import com.controldestock.ui.AvisoSonoro
import com.controldestock.ui.DialogoCodigoAMano
import com.controldestock.ui.EstadoDeSubida
import com.controldestock.ui.FichaDeAlta
import com.controldestock.ui.FichaDelArticulo
import com.controldestock.ui.Pantalla
import com.controldestock.ui.PantallaEscaneo
import com.controldestock.ui.PantallaMiLista
import com.controldestock.ui.PantallaVinculacion
import com.controldestock.ui.Tema
import com.controldestock.ui.atrasCierra
import com.controldestock.ui.estadoTrasSubir
import com.controldestock.ui.fichaAbierta
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
    // Mismo tratamiento visual que el desconocido —franja no bloqueante—,
    // pero en su propio par de variables: a diferencia de un desconocido,
    // esto nunca ofrece «Darlo de alta», el artículo ya existe.
    var avisoFueraDePasada by remember { mutableStateOf<String?>(null) }
    var codigoFueraDePasada by remember { mutableStateOf<String?>(null) }
    // El alta guarda el código y no un «sí, está abierta»: el toque se aplica
    // un cuadro después de la composición que lo dibujó, así que un dedo que
    // llega tarde puede tocar el botón cuando `codigoDesconocido` ya se
    // limpió. Guardando el código, el click se lo lleva desde la composición
    // y no queda forma de tener el alta abierta sin saber de qué código es.
    var altaDe by remember { mutableStateOf<String?>(null) }
    // Cuenta como una ficha más para pausar la cámara: sin esto, una
    // lectura de cámara en el medio le pisa el código que el operario está
    // tipeando a mano.
    var ingresandoAMano by remember { mutableStateOf(false) }
    var pendientes by remember { mutableStateOf(0) }
    var ubicaciones by remember { mutableStateOf<List<String>>(emptyList()) }
    var unidades by remember { mutableStateOf<List<UnidadEntidad>>(emptyList()) }
    var ubicacionesAsignadas by remember { mutableStateOf<List<UbicacionAsignada>>(emptyList()) }
    var actualizandoLista by remember { mutableStateOf(false) }
    var avisoDeActualizacion by remember { mutableStateOf<String?>(null) }
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
    // Y para actualizar la lista: un rebote rápido de fondo/primer plano no
    // puede lanzar diez pedidos superpuestos de 10 segundos de timeout cada
    // uno.
    val actualizandoListaGuarda = remember { AtomicBoolean(false) }
    val contexto = LocalContext.current
    val avisos = remember { AvisoSonoro(contexto) }
    val contador = remember { Contador(base, RelojDelSistema.DEL_SISTEMA) }
    val sincronizador = remember {
        Sincronizador(base) { url, token -> ClienteServidor(url, token) }
    }
    val listaDeTrabajo = remember { ListaDeTrabajo(base) }

    /**
     * Pide al servidor las ubicaciones asignadas y arma la lista con lo que
     * queda en la base local.
     *
     * La base se escribe solo si el pedido salió bien: una lista vacía que
     * vino del servidor sí se escribe —es un dato—, pero un error nunca toca
     * lo que ya había, porque escribir encima le borraría el reparto al
     * operario. El aviso es discreto a propósito: nunca el texto crudo del
     * servidor, que para este pedido puede hablar de un 409 que no es lo que
     * parece.
     *
     * Lee la vinculación de la base y no del estado del composable: este
     * efecto puede dispararse antes de que el `LaunchedEffect(Unit)` que la
     * carga haya terminado.
     */
    suspend fun refrescarListaAsignada() {
        if (!actualizandoListaGuarda.compareAndSet(false, true)) return
        try {
            actualizandoLista = true
            val quien = base.vinculacionDao().actual()
            if (quien != null) {
                try {
                    val cliente = ClienteServidor(quien.url, quien.token)
                    val respuesta = cliente.misUbicaciones()
                    listaDeTrabajo.guardar(respuesta)
                    avisoDeActualizacion = null
                } catch (error: ErrorDeServidor) {
                    avisoDeActualizacion =
                        "No se pudo actualizar. Se muestra la última lista que bajó."
                }
            }
            ubicacionesAsignadas = listaDeTrabajo.armar()
        } finally {
            actualizandoLista = false
            actualizandoListaGuarda.set(false)
        }
    }

    // Al arrancar y al volver del fondo. ON_START y no ON_RESUME: ese también
    // dispara al cerrar un diálogo del sistema o al volver el foco tras el
    // permiso de cámara, y ahí no se pidió ningún refresco.
    //
    // El lifecycleOwner va explícito: el compose-bom de este proyecto es
    // anterior al que provee solo el `LocalLifecycleOwner` que
    // lifecycle-runtime-compose busca por defecto —son dos composition
    // locals con el mismo nombre, de paquetes distintos—, y sin esto la app
    // cierra al abrir con «CompositionLocal LocalLifecycleOwner not present».
    LifecycleEventEffect(
        Lifecycle.Event.ON_START,
        lifecycleOwner = LocalLifecycleOwner.current,
    ) {
        alcance.launch { refrescarListaAsignada() }
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

    /**
     * Resuelve un código nuevo, venga de la cámara o escrito a mano: los
     * dos entran por acá para heredar el mismo timbre, el mismo aviso de
     * repetido y el mismo camino al alta rápida sin duplicar nada.
     */
    val leerCodigo: (String) -> Unit = { codigo ->
        // La cámara avisa una lectura por cuadro, y esta guarda sola no
        // alcanza: decide acá, pero el estado se escribe recién cuando la
        // corrutina vuelve de la base. En esa ventana entra el barrido que
        // hace el operario al bajar el celular para tocar «Darlo de alta»,
        // y la lectura de otro estante se aplica encima de lo que ya tocó.
        //
        // La bandera se toma en el mismo golpe que la lectura, así hay una
        // sola búsqueda en vuelo por vez y no un chorro de consultas por
        // cuadro. Usa `fichaAbierta`, la misma función que decide qué hay
        // que tapar en pantalla: mira las tres causas —hallazgo, altaDe e
        // ingresandoAMano—, así una lectura en vuelo no se cuela mientras
        // el operario tiene el diálogo de código a mano abierto.
        val laToma = !fichaAbierta(hallazgo, altaDe, ingresandoAMano) &&
            leyendo.compareAndSet(false, true)

        if (laToma) {
            alcance.launch {
                try {
                    // Todo lo que consulta la base va primero: después de
                    // revalidar no puede quedar ninguna suspensión, o la
                    // ventana se vuelve a abrir entre el control y la
                    // escritura.
                    val h = contador.buscar(codigo)
                    val previosDelArticulo = (h as? Hallazgo.Encontrado)
                        ?.let { contador.conteosDe(it.articulo) }

                    // Lo que valía al leer puede no valer más: si mientras
                    // tanto se abrió una ficha, el alta o el diálogo de
                    // código a mano, esta lectura llegó tarde y se
                    // descarta —si no, se aplica encima de lo que el
                    // operario ya eligió, que es lo único que él vio.
                    if (fichaAbierta(hallazgo, altaDe, ingresandoAMano)) return@launch

                    // El mismo desconocido, o el mismo fuera de pasada,
                    // cuadro tras cuadro, no se vuelve a anunciar: la franja
                    // ya lo está mostrando. Cada uno se compara contra su
                    // propia franja, así una lectura no pisa el «no se
                    // repite» de la otra.
                    when (h) {
                        is Hallazgo.Encontrado -> {
                            if (hayQueAnunciar(h, codigoDesconocido)) avisos.leido()
                            avisoDesconocido = null
                            codigoDesconocido = null
                            avisoFueraDePasada = null
                            codigoFueraDePasada = null
                            previos = previosDelArticulo.orEmpty()
                            hallazgo = h
                        }
                        is Hallazgo.Desconocido -> {
                            if (hayQueAnunciar(h, codigoDesconocido)) avisos.desconocido()
                            codigoDesconocido = h.codigo
                            avisoDesconocido =
                                "Este código no está en el conteo: ${h.codigo}"
                            avisoFueraDePasada = null
                            codigoFueraDePasada = null
                        }
                        is Hallazgo.FueraDePasada -> {
                            if (hayQueAnunciar(h, codigoFueraDePasada)) avisos.desconocido()
                            codigoFueraDePasada = h.codigo
                            avisoFueraDePasada =
                                "No corresponde a este conteo: ${h.descripcion}"
                            avisoDesconocido = null
                            codigoDesconocido = null
                        }
                    }
                } finally {
                    leyendo.set(false)
                }
            }
        }
    }

    LaunchedEffect(Unit) {
        vinculacion.value = base.vinculacionDao().actual()
        pantalla = pantallaSegun(vinculacion.value)
        pendientes = base.conteoDao().cantidadPendientes()
        ubicaciones = contador.ubicaciones()
        unidades = contador.unidades()
        // De la base local, sin red: para que la lista no arranque vacía
        // mientras se espera la respuesta del servidor.
        ubicacionesAsignadas = listaDeTrabajo.armar()
    }

    // Cada vez que se vuelve a la lista, sin red: lo que se acaba de contar
    // tiene que aparecer tildado sin que el operario tenga que tocar
    // «Actualizar», que además pega contra el servidor y no hace falta para
    // esto —el tilde sale de la base local, no de lo que baja el reparto—.
    LaunchedEffect(pantalla) {
        if (pantalla == Pantalla.EnLaLista) {
            ubicacionesAsignadas = listaDeTrabajo.armar()
        }
    }

    when (pantalla) {
        Pantalla.Cargando -> Aviso("Un momento…")

        Pantalla.EnLaLista -> PantallaMiLista(
            ubicaciones = ubicacionesAsignadas,
            actualizando = actualizandoLista,
            avisoDeActualizacion = avisoDeActualizacion,
            pendientes = pendientes,
            estadoDeSubida = estadoDeSubida,
            alActualizar = { alcance.launch { refrescarListaAsignada() } },
            alSubir = {
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
            alContar = { pantalla = Pantalla.Escaneando },
        )

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
                            pantalla = Pantalla.EnLaLista
                            // Para que la primera entrada a la lista no esté
                            // vacía: recién ahora hay un operario vinculado
                            // del que pedir el reparto.
                            refrescarListaAsignada()
                        }
                        is ResultadoDeVinculacion.Fallo -> error = r.mensaje
                    }
                    vinculando = false
                }
            }
        }

        Pantalla.Escaneando -> {
            val quien = vinculacion.value
            // Cuando la única causa es `ingresandoAMano`, `fichaAbierta`
            // igual da true: `PantallaEscaneo` muestra la `Surface` de la
            // ficha, pero el contenido que le pasamos (más abajo) no
            // dibuja nada para ese caso, así que queda en 0dp de alto —no
            // se ve nada raro en pantalla.
            val hayAlgoAbierto = fichaAbierta(hallazgo, altaDe, ingresandoAMano)

            // Se registra solo acá: en la lista, atrás sale de la app, que es
            // lo que el operario espera. Volver a la lista con una ficha a
            // medio cargar tiraría lo que tipeó, así que se cierra una cosa
            // por vez, en el mismo orden que `atrasCierra` define.
            BackHandler {
                when (atrasCierra(hallazgo, altaDe, ingresandoAMano)) {
                    Atras.CierraIngresoAMano -> ingresandoAMano = false
                    Atras.CierraAlta -> altaDe = null
                    Atras.CierraFicha -> hallazgo = null
                    Atras.VuelveALaLista -> pantalla = Pantalla.EnLaLista
                }
            }

            PantallaEscaneo(
                operario = quien?.operarioNombre.orEmpty(),
                pasada = quien?.pasadaEtiqueta.orEmpty(),
                pendientes = pendientes,
                fichaAbierta = hayAlgoAbierto,
                // Los dos son la misma franja no bloqueante y nunca conviven:
                // cada lectura limpia al otro antes de fijar el suyo.
                avisoDeDesconocido = avisoDesconocido ?: avisoFueraDePasada,
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
                puedeIngresarAMano = !hayAlgoAbierto,
                alIngresarAMano = { ingresandoAMano = true },
                alVolver = { pantalla = Pantalla.EnLaLista },
                alLeer = leerCodigo,
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
                                        avisoDesconocido == null && avisoFueraDePasada == null

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

            if (ingresandoAMano) {
                DialogoCodigoAMano(
                    // El orden importa: `ingresandoAMano` tiene que quedar
                    // en `false` antes de llamar a `leerCodigo`, porque esa
                    // función arranca revisando `fichaAbierta` y con el
                    // diálogo todavía "abierto" se bloquearía a sí misma.
                    //
                    // Queda una ventana angosta y preexistente: si una
                    // lectura de cámara ya está en vuelo (`leyendo` en
                    // `true`, esperando la consulta a la base) justo cuando
                    // el operario confirma, este `leerCodigo` no toma la
                    // guarda —`compareAndSet` falla— y el código tipeado se
                    // descarta en silencio. Es corta (dura lo que tarda una
                    // consulta) y no la introduce este arreglo; no hace
                    // falta cerrarla acá.
                    alConfirmar = { codigo ->
                        ingresandoAMano = false
                        leerCodigo(codigo)
                    },
                    alCancelar = { ingresandoAMano = false },
                )
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
