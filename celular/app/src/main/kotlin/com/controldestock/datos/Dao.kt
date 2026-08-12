package com.controldestock.datos

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.controldestock.nucleo.EstadoSync

@Dao
interface VinculacionDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun guardar(vinculacion: VinculacionEntidad)

    @Query("SELECT * FROM vinculacion WHERE id = 1")
    suspend fun actual(): VinculacionEntidad?

    @Query("DELETE FROM vinculacion")
    suspend fun borrar()
}

@Dao
interface MaestroDao {

    @Query("SELECT * FROM articulo ORDER BY idOrden")
    suspend fun articulos(): List<ArticuloEntidad>

    @Query(
        """
        SELECT a.* FROM articulo a
        JOIN codigo c ON c.articuloId = a.id
        WHERE c.codigo = :codigo
        LIMIT 1
        """
    )
    suspend fun porCodigo(codigo: String): ArticuloEntidad?

    @Query("SELECT * FROM articulo WHERE id = :id")
    suspend fun porId(id: Int): ArticuloEntidad?

    /** Lo que destraba la etiqueta rota: el operario busca a mano, sin señal. */
    @Query(
        """
        SELECT * FROM articulo
        WHERE descripcion LIKE '%' || :texto || '%' COLLATE NOCASE
           OR sku LIKE '%' || :texto || '%' COLLATE NOCASE
           OR ubicacion LIKE '%' || :texto || '%' COLLATE NOCASE
        ORDER BY idOrden
        LIMIT 50
        """
    )
    suspend fun buscar(texto: String): List<ArticuloEntidad>

    @Query("SELECT * FROM unidad WHERE codigo = :codigo")
    suspend fun unidad(codigo: String): UnidadEntidad?

    @Query(
        "SELECT ubicacion FROM articulo WHERE ubicacion IS NOT NULL "
            + "GROUP BY ubicacion ORDER BY ubicacion"
    )
    suspend fun ubicaciones(): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarArticulos(articulos: List<ArticuloEntidad>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarCodigos(codigos: List<CodigoEntidad>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarUnidades(unidades: List<UnidadEntidad>)

    @Query("DELETE FROM articulo")
    suspend fun borrarArticulos()

    @Query("DELETE FROM codigo")
    suspend fun borrarCodigos()

    /**
     * Reemplaza el maestro entero.
     *
     * Se borra antes de insertar: al reimportar, un artículo que ya no está
     * no puede seguir apareciendo en la búsqueda del operario. Va en una
     * transacción para que un maestro a medio reemplazar no exista nunca.
     */
    @Transaction
    suspend fun reemplazarMaestro(
        articulos: List<ArticuloEntidad>,
        codigos: List<CodigoEntidad>,
        unidades: List<UnidadEntidad>,
    ) {
        borrarCodigos()
        borrarArticulos()
        insertarArticulos(articulos)
        insertarCodigos(codigos)
        insertarUnidades(unidades)
    }
}

@Dao
interface ConteoDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun guardar(conteo: ConteoEntidad)

    @Query("SELECT * FROM conteo ORDER BY timestampDispositivo DESC, rowid DESC")
    suspend fun todos(): List<ConteoEntidad>

    // Sin valor por defecto en el parámetro: Room no los admite en los
    // métodos de un DAO.
    @Query("SELECT * FROM conteo WHERE estadoSync = :estado ORDER BY rowid")
    suspend fun porEstado(estado: EstadoSync): List<ConteoEntidad>

    @Query("SELECT COUNT(*) FROM conteo WHERE estadoSync = 'PENDIENTE'")
    suspend fun cantidadPendientes(): Int

    @Query("UPDATE conteo SET estadoSync = :estado, motivoRechazo = :motivo WHERE uuid = :uuid")
    suspend fun marcar(uuid: String, estado: EstadoSync, motivo: String? = null)

    @Query("SELECT * FROM conteo WHERE uuid = :uuid")
    suspend fun porUuid(uuid: String): ConteoEntidad?
}
