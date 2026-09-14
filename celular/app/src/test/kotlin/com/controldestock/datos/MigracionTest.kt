package com.controldestock.datos

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.controldestock.nucleo.EstadoSync
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

// Copiado de app/schemas/com.controldestock.datos.BaseLocal/1.json.
private val ESQUEMA_V1 = listOf(
    "CREATE TABLE IF NOT EXISTS `vinculacion` (`id` INTEGER NOT NULL, " +
        "`url` TEXT NOT NULL, `token` TEXT NOT NULL, `operarioId` INTEGER NOT NULL, " +
        "`operarioNombre` TEXT NOT NULL, `sesionId` INTEGER NOT NULL, " +
        "`pasadaId` INTEGER NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`pasadaEtiqueta` TEXT NOT NULL, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `articulo` (`id` INTEGER NOT NULL, " +
        "`idOrden` INTEGER NOT NULL, `tipo` TEXT, `material` TEXT, `sku` TEXT NOT NULL, " +
        "`descripcion` TEXT NOT NULL, `grupo` TEXT, `ubicacion` TEXT, " +
        "`unidad` TEXT NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`sesionId` INTEGER NOT NULL, `busqueda` TEXT NOT NULL, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `codigo` (`codigo` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, PRIMARY KEY(`codigo`, `articuloId`))",
    "CREATE INDEX IF NOT EXISTS `index_codigo_codigo` ON `codigo` (`codigo`)",
    "CREATE TABLE IF NOT EXISTS `unidad` (`codigo` TEXT NOT NULL, " +
        "`nombre` TEXT NOT NULL, `admiteDecimales` INTEGER NOT NULL, PRIMARY KEY(`codigo`))",
    "CREATE TABLE IF NOT EXISTS `conteo` (`uuid` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, `sesionId` INTEGER NOT NULL, " +
        "`codigo` TEXT NOT NULL, `cantidad` INTEGER NOT NULL, `ubicacionReal` TEXT, " +
        "`observaciones` TEXT, `fueraAsignacion` INTEGER NOT NULL, " +
        "`timestampDispositivo` TEXT NOT NULL, `anulaUuid` TEXT, " +
        "`estadoSync` TEXT NOT NULL, `motivoRechazo` TEXT, PRIMARY KEY(`uuid`))",
)

// El `identityHash` del 1.json. Room lo guarda en `room_master_table` y lo
// compara al abrir: sin esa fila, la base no parece de la versión 1 sino
// una base ajena, y Room se niega a migrarla.
private const val HASH_V1 = "95de6047ad819d0ac98cd3189bce4d80"

@RunWith(RobolectricTestRunner::class)
class MigracionTest {

    private val contexto = ApplicationProvider.getApplicationContext<Context>()

    /** Deja en disco una base tal como la escribía la versión 1 de la app. */
    private fun crearBaseVieja(nombre: String, poblar: (SQLiteDatabase) -> Unit): String {
        val archivo = contexto.getDatabasePath(nombre)
        archivo.parentFile?.mkdirs()
        archivo.delete()

        val vieja = SQLiteDatabase.openOrCreateDatabase(archivo, null)
        ESQUEMA_V1.forEach(vieja::execSQL)
        vieja.execSQL(
            "CREATE TABLE IF NOT EXISTS room_master_table " +
                "(id INTEGER PRIMARY KEY, identity_hash TEXT)",
        )
        vieja.execSQL(
            "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
            arrayOf(HASH_V1),
        )
        poblar(vieja)
        vieja.version = 1
        vieja.close()

        return archivo.absolutePath
    }

    private fun abrirMigrada(ruta: String): BaseLocal =
        Room.databaseBuilder(contexto, BaseLocal::class.java, ruta)
            .addMigrations(
                BaseLocal.MIGRACION_1_2, BaseLocal.MIGRACION_2_3, BaseLocal.MIGRACION_3_4,
                BaseLocal.MIGRACION_4_5, BaseLocal.MIGRACION_5_6,
            )
            .build()

    @Test
    fun `actualizar la app no se lleva los conteos sin subir`() = runTest {
        // Es el peor momento posible para perder algo: el operario actualiza
        // la app en medio del inventario y lo que contó a la mañana no viajó
        // todavía.
        val ruta = crearBaseVieja("vieja-con-conteos.db") { vieja ->
            vieja.execSQL(
                """
                INSERT INTO conteo (
                    uuid, articuloId, sesionId, codigo, cantidad, ubicacionReal,
                    observaciones, fueraAsignacion, timestampDispositivo, anulaUuid,
                    estadoSync, motivoRechazo
                ) VALUES (
                    'uuid-1', 7, 1, '7790001', 48000, NULL, NULL, 0,
                    '2026-08-12T10:00:00Z', NULL, 'PENDIENTE', NULL
                )
                """.trimIndent(),
            )
        }

        val base = abrirMigrada(ruta)

        val guardado = base.conteoDao().todos().single()
        assertEquals(48000, guardado.cantidad)
        assertEquals("7790001", guardado.codigo)
        assertEquals(EstadoSync.PENDIENTE, guardado.estadoSync)
        base.close()
    }

    @Test
    fun `el maestro que ya estaba baja como articulo del maestro`() = runTest {
        // Los artículos que venían del maestro no son altas: si quedaran
        // marcados como pendientes, el celular intentaría crearlos de nuevo
        // en el servidor uno por uno.
        val ruta = crearBaseVieja("vieja-con-maestro.db") { vieja ->
            vieja.execSQL(
                "INSERT INTO articulo (id, idOrden, sku, descripcion, unidad, " +
                    "pasadaNumero, sesionId, busqueda) " +
                    "VALUES (7, 1, 'A-1', 'Fideos', 'UN', 1, 1, 'fideos a-1')",
            )
        }

        val base = abrirMigrada(ruta)

        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
        assertEquals("Fideos", base.maestroDao().porId(7)?.descripcion)
        base.close()
    }
}
