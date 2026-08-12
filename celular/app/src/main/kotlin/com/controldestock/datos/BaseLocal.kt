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
    ],
    version = 2,
    exportSchema = true,
)
@TypeConverters(ConversorDeEstado::class)
abstract class BaseLocal : RoomDatabase() {

    abstract fun vinculacionDao(): VinculacionDao
    abstract fun maestroDao(): MaestroDao
    abstract fun conteoDao(): ConteoDao

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
     */
    suspend fun vincularA(vinculacion: VinculacionEntidad) = withTransaction {
        val anterior = vinculacionDao().actual()
        if (anterior != null && anterior.sesionId != vinculacion.sesionId) {
            conteoDao().borrarTodos()
            maestroDao().borrarCodigos()
            // Vincularse a otro inventario deja el celular limpio, altas
            // pendientes incluidas: son de una sesión que este celular ya no
            // cuenta, y mandarlas contra la sesión abierta hoy metería
            // artículos inventados en el inventario de otro cliente.
            maestroDao().borrarTodosLosArticulos()
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

        fun de(contexto: Context): BaseLocal = instancia ?: synchronized(this) {
            instancia ?: Room.databaseBuilder(
                contexto.applicationContext,
                BaseLocal::class.java,
                "control-de-stock.db",
            )
                .addMigrations(MIGRACION_1_2)
                .build().also { instancia = it }
        }
    }
}
