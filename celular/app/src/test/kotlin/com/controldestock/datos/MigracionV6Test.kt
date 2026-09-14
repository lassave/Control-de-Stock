package com.controldestock.datos

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

// Copiado de app/schemas/com.controldestock.datos.BaseLocal/5.json.
private val ESQUEMA_V5 = listOf(
    "CREATE TABLE IF NOT EXISTS `vinculacion` (`id` INTEGER NOT NULL, " +
        "`url` TEXT NOT NULL, `token` TEXT NOT NULL, `operarioId` INTEGER NOT NULL, " +
        "`operarioNombre` TEXT NOT NULL, `proyectoId` INTEGER NOT NULL, " +
        "`pasadaId` INTEGER NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`pasadaEtiqueta` TEXT NOT NULL, `esParcial` INTEGER NOT NULL, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `articulo` (`id` INTEGER NOT NULL, " +
        "`idOrden` INTEGER NOT NULL, `tipo` TEXT, `material` TEXT, `sku` TEXT NOT NULL, " +
        "`descripcion` TEXT NOT NULL, `grupo` TEXT, `ubicacion` TEXT, " +
        "`unidad` TEXT NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
        "`proyectoId` INTEGER NOT NULL, `busqueda` TEXT NOT NULL, `estadoAlta` TEXT, " +
        "`motivoRechazo` TEXT, PRIMARY KEY(`id`))",
    "CREATE TABLE IF NOT EXISTS `codigo` (`codigo` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, PRIMARY KEY(`codigo`, `articuloId`))",
    "CREATE INDEX IF NOT EXISTS `index_codigo_codigo` ON `codigo` (`codigo`)",
    "CREATE TABLE IF NOT EXISTS `unidad` (`codigo` TEXT NOT NULL, " +
        "`nombre` TEXT NOT NULL, `admiteDecimales` INTEGER NOT NULL, PRIMARY KEY(`codigo`))",
    "CREATE TABLE IF NOT EXISTS `conteo` (`uuid` TEXT NOT NULL, " +
        "`articuloId` INTEGER NOT NULL, `proyectoId` INTEGER NOT NULL, " +
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

// El `identityHash` del 5.json: sin esta fila la base migrada no parece de
// la versión 5 sino una base ajena, y Room se niega a migrarla.
private const val HASH_V5 = "4ad94ce4a218f3192dcf463daa38f371"

@RunWith(RobolectricTestRunner::class)
class MigracionV6Test {

    private val contexto = ApplicationProvider.getApplicationContext<Context>()

    private fun crearBaseVieja(nombre: String, poblar: (SQLiteDatabase) -> Unit): String {
        val archivo = contexto.getDatabasePath(nombre)
        archivo.parentFile?.mkdirs()
        archivo.delete()

        val vieja = SQLiteDatabase.openOrCreateDatabase(archivo, null)
        ESQUEMA_V5.forEach(vieja::execSQL)
        vieja.execSQL(
            "CREATE TABLE IF NOT EXISTS room_master_table " +
                "(id INTEGER PRIMARY KEY, identity_hash TEXT)",
        )
        vieja.execSQL(
            "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
            arrayOf(HASH_V5),
        )
        poblar(vieja)
        vieja.version = 5
        vieja.close()

        return archivo.absolutePath
    }

    private fun abrirMigrada(ruta: String): BaseLocal =
        Room.databaseBuilder(contexto, BaseLocal::class.java, ruta)
            .addMigrations(BaseLocal.MIGRACION_5_6)
            .build()

    @Test
    fun `un articulo viejo migra con origen importado`() = runTest {
        val ruta = crearBaseVieja("v5-con-articulo.db") { vieja ->
            vieja.execSQL(
                "INSERT INTO articulo (id, idOrden, sku, descripcion, unidad, " +
                    "pasadaNumero, proyectoId, busqueda) " +
                    "VALUES (7, 1, 'A-1', 'Fideos', 'UN', 1, 3, 'fideos a-1')",
            )
        }

        val base = abrirMigrada(ruta)

        val articulo = base.maestroDao().porId(7)
        assertEquals("importado", articulo?.origen)
        base.close()
    }
}
