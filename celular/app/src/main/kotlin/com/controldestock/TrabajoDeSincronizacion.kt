package com.controldestock

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.controldestock.datos.BaseLocal
import com.controldestock.red.ClienteServidor
import java.util.concurrent.TimeUnit

/**
 * Sube los conteos pendientes cuando hay red.
 *
 * Corre solo, en segundo plano, y nunca interrumpe: el operario cuenta sin
 * enterarse de si hay señal o no.
 */
class TrabajoDeSincronizacion(
    contexto: Context,
    parametros: WorkerParameters,
) : CoroutineWorker(contexto, parametros) {

    override suspend fun doWork(): Result {
        val base = BaseLocal.de(applicationContext)
        val sincronizador = Sincronizador(base) { url, token -> ClienteServidor(url, token) }

        val resultado = sincronizador.sincronizar()

        // Reintentar es responsabilidad de WorkManager: sabe esperar a que
        // haya red en vez de quemar batería probando.
        return if (resultado.huboError) Result.retry() else Result.success()
    }

    companion object {
        private const val NOMBRE = "sincronizar-conteos"

        /**
         * Cada quince minutos es el mínimo que admite WorkManager para un
         * trabajo periódico. Alcanza: el tablero no necesita ser instantáneo,
         * y la app también sincroniza al confirmar cada conteo.
         */
        fun programar(contexto: Context) {
            val pedido = PeriodicWorkRequestBuilder<TrabajoDeSincronizacion>(
                15, TimeUnit.MINUTES,
            ).setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            ).build()

            WorkManager.getInstance(contexto).enqueueUniquePeriodicWork(
                NOMBRE, ExistingPeriodicWorkPolicy.KEEP, pedido,
            )
        }
    }
}
