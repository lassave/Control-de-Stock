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
    version = 4,
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
     * Un pendiente que quedó de una sesión cerrada se sincronizaría contra la
     * sesión abierta hoy: el servidor resuelve por «la» sesión abierta, así
     * que el conteo de ayer entraría al inventario de hoy sin que nada lo
     * señale. Y el maestro viejo mostraría artículos que ya no se cuentan.
     *
     * Revincular al mismo inventario —cambio de operario, o el token que se
     * renovó— conserva todo: ahí los pendientes siguen siendo válidos.
     *
     * El reparto se borra en un caso más: cambió el operario, aunque la
     * sesión sea la misma. Es suyo, no de la sesión, y dejarlo puesto le
     * mostraría a quien se vincula ahora el reparto de quien tenía el
     * celular antes.
     */
    suspend fun vincularA(vinculacion: VinculacionEntidad) = withTransaction {
        val anterior = vinculacionDao().actual()
        val cambioSesion = anterior != null && anterior.sesionId != vinculacion.sesionId
        val cambioOperario = anterior == null || anterior.operarioId != vinculacion.operarioId

        if (cambioSesion) {
            conteoDao().borrarTodos()
            maestroDao().borrarCodigos()
            // Vincularse a otro inventario deja el celular limpio, altas
            // pendientes incluidas: son de una sesión que este celular ya no
            // cuenta, y mandarlas contra la sesión abierta hoy metería
            // artículos inventados en el inventario de otro cliente.
            maestroDao().borrarTodosLosArticulos()
        }
        if (cambioSesion || cambioOperario) {
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

        fun de(contexto: Context): BaseLocal = instancia ?: synchronized(this) {
            instancia ?: Room.databaseBuilder(
                contexto.applicationContext,
                BaseLocal::class.java,
                "control-de-stock.db",
            )
                .addMigrations(MIGRACION_1_2, MIGRACION_2_3, MIGRACION_3_4)
                .build().also { instancia = it }
        }
    }
}
