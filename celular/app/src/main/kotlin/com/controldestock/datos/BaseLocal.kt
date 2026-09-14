package com.controldestock.datos

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import androidx.room.migration.Migration
import androidx.room.withTransaction
import androidx.sqlite.db.SupportSQLiteDatabase
import com.controldestock.nucleo.EstadoSync

class ConversorDeEstado {
    @TypeConverter
    fun aTexto(estado: EstadoSync): String = estado.name

    @TypeConverter
    fun aEstado(texto: String): EstadoSync = EstadoSync.valueOf(texto)
}

@Database(
    entities = [
        VinculacionEntidad::class,
        ArticuloEntidad::class,
        CodigoEntidad::class,
        UnidadEntidad::class,
        ConteoEntidad::class,
        AsignacionEntidad::class,
        PasadaItemEntidad::class,
    ],
    version = 6,
    exportSchema = true,
)
@TypeConverters(ConversorDeEstado::class)
abstract class BaseLocal : RoomDatabase() {

    abstract fun vinculacionDao(): VinculacionDao
    abstract fun maestroDao(): MaestroDao
    abstract fun conteoDao(): ConteoDao
    abstract fun asignacionDao(): AsignacionDao
    abstract fun pasadaItemDao(): PasadaItemDao

    /**
     * Vincula el celular, limpiando lo del inventario anterior si cambió.
     *
     * Un pendiente que quedó de un proyecto cerrado se sincronizaría contra
     * el proyecto abierto hoy: el servidor resuelve por «el» proyecto
     * abierto, así que el conteo de ayer entraría al inventario de hoy sin
     * que nada lo señale. Y el maestro viejo mostraría artículos que ya no
     * se cuentan.
     *
     * Revincular al mismo inventario —cambio de operario, o el token que se
     * renovó— conserva todo: ahí los pendientes siguen siendo válidos.
     *
     * El reparto se borra en un caso más: cambió el operario, aunque el
     * proyecto sea el mismo. Es suyo, no del proyecto, y dejarlo puesto le
     * mostraría a quien se vincula ahora el reparto de quien tenía el
     * celular antes.
     */
    suspend fun vincularA(vinculacion: VinculacionEntidad) = withTransaction {
        val anterior = vinculacionDao().actual()
        val cambioProyecto = anterior != null && anterior.proyectoId != vinculacion.proyectoId
        val cambioOperario = anterior == null || anterior.operarioId != vinculacion.operarioId

        if (cambioProyecto) {
            conteoDao().borrarTodos()
            maestroDao().borrarCodigos()
            // Vincularse a otro inventario deja el celular limpio, altas
            // pendientes incluidas: son de un proyecto que este celular ya no
            // cuenta, y mandarlas contra el proyecto abierto hoy metería
            // artículos inventados en el inventario de otro cliente.
            maestroDao().borrarTodosLosArticulos()
        }
        if (cambioProyecto || cambioOperario) {
            asignacionDao().borrar()
        }
        vinculacionDao().guardar(vinculacion)
    }

