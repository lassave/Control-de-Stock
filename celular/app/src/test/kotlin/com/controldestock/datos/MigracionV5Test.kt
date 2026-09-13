package com.controldestock.datos

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

// Copiado de app/schemas/com.controldestock.datos.BaseLocal/4.json.
private val ESQUEMA_V4 = listOf(
    "CREATE TABLE IF NOT EXISTS `vinculacion` (`id` INTEGER NOT NULL, " +
        "`url` TEXT NOT NULL, `token` TEXT NOT NULL, `operarioId` INTEGER NOT NULL, " +
        "`operarioNombre` TEXT NOT NULL, `sesionId` INTEGER NOT NULL, " +
        "`pasadaId` INTEGER NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`pasadaEtiqueta` TEXT NOT NULL, `esParcial` INTEGER NOT NULL, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `articulo` (`id` INTEGER NOT NULL, " +
        "`idOrden` INTEGER NOT NULL, `tipo` TEXT, `material` TEXT, `sku` TEXT NOT NULL, " +
        "`descripcion` TEXT NOT NULL, `grupo` TEXT, `ubicacion` TEXT, " +
        "`unidad` TEXT NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`sesionId` INTEGER NOT NULL, `busqueda` TEXT NOT NULL, `estadoAlta` TEXT, " +
        "`motivoRechazo` TEXT, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `codigo` (`codigo` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, PRIMARY KEY(`codigo`, `articuloId`))",
    "CREATE INDEX IF NOT EXISTS `index_codigo_codigo` ON `codigo` (`codigo`)",
    "CREATE TABLE IF NOT EXISTS `unidad` (`codigo` TEXT NOT NULL, " +
        "`nombre` TEXT NOT NULL, `admiteDecimales` INTEGER NOT NULL, PRIMARY KEY(`codigo`))",
    "CREATE TABLE IF NOT EXISTS `conteo` (`uuid` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, `sesionId` INTEGER NOT NULL, " +
        "`codigo` TEXT NOT NULL, `cantidad` INTEGER NOT NULL, `ubicacionReal` TEXT, " +
        "`observaciones` TEXT, `fueraAsignacion` INTEGER NOT NULL, " +
        "`pasadaId` INTEGER NOT NULL, `timestampDispositivo` TEXT NOT NULL, " +
        "`anulaUuid` TEXT, `estadoSync` TEXT NOT NULL, `motivoRechazo` TEXT, " +
        "PRIMARY KEY(`uuid`))",
    "CREATE TABLE IF NOT EXISTS `asignacion` (`ubicacion` TEXT NOT NULL, " +
        "PRIMARY KEY(`ubicacion`))",
    "CREATE TABLE IF NOT EXISTS `pasada_item` (`articuloId` INTEGER NOT NULL, " +
        "PRIMARY KEY(`articuloId`))",
)

// El `identityHash` del 4.json: sin esta fila la base migrada no parece de
// la versión 4 sino una base ajena, y Room se niega a migrarla.
private const val HASH_V4 = "6eef08481621655c3438ae4cc6049b78"

@RunWith(RobolectricTestRunner::class)
class MigracionV5Test {

    private val contexto = ApplicationProvider.getApplicationContext<Context>()

    private fun crearBaseVieja(nombre: String, poblar: (SQLiteDatabase) -> Unit): String {
        val archivo = contexto.getDatabasePath(nombre)
        archivo.parentFile?.mkdirs()
        archivo.delete()

        val vieja = SQLiteDatabase.openOrCreateDatabase(archivo, null)
        ESQUEMA_V4.forEach(vieja::execSQL)
        vieja.execSQL(
            "CREATE TABLE IF NOT EXISTS room_master_table " +
                "(id INTEGER PRIMARY KEY, identity_hash TEXT)",
        )
        vieja.execSQL(
            "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
            arrayOf(HASH_V4),
        )
        poblar(vieja)
        vieja.version = 4
        vieja.close()

        return archivo.absolutePath
    }

    private fun abrirMigrada(ruta: String): BaseLocal =
        Room.databaseBuilder(contexto, BaseLocal::class.java, ruta)
            .addMigrations(BaseLocal.MIGRACION_4_5)
            .build()

    @Test
    fun `la vinculacion sobrevive a la migracion con proyectoId`() = runTest {
        val ruta = crearBaseVieja("v4-con-vinculacion.db") { vieja ->
            vieja.execSQL(
                "INSERT INTO vinculacion (id, url, token, operarioId, operarioNombre, " +
                    "sesionId, pasadaId, pasadaNumero, pasadaEtiqueta, esParcial) VALUES " +
                    "(1, 'http://172.16.11.12:8000', 'abc', 1, 'Juan', 7, 1, 1, 'Conteo 1', 0)",
            )
        }

        val base = abrirMigrada(ruta)

        val vinculacion = base.vinculacionDao().actual()
        assertEquals("Juan", vinculacion?.operarioNombre)
        assertEquals(7, vinculacion?.proyectoId)
        base.close()
    }

    @Test
    fun `el maestro sobrevive a la migracion con proyectoId`() = runTest {
        val ruta = crearBaseVieja("v4-con-maestro.db") { vieja ->
            vieja.execSQL(
                "INSERT INTO articulo (id, idOrden, sku, descripcion, unidad, " +
                    "pasadaNumero, sesionId, busqueda) " +
                    "VALUES (7, 1, 'A-1', 'Fideos', 'UN', 1, 3, 'fideos a-1')",
            )
        }

        val base = abrirMigrada(ruta)

        val articulo = base.maestroDao().porId(7)
        assertEquals("Fideos", articulo?.descripcion)
        assertEquals(3, articulo?.proyectoId)
        base.close()
    }

    @Test
    fun `los conteos sin subir sobreviven a la migracion con proyectoId`() = runTest {
        val ruta = crearBaseVieja("v4-con-conteos.db") { vieja ->
            vieja.execSQL(
                """
                INSERT INTO conteo (
                    uuid, articuloId, sesionId, codigo, cantidad, ubicacionReal,
                    observaciones, fueraAsignacion, pasadaId, timestampDispositivo,
                    anulaUuid, estadoSync, motivoRechazo
                ) VALUES (
                    'uuid-1', 7, 5, '7790001', 48000, NULL, NULL, 0, 0,
                    '2026-08-17T10:00:00Z', NULL, 'PENDIENTE', NULL
                )
                """.trimIndent(),
            )
        }

        val base = abrirMigrada(ruta)

        val guardado = base.conteoDao().todos().single()
        assertEquals(48000, guardado.cantidad)
        assertEquals(5, guardado.proyectoId)
        base.close()
    }

    @Test
    fun `la tabla de pasada_item no se toca y sigue vacia`() = runTest {
        val ruta = crearBaseVieja("v4-sin-recuento.db") {}

        val base = abrirMigrada(ruta)

        assertTrue(base.pasadaItemDao().todos().isEmpty())
        base.close()
    }
}
