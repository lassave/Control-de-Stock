package com.controldestock.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.controldestock.camara.VistaDeCamara
import com.controldestock.nucleo.leerQr

/**
 * La primera pantalla: escanear el QR del panel.
 *
 * Solo se ve una vez por celular. Si el QR no es el del panel lo dice y
 * sigue escaneando, en vez de trabarse: el operario va a apuntar sin querer
 * a media docena de cosas antes de dar con el código.
 */
@Composable
fun PantallaVinculacion(
    vinculando: Boolean,
    error: String?,
    alLeerQr: (String, String) -> Unit,
) {
    val contexto = LocalContext.current
    var hayPermiso by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(contexto, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED,
        )
    }
    var avisoDeQr by remember { mutableStateOf<String?>(null) }

    val pedirPermiso = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { concedido -> hayPermiso = concedido }

    LaunchedEffect(Unit) {
        if (!hayPermiso) pedirPermiso.launch(Manifest.permission.CAMERA)
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            "Escaneá el QR de tu nombre en el panel",
            style = MaterialTheme.typography.headlineSmall,
            textAlign = TextAlign.Center,
        )

        Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
            when {
                vinculando -> Centrado { CircularProgressIndicator() }

                hayPermiso -> VistaDeCamara(
                    activo = true,
                    modifier = Modifier.fillMaxSize(),
                    alLeer = { texto ->
                        val datos = leerQr(texto)
                        if (datos == null) {
                            avisoDeQr = "Ese código no es el del panel. Buscá el QR " +
                                "que está al lado de tu nombre, en Operarios."
                        } else {
                            avisoDeQr = null
                            alLeerQr(datos.url, datos.token)
                        }
                    },
                )

                else -> Centrado {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(
                            "La app necesita la cámara para escanear.",
                            textAlign = TextAlign.Center,
                        )
                        Button(onClick = { pedirPermiso.launch(Manifest.permission.CAMERA) }) {
                            Text("Permitir")
                        }
                    }
                }
            }
        }

        (error ?: avisoDeQr)?.let {
            Text(
                it,
                color = MaterialTheme.colorScheme.error,
                textAlign = TextAlign.Center,
            )
        }
    }
}

@Composable
private fun Centrado(contenido: @Composable () -> Unit) {
    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        contenido()
    }
}