    companion object {
        @Volatile
        private var instancia: BaseLocal? = null

        /**
         * Agrega las dos columnas del alta rápida sin tocar nada más.
         *
         * Nada de empezar de cero: un operario que actualiza la app en medio
         * de un inventario perdería los conteos que todavía no subió, que es
         * justo lo que la base local existe para proteger.
         */
        val MIGRACION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE articulo ADD COLUMN estadoAlta TEXT")
                db.execSQL("ALTER TABLE articulo ADD COLUMN motivoRechazo TEXT")
            }
        }

        /**
         * Agrega la tabla del reparto. El `CREATE TABLE` es una copia literal
         * del `createSql` que Room escribió en
         * `app/schemas/com.controldestock.datos.BaseLocal/3.json`: Room
         * compara la estructura al abrir, y una diferencia de comillas o de
         * orden alcanza para que se niegue a abrir una base migrada.
         */
        val MIGRACION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `asignacion` (`ubicacion` TEXT NOT NULL, " +
                        "PRIMARY KEY(`ubicacion`))"
                )
            }
        }

        /**
         * Agrega el bloqueo por recuento: si la pasada activa es parcial, y
         * a qué pasada pertenece cada conteo. El `CREATE TABLE` de
         * `pasada_item` y las columnas nuevas son copia literal de
         * `app/schemas/com.controldestock.datos.BaseLocal/4.json`, por el
         * mismo motivo que `MIGRACION_2_3`.
         */
        val MIGRACION_3_4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE vinculacion ADD COLUMN esParcial INTEGER NOT NULL DEFAULT 0")
                db.execSQL("ALTER TABLE conteo ADD COLUMN pasadaId INTEGER NOT NULL DEFAULT 0")
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `pasada_item` (`articuloId` INTEGER NOT NULL, " +
                        "PRIMARY KEY(`articuloId`))"
                )
            }
        }

        /**
         * Renombra `sesionId` a `proyectoId` en las tres tablas que lo tienen.
         *
         * `ALTER TABLE ... RENAME COLUMN` recién es confiable desde SQLite
         * 3.25, y el `minSdk` 26 de esta app puede correr con una versión más
         * vieja: se recrea cada tabla entera, copiando los datos, en vez de
         * arriesgarse a que el rename falle en silencio en un celular viejo.
         * El `CREATE TABLE` de cada una es copia literal del `createSql` de
         * `app/schemas/com.controldestock.datos.BaseLocal/5.json`, con
         * `sesionId` ya renombrada, por el mismo motivo que `MIGRACION_2_3`.
         */
        val MIGRACION_4_5 = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE `vinculacion_new` (`id` INTEGER NOT NULL, `url` TEXT NOT NULL, " +
                        "`token` TEXT NOT NULL, `operarioId` INTEGER NOT NULL, " +
                        "`operarioNombre` TEXT NOT NULL, `proyectoId` INTEGER NOT NULL, " +
                        "`pasadaId` INTEGER NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
                        "`pasadaEtiqueta` TEXT NOT NULL, `esParcial` INTEGER NOT NULL, " +
                        "PRIMARY KEY(`id`))"
                )
                db.execSQL(
                    "INSERT INTO vinculacion_new (id, url, token, operarioId, operarioNombre, " +
                        "proyectoId, pasadaId, pasadaNumero, pasadaEtiqueta, esParcial) " +
                        "SELECT id, url, token, operarioId, operarioNombre, sesionId, pasadaId, " +
                        "pasadaNumero, pasadaEtiqueta, esParcial FROM vinculacion"
                )
                db.execSQL("DROP TABLE vinculacion")
                db.execSQL("ALTER TABLE vinculacion_new RENAME TO vinculacion")

                db.execSQL(
                    "CREATE TABLE `articulo_new` (`id` INTEGER NOT NULL, `idOrden` INTEGER NOT NULL, " +
                        "`tipo` TEXT, `material` TEXT, `sku` TEXT NOT NULL, " +
                        "`descripcion` TEXT NOT NULL, `grupo` TEXT, `ubicacion` TEXT, " +
                        "`unidad` TEXT NOT NULL, `pasadaNumero` INTEGER NOT NULL, " +
                        "`proyectoId` INTEGER NOT NULL, `busqueda` TEXT NOT NULL, " +
                        "`estadoAlta` TEXT, `motivoRechazo` TEXT, PRIMARY KEY(`id`))"
                )
                db.execSQL(
                    "INSERT INTO articulo_new (id, idOrden, tipo, material, sku, descripcion, " +
                        "grupo, ubicacion, unidad, pasadaNumero, proyectoId, busqueda, " +
                        "estadoAlta, motivoRechazo) " +
                        "SELECT id, idOrden, tipo, material, sku, descripcion, grupo, ubicacion, " +
                        "unidad, pasadaNumero, sesionId, busqueda, estadoAlta, motivoRechazo " +
                        "FROM articulo"
                )
                db.execSQL("DROP TABLE articulo")
                db.execSQL("ALTER TABLE articulo_new RENAME TO articulo")

                db.execSQL(
                    "CREATE TABLE `conteo_new` (`uuid` TEXT NOT NULL, `articuloId` INTEGER NOT NULL, " +
                        "`proyectoId` INTEGER NOT NULL, `codigo` TEXT NOT NULL, " +
                        "`cantidad` INTEGER NOT NULL, `ubicacionReal` TEXT, `observaciones` TEXT, " +
                        "`fueraAsignacion` INTEGER NOT NULL, `pasadaId` INTEGER NOT NULL, " +
                        "`timestampDispositivo` TEXT NOT NULL, `anulaUuid` TEXT, " +
                        "`estadoSync` TEXT NOT NULL, `motivoRechazo` TEXT, PRIMARY KEY(`uuid`))"
                )
                db.execSQL(
                    "INSERT INTO conteo_new (uuid, articuloId, proyectoId, codigo, cantidad, " +
                        "ubicacionReal, observaciones, fueraAsignacion, pasadaId, " +
                        "timestampDispositivo, anulaUuid, estadoSync, motivoRechazo) " +
                        "SELECT uuid, articuloId, sesionId, codigo, cantidad, ubicacionReal, " +
                        "observaciones, fueraAsignacion, pasadaId, timestampDispositivo, " +
                        "anulaUuid, estadoSync, motivoRechazo FROM conteo"
                )
                db.execSQL("DROP TABLE conteo")
                db.execSQL("ALTER TABLE conteo_new RENAME TO conteo")
            }
        }

        /**
         * Agrega `origen`, para poder marcar en el celular los artículos
         * nacidos de una alta rápida. Solo una columna, como `MIGRACION_1_2`:
         * no hace falta recrear ninguna tabla.
         */
        val MIGRACION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "ALTER TABLE articulo ADD COLUMN origen TEXT NOT NULL DEFAULT 'importado'"
                )
            }
        }

        fun de(contexto: Context): BaseLocal = instancia ?: synchronized(this) {
            instancia ?: Room.databaseBuilder(
                contexto.applicationContext,
                BaseLocal::class.java,
                "control-de-stock.db",
            )
                .addMigrations(
                    MIGRACION_1_2, MIGRACION_2_3, MIGRACION_3_4, MIGRACION_4_5, MIGRACION_5_6,
                )
                .build().also { instancia = it }
        }
    }
}
