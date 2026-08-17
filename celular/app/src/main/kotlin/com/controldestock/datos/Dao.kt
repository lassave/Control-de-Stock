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

    /**
     * Lo que destraba la etiqueta rota: el operario busca a mano, sin señal.
     *
     * Busca contra la columna ya plegada, no contra la descripción: el LIKE
     * de SQLite solo pliega mayúsculas en ASCII, así que «caño» no
     * encontraría «CAÑO galvanizado». Usá `buscarTexto`, que pliega la
     * consulta igual que la columna.
     */
    @Query(
        """
        SELECT * FROM articulo
        WHERE busqueda LIKE '%' || :plegado || '%'
        ORDER BY idOrden
        LIMIT 50
        """
    )
    suspend fun buscarPlegado(plegado: String): List<ArticuloEntidad>

    suspend fun buscar(texto: String): List<ArticuloEntidad> =
        buscarPlegado(plegar(texto))

    /**
     * Un código de barras del artículo, para poder contarlo.
     *
     * Hace falta porque el conteo viaja con el código y no con el id, y el
     * servidor resuelve solo por código. Sin esto, lo que el operario
     * encuentra desde «Buscar» no se puede cargar: usar el SKU falla justo
     * en los artículos que sí tienen un código de barras propio.
     */
    @Query("SELECT codigo FROM codigo WHERE articuloId = :articuloId LIMIT 1")
    suspend fun codigoDe(articuloId: Int): String?

    @Query("SELECT * FROM unidad WHERE codigo = :codigo")
    suspend fun unidad(codigo: String): UnidadEntidad?

    /** El catálogo entero, para que el alta rápida ofrezca dónde elegir. */
    @Query("SELECT * FROM unidad ORDER BY codigo")
    suspend fun unidades(): List<UnidadEntidad>

    @Query("SELECT * FROM articulo WHERE estadoAlta = 'PENDIENTE' ORDER BY id DESC")
    suspend fun altasPendientes(): List<ArticuloEntidad>

    @Query("UPDATE articulo SET estadoAlta = :estado, motivoRechazo = :motivo WHERE id = :id")
    suspend fun marcarAlta(id: Int, estado: String, motivo: String?)

    /**
     * El id del próximo artículo nacido en el celular: negativo.
     *
     * Los del servidor son positivos, así que ninguna alta local puede pisar
     * a un artículo del maestro cuando el maestro se vuelve a bajar.
     *
     * Mira solo los ids negativos: con el maestro bajado, el mínimo de todos
     * sería positivo y la primera alta nacería con un id que le pertenece al
     * servidor.
     *
     * Y mira las dos tablas, no alcanza con `articulo`: al reimportar el
     * maestro se van las altas que ya llegaron al servidor, pero sus conteos
     * se quedan. Mirando solo los artículos, ese id se daría por libre y la
     * próxima alta lo heredaría con los conteos del producto anterior
     * colgados: el aviso de repetido diría que ya se contó algo que nunca se
     * contó, y el producto nuevo quedaría sin contar.
     */
    @Query(
        """
        SELECT MIN(
            COALESCE((SELECT MIN(id) FROM articulo WHERE id < 0), 0),
            COALESCE((SELECT MIN(articuloId) FROM conteo WHERE articuloId < 0), 0)
        ) - 1
        """
    )
    suspend fun proximoIdLocal(): Int

    /** El artículo nuevo va al final del recorrido, nunca en el medio. */
    @Query("SELECT COALESCE(MAX(idOrden), 0) + 1 FROM articulo")
    suspend fun proximoOrden(): Int

    @Query(
        "SELECT ubicacion FROM articulo WHERE ubicacion IS NOT NULL "
            + "GROUP BY ubicacion ORDER BY ubicacion"
    )
    suspend fun ubicaciones(): List<String>

    /**
     * Los artículos de las ubicaciones asignadas al operario: la lista de
     * trabajo. El `JOIN` reemplaza al `IN (:lista)` dinámico y no tiene el
     * borde de una lista vacía.
     */
    @Query(
        """
        SELECT a.* FROM articulo a
        JOIN asignacion s ON s.ubicacion = a.ubicacion
        ORDER BY a.idOrden
        """
    )
    suspend fun deUbicacionesAsignadas(): List<ArticuloEntidad>

    /**
     * Los códigos de barra de esos mismos artículos, en el orden en que se
     * cargaron —por `rowid`, la tabla no tiene una columna de orden propia—.
     */
    @Query(
        """
        SELECT c.* FROM codigo c
        JOIN articulo a ON a.id = c.articuloId
        JOIN asignacion s ON s.ubicacion = a.ubicacion
        ORDER BY c.rowid
        """
    )
    suspend fun codigosDeUbicacionesAsignadas(): List<CodigoEntidad>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarArticulos(articulos: List<ArticuloEntidad>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarCodigos(codigos: List<CodigoEntidad>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertarUnidades(unidades: List<UnidadEntidad>)

    @Query("DELETE FROM articulo")
    suspend fun borrarTodosLosArticulos()

    @Query("DELETE FROM codigo WHERE articuloId NOT IN (SELECT id FROM articulo)")
    suspend fun borrarCodigosHuerfanos()

    /**
     * Borra el maestro salvo las altas que todavía no llegaron al servidor.
     *
     * Si se las llevara, quedarían conteos de un código que la base local ya
     * no conoce, y el servidor los rechaza para siempre por código
     * desconocido: el operario contó y el conteo se pierde.
     */
    @Query("DELETE FROM articulo WHERE estadoAlta IS NULL OR estadoAlta <> 'PENDIENTE'")
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
        borrarArticulos()
        borrarCodigosHuerfanos()
        insertarArticulos(articulos)
        insertarCodigos(codigos)
        insertarUnidades(unidades)
    }
}

@Dao
interface AsignacionDao {

    @Query("SELECT ubicacion FROM asignacion ORDER BY ubicacion")
    suspend fun todas(): List<String>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertar(asignaciones: List<AsignacionEntidad>)

    @Query("DELETE FROM asignacion")
    suspend fun borrar()

    /**
     * Reemplaza el reparto entero. Igual que `asignaciones.reemplazar` del
     * servidor: se borra antes de insertar, no se calcula una diferencia.
     */
    @Transaction
    suspend fun reemplazar(ubicaciones: List<String>) {
        borrar()
        insertar(ubicaciones.map { AsignacionEntidad(it) })
    }
}

@Dao
interface PasadaItemDao {

    @Query("SELECT articuloId FROM pasada_item")
    suspend fun todos(): List<Int>

    @Query("SELECT EXISTS(SELECT 1 FROM pasada_item WHERE articuloId = :articuloId)")
    suspend fun contiene(articuloId: Int): Boolean

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertar(items: List<PasadaItemEntidad>)

    @Query("DELETE FROM pasada_item")
    suspend fun borrar()

    /** Reemplaza el conjunto entero. Mismo patrón que `AsignacionDao.reemplazar`. */
    @Transaction
    suspend fun reemplazar(articuloIds: List<Int>) {
        borrar()
        insertar(articuloIds.map { PasadaItemEntidad(it) })
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

    /** Los conteos de un artículo, para saber si ya se contó en esa ubicación. */
    @Query("SELECT * FROM conteo WHERE articuloId = :articuloId ORDER BY rowid")
    suspend fun deArticulo(articuloId: Int): List<ConteoEntidad>

    @Query("DELETE FROM conteo")
    suspend fun borrarTodos()
}
