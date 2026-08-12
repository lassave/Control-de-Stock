package com.controldestock.datos

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
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
    version = 1,
    exportSchema = false,
)
@TypeConverters(ConversorDeEstado::class)
abstract class BaseLocal : RoomDatabase() {

    abstract fun vinculacionDao(): VinculacionDao
    abstract fun maestroDao(): MaestroDao
    abstract fun conteoDao(): ConteoDao

    companion object {
        @Volatile
        private var instancia: BaseLocal? = null

        fun de(contexto: Context): BaseLocal = instancia ?: synchronized(this) {
            instancia ?: Room.databaseBuilder(
                contexto.applicationContext,
                BaseLocal::class.java,
                "control-de-stock.db",
            ).build().also { instancia = it }
        }
    }
}
