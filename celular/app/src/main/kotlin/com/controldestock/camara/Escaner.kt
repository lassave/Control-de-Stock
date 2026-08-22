package com.controldestock.camara

import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.OutlinedIconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanner
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors

/**
 * La cámara, siempre activa, leyendo códigos.
 *
 * El operario apunta y lee: no hay botón de disparo. Cuando `activo` es
 * falso la cámara sigue prendida pero no avisa lecturas — es lo que pausa
 * el escaneo mientras hay una ficha abierta, sin el parpadeo que provocaría
 * reiniciar la cámara.
 */
@Composable
fun VistaDeCamara(
    activo: Boolean,
    alLeer: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val duenio = LocalLifecycleOwner.current
    val hilo = remember { Executors.newSingleThreadExecutor() }
    val lector = remember { BarcodeScanning.getClient() }
    val estaActivo = rememberUpdatedState(activo)
    val avisar = rememberUpdatedState(alLeer)
    var camara by remember { mutableStateOf<Camera?>(null) }
    var linternaEncendida by remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        onDispose {
            hilo.shutdown()
            lector.close()
        }
    }

    // El bind es asincrónico: `camara` puede seguir en null un rato después
    // de que el operario ya tocó el botón. Reacciona a los dos porque
    // cualquiera de las dos formas de llegar acá —tocar antes de que ligue,
    // o ligar mientras ya estaba encendida por un toque previo a esta
    // recomposición— tiene que terminar prendiendo la linterna.
    LaunchedEffect(camara, linternaEncendida) {
        try {
            camara?.cameraControl?.enableTorch(linternaEncendida)
        } catch (error: IllegalStateException) {
            // Sin unidad de flash: el mismo criterio que el resto de este
            // archivo con los errores de cámara, ver deuda conocida.
        }
    }

    Box(modifier = modifier) {
        AndroidView(
            // Sin este tamaño explícito, la superficie nativa de PreviewView
            // —un SurfaceView, compuesto aparte del árbol normal de Compose—
            // se posiciona con el primer paso de medición, uno más chico que
            // el del Box que la envuelve, y se queda ahí: el video de la
            // cámara termina flotando sobre el encabezado en vez de debajo.
            // Verificado en un celular real: sin esto tapaba «A mano» y el
            // resto del encabezado aunque el árbol de vistas los seguía
            // teniendo en el lugar correcto.
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                val vista = PreviewView(ctx)
                val futuro = ProcessCameraProvider.getInstance(ctx)

                futuro.addListener({
                    val proveedor = futuro.get()

                    val vistaPrevia = Preview.Builder().build().also {
                        it.setSurfaceProvider(vista.surfaceProvider)
                    }

                    val analisis = ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build()

                    analisis.setAnalyzer(hilo) { imagen ->
                        procesar(imagen, lector, estaActivo.value) { codigo ->
                            avisar.value(codigo)
                        }
                    }

                    proveedor.unbindAll()
                    camara = proveedor.bindToLifecycle(
                        duenio, CameraSelector.DEFAULT_BACK_CAMERA, vistaPrevia, analisis,
                    )
                }, ContextCompat.getMainExecutor(ctx))

                vista
            },
        )

        BotonLinterna(
            encendida = linternaEncendida,
            alTocar = { linternaEncendida = !linternaEncendida },
            modifier = Modifier.align(Alignment.TopEnd).padding(12.dp),
        )
    }
}

/** Círculo flotante sobre la cámara: relleno y prendido cuando está encendida. */
@Composable
private fun BotonLinterna(
    encendida: Boolean,
    alTocar: () -> Unit,
    modifier: Modifier = Modifier,
) {
    if (encendida) {
        FilledIconButton(onClick = alTocar, modifier = modifier) { Text("🔦") }
    } else {
        OutlinedIconButton(onClick = alTocar, modifier = modifier) { Text("🔦") }
    }
}

@OptIn(ExperimentalGetImage::class)
private fun procesar(
    imagen: ImageProxy,
    lector: BarcodeScanner,
    activo: Boolean,
    alLeer: (String) -> Unit,
) {
    val cruda = imagen.image
    if (cruda == null || !activo) {
        imagen.close()
        return
    }

    val entrada = InputImage.fromMediaImage(cruda, imagen.imageInfo.rotationDegrees)
    lector.process(entrada)
        .addOnSuccessListener { codigos ->
            codigos.firstOrNull { it.rawValue != null }?.let { alLeer(it.rawValue!!) }
        }
        .addOnCompleteListener { imagen.close() }
}
