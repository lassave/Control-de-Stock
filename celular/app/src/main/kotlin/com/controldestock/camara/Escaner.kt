package com.controldestock.camara

import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
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

    DisposableEffect(Unit) {
        onDispose {
            hilo.shutdown()
            lector.close()
        }
    }

    AndroidView(
        modifier = modifier,
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
                proveedor.bindToLifecycle(
                    duenio, CameraSelector.DEFAULT_BACK_CAMERA, vistaPrevia, analisis,
                )
            }, ContextCompat.getMainExecutor(ctx))

            vista
        },
    )
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
