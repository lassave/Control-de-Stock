# Alta rápida y aviso de repetido — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** que el operario pueda dar de alta desde el celular un código
que no está en el maestro —con o sin señal— y que la app le avise cuando
está por cargar dos veces el mismo producto en la misma ubicación.

**Arquitectura:** el alta crea el artículo en la base del celular con un id
provisional negativo y lo deja `PENDIENTE`; el sincronizador manda las altas
antes que los conteos, porque el servidor rechaza para siempre un conteo
cuyo código no conoce. El aviso de repetido es una función pura del núcleo
que la ficha consulta al confirmar, sin tocar la red.

**Herramientas:** Kotlin, Jetpack Compose, Room, OkHttp, JUnit4, Robolectric,
MockWebServer, Compose UI Test.

**Especificaciones:**
- `docs/superpowers/specs/2026-08-12-alta-rapida-en-el-celular-design.md`
- `docs/superpowers/specs/2026-08-12-aviso-de-repetido-en-la-misma-ubicacion-design.md`

## Global Constraints

- **Cantidades en milésimas, siempre `Int`.** `24 UN` es `24000`; `3,5 kg` es
  `3500`.
- **`stock_sistema` y `costo_unitario` nunca salen por `/api/dispositivo/*`.**
  El conteo es a ciegas.
- **Fechas ISO 8601 UTC como texto** (`2026-08-12T14:32:05Z`). La única
  fuente es `nucleo/Reloj.kt`. La hora local solo existe para mostrarse.
- **Nada se edita ni se borra.** Una corrección es una anulación.
- **Textos en castellano rioplatense**, sin jerga técnica, también en los
  errores.
- **Mensajes de commit en castellano, en presente, describiendo el efecto**;
  el cuerpo explica *por qué*, no *qué*.
- **TDD sin excepciones**: test que falla, implementación, test que pasa,
  commit.
- **El id del artículo local es negativo y no se persigue.** El conteo viaja
  con el código de barras, nunca con el id.

## Entorno

El `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta
nada: siempre el intérprete del venv por ruta.

```powershell
# Tests del celular
cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon

# Tests del servidor (no deberían tocarse en este plan)
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor

# APK y celular
cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:assembleDebug --no-daemon
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
```

## Lo que ya existe y se consume

- `ClienteServidor.altaRapida(codigo, descripcion, unidad, ubicacion): RespuestaAlta`
  — ya implementado y probado. `RespuestaAlta` trae `creado: Boolean`.
- `ErrorDeServidor(mensaje, reintentable)` — `reintentable = false` es un
  rechazo definitivo (400, 401, 409); `true` es sin conexión o error 5xx.
- `PlanDeSincronizacion.aEnviar / anulacionesSinDestino / aplicar` — lógica
  pura de sincronización.
- `ReglasDeCarga.validar(texto, admiteDecimales)` — devuelve `Valida`,
  `PideConfirmacion` o `Invalida`.
- `Cantidades.aTexto(milesimas)` — `3500` → `"3,5"`.
- `Contador.buscar / registrar / ubicaciones`.
- `AvisoSonoro.leido / desconocido / error / cargado`.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `nucleo/…/Repeticion.kt` *(nuevo)* | Decidir si ese artículo ya se contó en esa ubicación. Puro. |
| `nucleo/…/Reloj.kt` | Suma `horaLocal(instante)`, para mostrar. |
| `nucleo/…/PlanDeSincronizacion.kt` | Suma qué conteos espera un alta y cuáles cierra un alta rechazada. |
| `app/…/datos/Entidades.kt` | `ArticuloEntidad` suma `estadoAlta` y `motivoRechazo`. |
| `app/…/datos/Dao.kt` | Consultas del alta y de los conteos de un artículo. |
| `app/…/datos/BaseLocal.kt` | Versión 2 y la migración. |
| `app/…/Contador.kt` | Suma `darDeAlta` y `conteosDe`. |
| `app/…/Sincronizador.kt` | Manda las altas antes que los conteos. |
| `app/…/ui/ControlesDeCarga.kt` *(nuevo)* | Teclado numérico y selector de ubicación, compartidos. |
| `app/…/ui/FichaDeAlta.kt` *(nuevo)* | La pantalla del alta. |
| `app/…/ui/FichaDelArticulo.kt` | Usa los controles compartidos y pregunta por el repetido. |
| `app/…/ui/PantallaEscaneo.kt` | El botón «Darlo de alta» en la franja. |
| `app/…/MainActivity.kt` | Cablea todo. |

---

### Task 1: La base guarda las altas y sobrevive a la actualización

**Files:**
- Modify: `celular/app/build.gradle.kts`
- Modify: `celular/app/src/main/kotlin/com/controldestock/datos/Entidades.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/datos/Dao.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt`
- Create: `celular/app/src/test/kotlin/com/controldestock/datos/MigracionTest.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/datos/BaseLocalTest.kt`

**Interfaces:**
- Produces:
  - `ArticuloEntidad.estadoAlta: String?` y `.motivoRechazo: String?`
  - `ArticuloEntidad.esAltaPendiente: Boolean` (extensión)
  - `MaestroDao.unidades(): List<UnidadEntidad>`
  - `MaestroDao.altasPendientes(): List<ArticuloEntidad>`
  - `MaestroDao.marcarAlta(id: Int, estado: String, motivo: String?)`
  - `MaestroDao.proximoIdLocal(): Int` — negativo
  - `MaestroDao.proximoOrden(): Int`
  - `MaestroDao.borrarTodosLosArticulos()`
  - `ConteoDao.deArticulo(articuloId: Int): List<ConteoEntidad>`
  - `BaseLocal.MIGRACION_1_2`

- [ ] **Step 1: Guardar el esquema de la versión 1 antes de tocar nada**

Room puede exportar el esquema de la base a un JSON. Hace falta el de la
versión **actual** para escribir el test de migración con el DDL exacto: si
el test crea una base vieja distinta de la que Room espera, falla por el
motivo equivocado.

En `celular/app/build.gradle.kts`, **al nivel de arriba** —fuera de
`android { }`, junto a `dependencies { }`— agregar:

```kotlin
// Room escribe acá el esquema de cada versión de la base. Van al repo: son
// la referencia de cómo era antes de cada migración, y sin ellos una
// migración solo se puede probar a ojo.
ksp {
    arg("room.schemaLocation", "$projectDir/schemas")
}
```

En `BaseLocal.kt`, cambiar `exportSchema = false` por `exportSchema = true`
**sin tocar la versión todavía**.

- [ ] **Step 2: Generar el esquema y verlo**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:kspDebugKotlin --no-daemon`
Expected: aparece `celular/app/schemas/com.controldestock.datos.BaseLocal/1.json`

Abrirlo y anotar dos cosas, que se usan en el paso siguiente:
- el valor de `identityHash`
- el `createSql` de cada tabla (`vinculacion`, `articulo`, `codigo`,
  `unidad`, `conteo`) y el de los índices

- [ ] **Step 3: Commitear el esquema de la versión 1**

```bash
git add celular/app/build.gradle.kts celular/app/src/main/kotlin/com/controldestock/datos/BaseLocal.kt celular/app/schemas
git commit -m "Guarda el esquema de la base del celular en el repo

Sin el esquema de cada version, una migracion solo se puede probar a ojo:
no hay con que construir la base vieja para verificar que lo que el
operario todavia no subio sigue ahi despues de actualizar."
```

- [ ] **Step 4: Escribir el test de migración**

Crear `celular/app/src/test/kotlin/com/controldestock/datos/MigracionTest.kt`.

**Reemplazar** las constantes `ESQUEMA_V1` y `HASH_V1` por lo que dice el
`1.json` del Step 2. El DDL de abajo es el que Room genera para estas
entidades, pero el archivo manda: una diferencia de una coma hace que Room
rechace la base con un mensaje larguísimo sobre columnas esperadas.

```kotlin
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
private const val HASH_V1 = "reemplazar por el identityHash del 1.json"

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
            .addMigrations(BaseLocal.MIGRACION_1_2)
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
```

- [ ] **Step 5: Correr el test y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.datos.MigracionTest" --no-daemon`
Expected: FAIL con `Unresolved reference: MIGRACION_1_2` y `altasPendientes`

- [ ] **Step 6: Agregar las columnas a `ArticuloEntidad`**

En `Entidades.kt`, dentro de `ArticuloEntidad`, después de `busqueda`:

```kotlin
    // Vacío si el artículo vino del maestro. Si nació acá, por un alta
    // rápida, en qué anda esa alta contra el servidor: PENDIENTE, ENVIADO o
    // RECHAZADO.
    //
    // Es texto y no el enum: la columna admite nulo, y el conversor de
    // EstadoSync es para columnas obligatorias. Room no admite dos
    // conversores para el mismo tipo.
    val estadoAlta: String? = null,
    // Por qué el servidor no la aceptó, para poder mostrárselo al operario.
    val motivoRechazo: String? = null,
```

Y al final del archivo:

```kotlin
/** Un artículo que nació en el celular y todavía no existe en el servidor. */
val ArticuloEntidad.esAltaPendiente: Boolean
    get() = estadoAlta == EstadoSync.PENDIENTE.name
```

- [ ] **Step 7: Escribir la migración y subir la versión**

En `BaseLocal.kt`:

```kotlin
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
```

Cambiar `version = 1` por `version = 2`, y dentro de `companion object`:

```kotlin
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
```

Y en el builder de `de(contexto)`, antes de `.build()`:

```kotlin
                .addMigrations(MIGRACION_1_2)
```

- [ ] **Step 8: Agregar las consultas a los DAO**

En `Dao.kt`, dentro de `MaestroDao`:

```kotlin
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
     */
    @Query("SELECT COALESCE(MIN(id), 0) - 1 FROM articulo")
    suspend fun proximoIdLocal(): Int

    /** El artículo nuevo va al final del recorrido, nunca en el medio. */
    @Query("SELECT COALESCE(MAX(idOrden), 0) + 1 FROM articulo")
    suspend fun proximoOrden(): Int

    @Query("DELETE FROM articulo")
    suspend fun borrarTodosLosArticulos()

    @Query("DELETE FROM codigo WHERE articuloId NOT IN (SELECT id FROM articulo)")
    suspend fun borrarCodigosHuerfanos()
```

Reemplazar `borrarArticulos` por una versión que respete lo pendiente:

```kotlin
    /**
     * Borra el maestro salvo las altas que todavía no llegaron al servidor.
     *
     * Si se las llevara, quedarían conteos de un código que la base local ya
     * no conoce, y el servidor los rechaza para siempre por código
     * desconocido: el operario contó y el conteo se pierde.
     */
    @Query("DELETE FROM articulo WHERE estadoAlta IS NULL OR estadoAlta <> 'PENDIENTE'")
    suspend fun borrarArticulos()
```

Y cambiar el cuerpo de `reemplazarMaestro` para que no borre los códigos de
lo que sobrevive:

```kotlin
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
```

En `ConteoDao`:

```kotlin
    /** Los conteos de un artículo, para saber si ya se contó en esa ubicación. */
    @Query("SELECT * FROM conteo WHERE articuloId = :articuloId ORDER BY rowid")
    suspend fun deArticulo(articuloId: Int): List<ConteoEntidad>
```

- [ ] **Step 9: Arreglar el borrado al cambiar de inventario**

En `BaseLocal.vincularA`, cambiar `maestroDao().borrarArticulos()` por
`maestroDao().borrarTodosLosArticulos()`.

Vincularse a **otro** inventario tiene que dejar el celular limpio, altas
pendientes incluidas: son de una sesión que este celular ya no cuenta, y
mandarlas contra la sesión abierta hoy metería artículos inventados en el
inventario de otro cliente.

- [ ] **Step 10: Escribir los tests de las consultas nuevas**

Agregar a `BaseLocalTest.kt` (usa el `base` en memoria que el archivo ya
arma; si los nombres de los ayudantes difieren, seguir los del archivo):

```kotlin
    @Test
    fun `reemplazar el maestro conserva el alta que no subio`() = runTest {
        // Si se la llevara, el conteo que ya cargó el operario quedaría
        // apuntando a un código que la base no conoce, y el servidor lo
        // rechaza para siempre.
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = "7790999", descripcion = "Pack por 6",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Pack por 6", "7790999", null),
                    estadoAlta = EstadoSync.PENDIENTE.name,
                ),
            ),
        )
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad("7790999", -1)))

        base.maestroDao().reemplazarMaestro(
            articulos = listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", null),
                ),
            ),
            codigos = listOf(CodigoEntidad("7790001", 1)),
            unidades = listOf(UnidadEntidad("UN", "Unidad", 0)),
        )

        assertEquals("Pack por 6", base.maestroDao().porCodigo("7790999")?.descripcion)
        assertEquals(1, base.maestroDao().altasPendientes().size)
    }

    @Test
    fun `reemplazar el maestro se lleva el alta que ya subio`() = runTest {
        // Esa ya existe del otro lado: si se quedara, el maestro nuevo la
        // traería otra vez con su id de verdad y el operario vería el mismo
        // producto dos veces.
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = "7790999", descripcion = "Pack por 6",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Pack por 6", "7790999", null),
                    estadoAlta = EstadoSync.ENVIADO.name,
                ),
            ),
        )

        base.maestroDao().reemplazarMaestro(emptyList(), emptyList(), emptyList())

        assertNull(base.maestroDao().porId(-1))
    }

    @Test
    fun `vincularse a otro inventario no deja ni las altas pendientes`() = runTest {
        base.vinculacionDao().guardar(unaVinculacion(sesionId = 1))
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = "7790999", descripcion = "Pack por 6",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Pack por 6", "7790999", null),
                    estadoAlta = EstadoSync.PENDIENTE.name,
                ),
            ),
        )

        base.vincularA(unaVinculacion(sesionId = 2))

        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
    }

    @Test
    fun `el id del articulo local es negativo y no pisa al maestro`() = runTest {
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = 1, idOrden = 1, sku = "A-1", descripcion = "Fideos",
                    unidad = "UN", pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda("Fideos", "A-1", null),
                ),
            ),
        )

        assertEquals(-1, base.maestroDao().proximoIdLocal())
        assertEquals(2, base.maestroDao().proximoOrden())
    }
```

`unaVinculacion(sesionId)` es un ayudante: si `BaseLocalTest` ya tiene uno
equivalente, usar ese; si no, agregarlo:

```kotlin
    private fun unaVinculacion(sesionId: Int) = VinculacionEntidad(
        url = "http://172.16.11.12:8000", token = "abc",
        operarioId = 1, operarioNombre = "Juan", sesionId = sesionId,
        pasadaId = 1, pasadaNumero = 1, pasadaEtiqueta = "Conteo 1",
    )
```

- [ ] **Step 11: Correr toda la suite del celular**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS. Se regeneró `app/schemas/…/2.json`.

Si Room se queja de que el esquema esperado no coincide, comparar su mensaje
con el `2.json` recién generado: la diferencia está siempre en el DDL de la
tabla `articulo` del test.

- [ ] **Step 12: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/datos celular/app/src/test/kotlin/com/controldestock/datos celular/app/schemas
git commit -m "Guarda en el celular los articulos dados de alta

El articulo nace en el celular con un id negativo y queda pendiente de
crearse en el servidor. Los ids del servidor son positivos, asi que un alta
local nunca pisa a un articulo del maestro cuando el maestro se vuelve a
bajar.

Al reemplazar el maestro se conservan las altas que todavia no subieron. Si
se las llevara, quedarian conteos de un codigo que la base local ya no
conoce, y el servidor los rechaza para siempre por codigo desconocido: el
operario conto y el conteo se pierde.

La base sube a la version 2 con una migracion que solo agrega columnas.
Empezar de cero le borraria a un operario los conteos sin subir en medio del
inventario, que es justo lo que la base local existe para proteger."
```

---

### Task 2: El aviso de repetido, la parte que se prueba sin celular

**Files:**
- Create: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/Repeticion.kt`
- Create: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/RepeticionTest.kt`
- Modify: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/Reloj.kt`
- Test: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/RelojTest.kt`

**Interfaces:**
- Consumes: `ConteoLocal`, `EventoConteo`, `EstadoSync`
- Produces:
  - `Repeticion.buscar(previos, ubicacionDelArticulo, ubicacionElegida): Repeticion.YaContado?`
  - `Repeticion.YaContado(milesimas: Int, cuando: String)`
  - `horaLocal(instante: String, zona: ZoneId = ZoneId.systemDefault()): String`

- [ ] **Step 1: Escribir el test de la repetición**

Crear `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/RepeticionTest.kt`:

```kotlin
package com.controldestock.nucleo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RepeticionTest {

    private fun conteo(
        cantidad: Int,
        ubicacionReal: String? = null,
        estado: EstadoSync = EstadoSync.PENDIENTE,
        cuando: String = "2026-08-12T13:32:00Z",
        anula: String? = null,
    ) = ConteoLocal(
        EventoConteo(
            uuid = "uuid-$cantidad-$cuando",
            codigo = "7790001",
            cantidad = cantidad,
            timestampDispositivo = cuando,
            ubicacionReal = ubicacionReal,
            anulaUuid = anula,
        ),
        estado,
    )

    @Test
    fun `avisa cuando ya se conto ese articulo en esa ubicacion`() {
        val repetido = Repeticion.buscar(listOf(conteo(24000)), "P-1", null)

        assertEquals(Repeticion.YaContado(24000, "2026-08-12T13:32:00Z"), repetido)
    }

    @Test
    fun `no avisa cuando el conteo anterior fue en otra ubicacion`() {
        // El mismo producto sí puede estar en dos estantes: ahí los conteos
        // suman y preguntar sería estorbar.
        val repetido = Repeticion.buscar(listOf(conteo(24000, ubicacionReal = "P-9")), "P-1", null)

        assertNull(repetido)
    }

    @Test
    fun `no avisa cuando el operario corrige la ubicacion del nuevo conteo`() {
        val repetido = Repeticion.buscar(listOf(conteo(24000)), "P-1", "P-9")

        assertNull(repetido)
    }

    @Test
    fun `sin ubicacion tambien se repite consigo misma`() {
        // Un artículo sin ubicación en el maestro se cuenta igual, y contarlo
        // dos veces es el mismo error.
        val repetido = Repeticion.buscar(listOf(conteo(24000)), null, null)

        assertEquals(24000, repetido?.milesimas)
    }

    @Test
    fun `un conteo rechazado no cuenta como ya contado`() {
        // El servidor no lo aceptó: nunca entró al inventario, así que
        // frenar al operario por él sería frenarlo por algo que no existe.
        val repetido = Repeticion.buscar(
            listOf(conteo(24000, estado = EstadoSync.RECHAZADO)), "P-1", null,
        )

        assertNull(repetido)
    }

    @Test
    fun `una anulacion no cuenta como ya contado`() {
        // Una anulación no es un conteo: es su baja.
        val repetido = Repeticion.buscar(
            listOf(conteo(0, anula = "uuid-original")), "P-1", null,
        )

        assertNull(repetido)
    }

    @Test
    fun `avisa con el ultimo conteo, que es el que el operario recuerda`() {
        val repetido = Repeticion.buscar(
            listOf(
                conteo(10000, cuando = "2026-08-12T13:00:00Z"),
                conteo(24000, cuando = "2026-08-12T13:32:00Z"),
            ),
            "P-1", null,
        )

        assertEquals(24000, repetido?.milesimas)
    }

    @Test
    fun `sin conteos previos no avisa nada`() {
        assertNull(Repeticion.buscar(emptyList(), "P-1", null))
    }
}
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: Repeticion`

- [ ] **Step 3: Implementar `Repeticion.kt`**

```kotlin
package com.controldestock.nucleo

/**
 * Si ese artículo ya se contó en esa misma ubicación.
 *
 * Un SKU se cuenta una sola vez por ubicación: todo lo que hay de ese
 * producto en ese estante se cuenta junto y se carga junto. Un segundo
 * escaneo en el mismo lugar no es un estante nuevo, es que el operario
 * perdió la cuenta, y si entra callado el inventario termina con unidades de
 * más que nadie va a poder explicar.
 *
 * Entre ubicaciones distintas no avisa: el mismo producto sí puede estar en
 * dos estantes, y ahí los conteos suman.
 *
 * Es lógica pura a propósito: la pantalla la consulta al confirmar, sin
 * tocar la red ni esperar a nadie.
 */
object Repeticion {

    data class YaContado(
        val milesimas: Int,
        /** Cuándo se cargó, en UTC. Se muestra en hora local. */
        val cuando: String,
    )

    /**
     * @param previos los conteos de ese mismo artículo en este celular.
     * @param ubicacionDelArticulo la que trae el maestro.
     * @param ubicacionElegida la que el operario corrigió, si corrigió alguna.
     */
    fun buscar(
        previos: List<ConteoLocal>,
        ubicacionDelArticulo: String?,
        ubicacionElegida: String?,
    ): YaContado? {
        val donde = ubicacionElegida ?: ubicacionDelArticulo

        return previos
            .filter { it.estadoSync != EstadoSync.RECHAZADO }
            .filter { it.evento.anulaUuid == null }
            .lastOrNull { (it.evento.ubicacionReal ?: ubicacionDelArticulo) == donde }
            ?.let { YaContado(it.evento.cantidad, it.evento.timestampDispositivo) }
    }
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 8 tests nuevos

- [ ] **Step 5: Escribir el test de la hora local**

Agregar a `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/RelojTest.kt`:

```kotlin
    @Test
    fun `la hora que ve el operario es la del deposito`() {
        // Todo se guarda en UTC. Mostrarlo tal cual, en Argentina, diría tres
        // horas menos: el operario leería que lo cargó otro, o que fue otro
        // día.
        val texto = horaLocal("2026-08-12T13:32:05Z", ZoneId.of("America/Argentina/Buenos_Aires"))

        assertEquals("10:32", texto)
    }

    @Test
    fun `la hora se muestra con dos digitos`() {
        // «9:05» y «09:05» se leen distinto de reojo, que es como se lee en
        // el depósito.
        val texto = horaLocal("2026-08-12T12:05:00Z", ZoneId.of("America/Argentina/Buenos_Aires"))

        assertEquals("09:05", texto)
    }
```

Con los imports `java.time.ZoneId` y `org.junit.Assert.assertEquals` si no
están.

- [ ] **Step 6: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: horaLocal`

- [ ] **Step 7: Implementar `horaLocal` en `Reloj.kt`**

Al final de `Reloj.kt`, fuera de las clases:

```kotlin
private val SOLO_LA_HORA = DateTimeFormatter.ofPattern("HH:mm")

/**
 * La hora del día en la zona del depósito, para mostrarla.
 *
 * Vive junto al reloj porque es su contraparte: el reloj es la única fuente
 * del formato con el que se guarda, y esta la única del formato con el que
 * se lee. Todo se guarda en UTC; mostrarlo así, en Argentina, diría tres
 * horas menos.
 */
fun horaLocal(instante: String, zona: ZoneId = ZoneId.systemDefault()): String =
    Instant.parse(instante).atZone(zona).format(SOLO_LA_HORA)
```

Con los imports `java.time.Instant` y `java.time.ZoneId`.

- [ ] **Step 8: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add celular/nucleo
git commit -m "Sabe si un articulo ya se conto en esa ubicacion

Un SKU se cuenta una sola vez por ubicacion: todo lo que hay de ese producto
en ese estante se cuenta junto. Un segundo escaneo en el mismo lugar no es
un estante nuevo, es que el operario perdio la cuenta, y si entra callado el
inventario termina con unidades de mas que nadie puede explicar.

Entre ubicaciones distintas no avisa: el mismo producto si puede estar en
dos estantes, y ahi los conteos suman.

Un conteo rechazado no cuenta: el servidor no lo acepto, nunca entro al
inventario, y frenar al operario por el seria frenarlo por algo que no
existe.

La hora se muestra en la zona del deposito. Mostrar el UTC crudo, en
Argentina, diria tres horas menos: el operario leeria que lo cargo otro."
```

---

### Task 3: El alta se guarda en el celular

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/Contador.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt`

**Interfaces:**
- Consumes: `MaestroDao.proximoIdLocal / proximoOrden`, `ArticuloEntidad.estadoAlta`
- Produces:
  - `Contador.darDeAlta(codigo, descripcion, unidad, ubicacion, milesimas, observaciones): ArticuloEntidad`
  - `Contador.conteosDe(articulo): List<ConteoLocal>`
  - `Contador.unidades(): List<UnidadEntidad>`

- [ ] **Step 1: Escribir los tests del alta**

Agregar a `ContadorTest.kt`:

```kotlin
    @Test
    fun `el alta deja el articulo, su codigo y su primer conteo`() = runTest {
        val articulo = contador().darDeAlta(
            codigo = "7790999", descripcion = "Pack por 6", unidad = "UN",
            ubicacion = "P-3", milesimas = 6000, observaciones = null,
        )

        assertEquals("Pack por 6", base.maestroDao().porCodigo("7790999")?.descripcion)
        val conteo = base.conteoDao().todos().single()
        assertEquals("7790999", conteo.codigo)
        assertEquals(6000, conteo.cantidad)
        assertEquals(articulo.id, conteo.articuloId)
    }

    @Test
    fun `el articulo dado de alta queda pendiente de crearse en el servidor`() = runTest {
        contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        val pendiente = base.maestroDao().altasPendientes().single()
        assertEquals("Pack por 6", pendiente.descripcion)
        assertEquals(EstadoSync.PENDIENTE.name, pendiente.estadoAlta)
    }

    @Test
    fun `el id del articulo dado de alta no pisa a ninguno del maestro`() = runTest {
        // Los del servidor son positivos. Sin esto, bajar el maestro de nuevo
        // reemplazaría el artículo nuevo por otro con el mismo número.
        val articulo = contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        assertTrue("el id tiene que ser negativo: ${articulo.id}", articulo.id < 0)
    }

    @Test
    fun `el segundo escaneo del producto recien dado de alta ya lo encuentra`() = runTest {
        // Es lo que hace que en una estantería de packs iguales el operario
        // escriba la descripción una sola vez.
        contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        val hallazgo = contador().buscar("7790999")

        assertTrue(hallazgo is Hallazgo.Encontrado)
        assertEquals("Pack por 6", (hallazgo as Hallazgo.Encontrado).articulo.descripcion)
    }

    @Test
    fun `el alta respeta la unidad elegida y si admite decimales`() = runTest {
        contador().darDeAlta("7790999", "Harina suelta", "KG", null, 3500, null)

        val hallazgo = contador().buscar("7790999") as Hallazgo.Encontrado

        assertEquals("KG", hallazgo.articulo.unidad)
        assertEquals(true, hallazgo.admiteDecimales)
    }

    @Test
    fun `el alta queda atada a la sesion y a la pasada del celular`() = runTest {
        base.vinculacionDao().guardar(
            VinculacionEntidad(
                url = "http://172.16.11.12:8000", token = "abc",
                operarioId = 1, operarioNombre = "Juan", sesionId = 7,
                pasadaId = 3, pasadaNumero = 2, pasadaEtiqueta = "Conteo 2",
            ),
        )

        val articulo = contador().darDeAlta("7790999", "Pack por 6", "UN", null, 6000, null)

        assertEquals(7, articulo.sesionId)
        assertEquals(2, articulo.pasadaNumero)
        assertEquals(7, base.conteoDao().todos().single().sesionId)
    }

    @Test
    fun `los conteos de un articulo se pueden leer para avisar de repetidos`() = runTest {
        val articulo = (contador().buscar("7790001") as Hallazgo.Encontrado).articulo
        contador().registrar(articulo, 24000, null, null)

        val previos = contador().conteosDe(articulo)

        assertEquals(1, previos.size)
        assertEquals(24000, previos.single().evento.cantidad)
    }
```

Agregar los imports que falten: `com.controldestock.datos.VinculacionEntidad`
y `com.controldestock.nucleo.EstadoSync` (este último ya está).

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ContadorTest" --no-daemon`
Expected: FAIL con `Unresolved reference: darDeAlta`

- [ ] **Step 3: Implementar `darDeAlta` y `conteosDe`**

En `Contador.kt`, agregar los imports:

```kotlin
import androidx.room.withTransaction
import com.controldestock.datos.CodigoEntidad
import com.controldestock.datos.UnidadEntidad
import com.controldestock.datos.textoDeBusqueda
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.EstadoSync
```

Y dentro de la clase:

```kotlin
    /** El catálogo de unidades, para que el alta ofrezca dónde elegir. */
    suspend fun unidades(): List<UnidadEntidad> = base.maestroDao().unidades()

    /** Los conteos que este celular ya hizo de ese artículo. */
    suspend fun conteosDe(articulo: ArticuloEntidad): List<ConteoLocal> =
        base.conteoDao().deArticulo(articulo.id).map { it.aLocal() }

    /**
     * Da de alta un código que no está en el maestro, con su primer conteo.
     *
     * El artículo nace acá, con un id provisional, y queda pendiente de
     * crearse en el servidor. Que exista en la base local es lo que hace que
     * el segundo escaneo del mismo pack muestre su ficha en vez de volver a
     * decir «desconocido»: en una estantería de packs iguales eso se repite
     * diez veces seguidas.
     *
     * Va todo en una transacción: un artículo sin su código no se puede
     * contar nunca más, y un conteo sin su artículo lo rechaza el servidor
     * para siempre.
     */
    suspend fun darDeAlta(
        codigo: String,
        descripcion: String,
        unidad: String,
        ubicacion: String?,
        milesimas: Int,
        observaciones: String?,
    ): ArticuloEntidad = base.withTransaction {
        val vinculacion = base.vinculacionDao().actual()

        val articulo = ArticuloEntidad(
            id = base.maestroDao().proximoIdLocal(),
            idOrden = base.maestroDao().proximoOrden(),
            // El servidor usa el código escaneado como SKU de las altas
            // rápidas: el celular hace lo mismo para que las dos filas se
            // parezcan mientras el alta no subió.
            sku = codigo,
            descripcion = descripcion,
            ubicacion = ubicacion,
            unidad = unidad,
            pasadaNumero = vinculacion?.pasadaNumero ?: 1,
            sesionId = vinculacion?.sesionId ?: 0,
            busqueda = textoDeBusqueda(descripcion, codigo, ubicacion),
            estadoAlta = EstadoSync.PENDIENTE.name,
        )

        base.maestroDao().insertarArticulos(listOf(articulo))
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad(codigo, articulo.id)))

        // La ubicación del alta es la del artículo, así que el conteo no
        // lleva corrección: corregir sería corregirse a sí mismo.
        registrar(articulo, milesimas, null, observaciones)

        articulo
    }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ContadorTest" --no-daemon`
Expected: PASS, 7 tests nuevos

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/Contador.kt celular/app/src/test/kotlin/com/controldestock/ContadorTest.kt
git commit -m "Da de alta un codigo desconocido con su primer conteo

El articulo nace en la base del celular y queda pendiente de crearse en el
servidor. Que exista localmente es lo que hace que el segundo escaneo del
mismo pack muestre su ficha en vez de volver a decir desconocido: en una
estanteria de packs iguales eso se repite diez veces seguidas, y el operario
escribiria la descripcion diez veces.

Va todo en una transaccion: un articulo sin su codigo no se puede contar
nunca mas, y un conteo sin su articulo lo rechaza el servidor para siempre."
```

---

### Task 4: Las altas suben antes que los conteos

**Files:**
- Modify: `celular/nucleo/src/main/kotlin/com/controldestock/nucleo/PlanDeSincronizacion.kt`
- Test: `celular/nucleo/src/test/kotlin/com/controldestock/nucleo/PlanDeSincronizacionTest.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/Sincronizador.kt`
- Test: `celular/app/src/test/kotlin/com/controldestock/SincronizadorTest.kt`

**Interfaces:**
- Consumes: `MaestroDao.altasPendientes / marcarAlta / codigoDe`,
  `ClienteServidor.altaRapida`, `ErrorDeServidor.reintentable`
- Produces:
  - `PlanDeSincronizacion.aEnviar(locales, codigosSinArticulo: Set<String> = emptySet())`
  - `PlanDeSincronizacion.cerradosPorAltaRechazada(locales, codigo, motivo): List<ConteoLocal>`
  - `ResultadoDeSync.yaExistian: List<String>` — las descripciones que el
    servidor ya tenía para un código recién dado de alta

- [ ] **Step 1: Escribir los tests de la lógica pura**

Agregar a `PlanDeSincronizacionTest.kt` (usar los ayudantes que el archivo ya
tiene para armar `ConteoLocal`; si se llaman distinto, seguir los del
archivo):

```kotlin
    @Test
    fun `un conteo cuyo articulo no existe todavia en el servidor espera`() {
        // Mandarlo antes que su alta es tirarlo: el servidor rechaza para
        // siempre un conteo cuyo codigo no conoce.
        val locales = listOf(
            ConteoLocal(EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z")),
            ConteoLocal(EventoConteo("uuid-2", "7790001", 1000, "2026-08-12T10:01:00Z")),
        )

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, setOf("7790999"))

        assertEquals(listOf("uuid-2"), aEnviar.map { it.uuid })
    }

    @Test
    fun `un alta trabada no frena a los conteos de los demas articulos`() {
        // El operario conto cincuenta articulos del maestro y uno nuevo: los
        // cincuenta no tienen por que esperar al que falta.
        val locales = (1..3).map {
            ConteoLocal(EventoConteo("uuid-$it", "779000$it", 1000, "2026-08-12T10:0$it:00Z"))
        }

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, setOf("7790999"))

        assertEquals(3, aEnviar.size)
    }

    @Test
    fun `los conteos de un alta rechazada para siempre se cierran con su motivo`() {
        val locales = listOf(
            ConteoLocal(EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z")),
            ConteoLocal(EventoConteo("uuid-2", "7790001", 1000, "2026-08-12T10:01:00Z")),
        )

        val cerrados = PlanDeSincronizacion.cerradosPorAltaRechazada(
            locales, "7790999", "La unidad «XX» no está en el catálogo",
        )

        assertEquals(1, cerrados.size)
        assertEquals("uuid-1", cerrados.single().evento.uuid)
        assertEquals(EstadoSync.RECHAZADO, cerrados.single().estadoSync)
        assertEquals(
            "La unidad «XX» no está en el catálogo",
            cerrados.single().motivoRechazo,
        )
    }

    @Test
    fun `cerrar los conteos de un alta rechazada no toca a los que ya subieron`() {
        val locales = listOf(
            ConteoLocal(
                EventoConteo("uuid-1", "7790999", 6000, "2026-08-12T10:00:00Z"),
                EstadoSync.ENVIADO,
            ),
        )

        val cerrados = PlanDeSincronizacion.cerradosPorAltaRechazada(locales, "7790999", "no")

        assertEquals(emptyList<ConteoLocal>(), cerrados)
    }
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: FAIL con `Unresolved reference: cerradosPorAltaRechazada` y por la
cantidad de parámetros de `aEnviar`

- [ ] **Step 3: Implementar en `PlanDeSincronizacion`**

Cambiar la firma de `aEnviar` y agregar el filtro nuevo, sin tocar lo demás:

```kotlin
    /**
     * Los pendientes, en el orden en que se cargaron.
     *
     * Se descarta la anulación de un conteo que el servidor nunca aceptó
     * (ver abajo) y se retiene lo que depende de un alta que todavía no
     * llegó: mandar un conteo antes que su artículo es tirarlo, porque el
     * servidor rechaza para siempre un código que no conoce.
     */
    fun aEnviar(
        locales: List<ConteoLocal>,
        codigosSinArticulo: Set<String> = emptySet(),
    ): List<EventoConteo> {
        val nuncaLlegaron = locales
            .filter { it.estadoSync == EstadoSync.RECHAZADO }
            .map { it.evento.uuid }
            .toSet()

        return locales
            .filter { it.estadoSync == EstadoSync.PENDIENTE }
            .filterNot { it.evento.anulaUuid in nuncaLlegaron }
            .filterNot { it.evento.codigo in codigosSinArticulo }
            .map { it.evento }
    }

    /**
     * Los conteos que hay que cerrar porque su alta no va a entrar nunca.
     *
     * Si el servidor rechazó el artículo para siempre —una unidad que no está
     * en su catálogo, el inventario cerrado— sus conteos no tienen a dónde
     * llegar. Dejarlos pendientes deja la cola girando para siempre, quema
     * batería y red, y el indicador de «sin subir» pasa a mentir.
     */
    fun cerradosPorAltaRechazada(
        locales: List<ConteoLocal>,
        codigo: String,
        motivo: String,
    ): List<ConteoLocal> = locales
        .filter { it.estadoSync == EstadoSync.PENDIENTE }
        .filter { it.evento.codigo == codigo }
        .map { it.copy(estadoSync = EstadoSync.RECHAZADO, motivoRechazo = motivo) }
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon`
Expected: PASS, 4 tests nuevos y los 13 de antes intactos

- [ ] **Step 5: Escribir los tests del sincronizador**

Agregar a `SincronizadorTest.kt`. El ayudante `guardarAlta` deja un artículo
pendiente con su código, igual que `Contador.darDeAlta`:

```kotlin
    private suspend fun guardarAlta(
        codigo: String = "7790999",
        descripcion: String = "Pack por 6",
        unidad: String = "UN",
    ) {
        base.maestroDao().insertarArticulos(
            listOf(
                ArticuloEntidad(
                    id = -1, idOrden = 99, sku = codigo, descripcion = descripcion,
                    unidad = unidad, pasadaNumero = 1, sesionId = 1,
                    busqueda = textoDeBusqueda(descripcion, codigo, null),
                    estadoAlta = EstadoSync.PENDIENTE.name,
                ),
            ),
        )
        base.maestroDao().insertarCodigos(listOf(CodigoEntidad(codigo, -1)))
        base.conteoDao().guardar(
            ConteoEntidad.de(EventoConteo.nuevo(codigo, 6000, reloj), -1, 1),
        )
    }

    @Test
    fun `el articulo dado de alta sube antes que su conteo`() = runTest {
        // Al reves el conteo se pierde: el servidor rechaza para siempre un
        // codigo que no conoce.
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Pack por 6","unidad":"UN","creado":true}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        sincronizador().sincronizar()

        assertEquals("/api/dispositivo/articulos", servidor.takeRequest().path)
        assertEquals("/api/dispositivo/conteos", servidor.takeRequest().path)
        assertEquals(0, base.conteoDao().cantidadPendientes())
        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
    }

    @Test
    fun `sin red el alta y su conteo siguen esperando`() = runTest {
        guardarAlta()
        servidor.shutdown()

        val resultado = sincronizador().sincronizar()

        assertTrue(resultado.huboError)
        assertEquals(1, base.conteoDao().cantidadPendientes())
        assertEquals(1, base.maestroDao().altasPendientes().size)
    }

    @Test
    fun `un alta rechazada para siempre cierra sus conteos`() = runTest {
        // Sin esto la cola nunca se vacia: el articulo no va a existir jamas,
        // asi que sus conteos se reintentarian para siempre.
        guardarAlta(unidad = "XX")
        responder("""{"detail":"La unidad «XX» no está en el catálogo"}""", codigo = 400)

        sincronizador().sincronizar()

        assertEquals(0, base.conteoDao().cantidadPendientes())
        val conteo = base.conteoDao().todos().single()
        assertEquals(EstadoSync.RECHAZADO, conteo.estadoSync)
        assertEquals("La unidad «XX» no está en el catálogo", conteo.motivoRechazo)
        assertEquals(
            "La unidad «XX» no está en el catálogo",
            base.maestroDao().porId(-1)?.motivoRechazo,
        )
    }

    @Test
    fun `un codigo que ya existia no es un error`() = runTest {
        // Otro operario lo dio de alta hace un minuto, o coincide con el SKU
        // de uno del maestro: el conteo entra igual contra ese articulo.
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Tornillo","unidad":"UN","creado":false}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(1, resultado.enviados)
        assertEquals(emptyList<ArticuloEntidad>(), base.maestroDao().altasPendientes())
    }

    @Test
    fun `cuando el codigo ya existia se reporta con que nombre`() = runTest {
        // Para poder decirle al operario «ese codigo ya era: Tornillo». Sin
        // eso escribio una descripcion que se descarto y nunca se entera.
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Tornillo","unidad":"UN","creado":false}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(listOf("Tornillo"), resultado.yaExistian)
    }

    @Test
    fun `un alta nueva no reporta ningun nombre`() = runTest {
        guardarAlta()
        responder("""{"id":9,"id_orden":84,"sku":"7790999","descripcion":"Pack por 6","unidad":"UN","creado":true}""")
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        val resultado = sincronizador().sincronizar()

        assertEquals(emptyList<String>(), resultado.yaExistian)
    }

    @Test
    fun `un alta trabada no frena a los conteos de los demas articulos`() = runTest {
        // El operario conto cincuenta del maestro y uno nuevo: los cincuenta
        // no esperan al que falta.
        guardarAlta()
        guardarPendiente()
        responder("""{"detail":"algo pasajero"}""", codigo = 500)
        responder("""{"registrados":1,"duplicados":0,"rechazados":[]}""")

        sincronizador().sincronizar()

        assertEquals(1, base.conteoDao().cantidadPendientes())
        assertEquals(1, base.maestroDao().altasPendientes().size)
    }
```

Agregar los imports que falten: `com.controldestock.datos.ArticuloEntidad`,
`com.controldestock.datos.textoDeBusqueda`.

- [ ] **Step 6: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.SincronizadorTest" --no-daemon`
Expected: FAIL — hoy el sincronizador no pide `/api/dispositivo/articulos`,
así que el primer `takeRequest()` devuelve el de conteos

- [ ] **Step 7: Implementar el orden en `Sincronizador`**

`ResultadoDeSync` suma un campo:

```kotlin
data class ResultadoDeSync(
    val enviados: Int = 0,
    val rechazados: Int = 0,
    val huboError: Boolean = false,
    /**
     * Los códigos que el servidor ya conocía, con el nombre que tenía.
     *
     * El operario escribió una descripción que se descarta —manda la del
     * servidor— así que si sigue mirando hay que decírselo: «ese código ya
     * era: Tornillo». Sin esto se entera recién cuando baja el maestro, o
     * nunca.
     */
    val yaExistian: List<String> = emptyList(),
)
```

Reemplazar el cuerpo de `sincronizar()` por:

```kotlin
    suspend fun sincronizar(): ResultadoDeSync {
        val vinculacion = base.vinculacionDao().actual() ?: return ResultadoDeSync()
        val cliente = crearCliente(vinculacion.url, vinculacion.token)

        // Primero los artículos que nacieron en el celular: un conteo cuyo
        // código el servidor no conoce se rechaza para siempre, no se
        // reintenta. Mandarlo antes que su artículo es tirarlo.
        val altas = subirAltas(cliente)

        val locales = base.conteoDao().todos().map { it.aLocal() }

        // Las anulaciones de conteos que el servidor nunca aceptó se cierran
        // acá: mandarlas deja la cola girando para siempre.
        PlanDeSincronizacion.anulacionesSinDestino(locales).forEach {
            base.conteoDao().marcar(it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo)
        }

        val aEnviar = PlanDeSincronizacion.aEnviar(locales, altas.codigos)
        if (aEnviar.isEmpty()) {
            return ResultadoDeSync(
                huboError = altas.huboError,
                yaExistian = altas.yaExistian,
            )
        }

        return try {
            val respuesta = cliente.enviarConteos(aEnviar)
            val resueltos = PlanDeSincronizacion.aplicar(aEnviar, respuesta)

            resueltos.forEach {
                base.conteoDao().marcar(it.evento.uuid, it.estadoSync, it.motivoRechazo)
            }

            ResultadoDeSync(
                enviados = resueltos.count { it.estadoSync == EstadoSync.ENVIADO },
                rechazados = resueltos.count { it.estadoSync == EstadoSync.RECHAZADO },
                huboError = altas.huboError,
                yaExistian = altas.yaExistian,
            )
        } catch (error: ErrorDeServidor) {
            // Lo pendiente sigue pendiente. No se toca nada.
            ResultadoDeSync(huboError = true, yaExistian = altas.yaExistian)
        }
    }

    /** Cómo quedaron las altas: qué se trabó y qué código ya existía. */
    private data class Altas(
        val codigos: Set<String> = emptySet(),
        val huboError: Boolean = false,
        val yaExistian: List<String> = emptyList(),
    )

    private suspend fun subirAltas(cliente: ClienteServidor): Altas {
        val codigos = mutableSetOf<String>()
        val yaExistian = mutableListOf<String>()
        var huboError = false

        for (alta in base.maestroDao().altasPendientes()) {
            val codigo = base.maestroDao().codigoDe(alta.id) ?: alta.sku

            try {
                // La respuesta trae `creado`, que distingue el alta nueva de
                // la que ya existía. Las dos son buenas noticias: en las dos,
                // el código ya identifica a un artículo y sus conteos pueden
                // entrar. La diferencia es que en la segunda el operario
                // escribió una descripción que se descarta, y merece
                // enterarse.
                val respuesta =
                    cliente.altaRapida(codigo, alta.descripcion, alta.unidad, alta.ubicacion)
                if (!respuesta.creado) yaExistian += respuesta.descripcion
                base.maestroDao().marcarAlta(alta.id, EstadoSync.ENVIADO.name, null)
            } catch (error: ErrorDeServidor) {
                if (error.reintentable) {
                    // Se cayó la red o el servidor tosió: el alta sigue
                    // pendiente y sus conteos esperan con ella.
                    huboError = true
                    codigos += codigo
                } else {
                    val motivo = error.message.orEmpty()
                    base.maestroDao().marcarAlta(alta.id, EstadoSync.RECHAZADO.name, motivo)

                    // Ese artículo no va a existir nunca: sus conteos no
                    // tienen a dónde llegar, y dejarlos pendientes deja la
                    // cola girando para siempre.
                    val locales = base.conteoDao().todos().map { it.aLocal() }
                    PlanDeSincronizacion
                        .cerradosPorAltaRechazada(locales, codigo, motivo)
                        .forEach {
                            base.conteoDao().marcar(
                                it.evento.uuid, EstadoSync.RECHAZADO, it.motivoRechazo,
                            )
                        }
                }
            }
        }

        return Altas(codigos, huboError, yaExistian)
    }
```

- [ ] **Step 8: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.SincronizadorTest" --no-daemon`
Expected: PASS, 5 tests nuevos y los 7 de antes intactos

- [ ] **Step 9: Correr toda la suite**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add celular/nucleo celular/app/src/main/kotlin/com/controldestock/Sincronizador.kt celular/app/src/test/kotlin/com/controldestock/SincronizadorTest.kt
git commit -m "Sube los articulos dados de alta antes que sus conteos

El servidor rechaza para siempre un conteo cuyo codigo no conoce: mandarlo
antes que su articulo es tirarlo. Por eso el orden es parte del diseno y no
un detalle.

Un alta que no pudo subir retiene solo a los conteos de su propio codigo. El
operario conto cincuenta articulos del maestro y uno nuevo: los cincuenta no
tienen por que esperar al que falta.

Un alta rechazada para siempre cierra sus conteos con el mismo motivo. Ese
articulo no va a existir nunca, y dejarlos pendientes deja la cola girando,
quema bateria y hace que el indicador de sin subir mienta."
```

---

### Task 5: Los controles compartidos y el aviso de repetido en la ficha

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/ControlesDeCarga.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/FichaDelArticulo.kt`
- Test: `celular/app/src/testDebug/kotlin/com/controldestock/ui/FichaDelArticuloTest.kt`

**Interfaces:**
- Consumes: `Repeticion.buscar`, `horaLocal`, `Cantidades.aTexto`, `ConteoLocal`
- Produces:
  - `TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit)` — público
  - `ElegirUbicacion(ubicaciones, alElegir, alCerrar)` — público
  - `FichaDelArticulo(articulo, admiteDecimales, ubicaciones, previos, alCancelar, alConfirmar)`

- [ ] **Step 1: Escribir el test del aviso**

Agregar a `FichaDelArticuloTest.kt`. Ojo: «Cancelar» aparece dos veces
—el botón de la ficha y el del cartel— así que el del cartel se toma con
`onLast()`.

```kotlin
    private val yaContado = listOf(
        ConteoLocal(
            EventoConteo(
                uuid = "uuid-1", codigo = "7790001", cantidad = 24000,
                timestampDispositivo = "2026-08-12T13:32:00Z",
            ),
        ),
    )

    private fun abrirFichaConteada() {
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos,
                admiteDecimales = false,
                ubicaciones = listOf("P-1", "P-9"),
                previos = yaContado,
                alCancelar = {},
                alConfirmar = { _, _, _ -> },
            )
        }
    }

    @Test
    fun `avisa cuando ese producto ya se conto en esa ubicacion`() {
        // Un SKU se cuenta una sola vez por ubicación: el segundo escaneo en
        // el mismo estante es que el operario perdió la cuenta.
        abrirFichaConteada()
        teclear("6")

        tocar("Confirmar")

        compose.onNodeWithText("¿Ya lo contaste acá?").assertExists()
    }

    @Test
    fun `el aviso dice cuanto y cuando se cargo`() {
        abrirFichaConteada()
        teclear("6")

        tocar("Confirmar")

        compose.onNodeWithText("Ya cargaste 24 UN", substring = true).assertExists()
    }

    @Test
    fun `cargar igual registra el conteo`() {
        // Si el estante tenía dos pallets separados, el operario sabe más que
        // la regla.
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = yaContado,
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("6")
        tocar("Confirmar")

        compose.onNodeWithText("Cargar igual").performClick()

        assertEquals(6000, cargado)
    }

    @Test
    fun `cancelar el aviso no registra nada y deja la ficha abierta`() {
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = yaContado,
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("6")
        tocar("Confirmar")

        compose.onAllNodesWithText("Cancelar").onLast().performClick()

        assertNull(cargado)
        compose.onNodeWithText("6 UN").assertExists()
    }

    @Test
    fun `sin conteos previos confirma derecho`() {
        var cargado: Int? = null
        compose.setContent {
            FichaDelArticulo(
                articulo = tornillos, admiteDecimales = false,
                ubicaciones = emptyList(), previos = emptyList(),
                alCancelar = {},
                alConfirmar = { milesimas, _, _ -> cargado = milesimas },
            )
        }
        teclear("6")

        tocar("Confirmar")

        assertEquals(6000, cargado)
    }
```

Actualizar también `abrirFicha()`, que ya existe en el archivo, para que pase
`previos = emptyList()`.

Imports nuevos: `androidx.compose.ui.test.assertExists` no hace falta (es
método de `SemanticsNodeInteraction`), pero sí
`com.controldestock.nucleo.ConteoLocal`,
`com.controldestock.nucleo.EventoConteo`, `org.junit.Assert.assertEquals` y
`org.junit.Assert.assertNull`.

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.FichaDelArticuloTest" --no-daemon`
Expected: FAIL — `FichaDelArticulo` todavía no tiene el parámetro `previos`

- [ ] **Step 3: Sacar los controles a su propio archivo**

Crear `celular/app/src/main/kotlin/com/controldestock/ui/ControlesDeCarga.kt`
y **mover ahí, tal cual**, las funciones `TecladoNumerico` y
`ElegirUbicacion` que hoy están al final de `FichaDelArticulo.kt`, quitándoles
el `private` para que las dos fichas las usen:

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * El teclado de la carga: propio y con teclas grandes.
 *
 * Se usa con apuro y a veces con guantes, así que no sirve el teclado del
 * sistema. Lo comparten la ficha del artículo y la del alta rápida: dos
 * teclados distintos para lo mismo se desincronizan en cuanto uno cambia.
 */
@Composable
fun TecladoNumerico(alTocar: (String) -> Unit, alBorrar: () -> Unit) {
    val filas = listOf(
        listOf("1", "2", "3"),
        listOf("4", "5", "6"),
        listOf("7", "8", "9"),
        listOf("C", "0", ","),
    )

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        filas.forEach { fila ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                fila.forEach { tecla ->
                    Button(
                        onClick = { alTocar(tecla) },
                        modifier = Modifier.weight(1f).height(64.dp),
                    ) {
                        Text(tecla, fontSize = 22.sp)
                    }
                }
                if (fila == filas.last()) {
                    Button(
                        onClick = alBorrar,
                        modifier = Modifier.weight(1f).height(64.dp),
                    ) {
                        Text("←", fontSize = 22.sp)
                    }
                }
            }
        }
    }
}

/** Dónde estaba de verdad: la lista del maestro, o una escrita a mano. */
@Composable
fun ElegirUbicacion(
    ubicaciones: List<String>,
    alElegir: (String) -> Unit,
    alCerrar: () -> Unit,
) {
    var filtro by remember { mutableStateOf("") }
    var otra by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = alCerrar,
        title = { Text("¿Dónde estaba?") },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                OutlinedTextField(
                    value = filtro,
                    onValueChange = { filtro = it },
                    label = { Text("Buscar ubicación") },
                )
                ubicaciones.filter { it.contains(filtro, ignoreCase = true) }
                    .take(20)
                    .forEach { u ->
                        TextButton(onClick = { alElegir(u) }) { Text(u) }
                    }
                OutlinedTextField(
                    value = otra,
                    onValueChange = { otra = it },
                    label = { Text("Otra…") },
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { if (otra.isNotBlank()) alElegir(otra.trim()) else alCerrar() },
            ) { Text("Listo") }
        },
        dismissButton = { TextButton(onClick = alCerrar) { Text("Cancelar") } },
    )
}
```

Las dos son exactamente lo que hoy está al final de `FichaDelArticulo.kt`,
sin `private`. No cambia nada del comportamiento: es una mudanza.

Borrar de `FichaDelArticulo.kt` las dos funciones movidas y los imports que
queden sin uso.

- [ ] **Step 4: Agregar el aviso a `FichaDelArticulo`**

Nuevos imports en `FichaDelArticulo.kt`:

```kotlin
import com.controldestock.nucleo.Cantidades
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.nucleo.Repeticion
import com.controldestock.nucleo.horaLocal
```

La firma suma `previos`, antes de las lambdas:

```kotlin
fun FichaDelArticulo(
    articulo: ArticuloEntidad,
    admiteDecimales: Boolean,
    ubicaciones: List<String>,
    /** Los conteos que este celular ya hizo de este artículo. */
    previos: List<ConteoLocal>,
    alCancelar: () -> Unit,
    // Último para que quede como lambda final en la llamada.
    alConfirmar: (Int, String?, String?) -> Unit,
) {
```

Agregar el estado, junto a `confirmarDecimal`:

```kotlin
    var confirmarRepetido by remember {
        mutableStateOf<Pair<Int, Repeticion.YaContado>?>(null)
    }
```

Y reemplazar `confirmar()` por estas tres funciones:

```kotlin
    fun cargar(milesimas: Int) =
        alConfirmar(milesimas, ubicacionReal, observaciones.ifBlank { null })

    /**
     * El último filtro antes de cargar: ¿ya se contó acá?
     *
     * Va después de la pregunta por el decimal y no antes: preguntar dos
     * cosas a la vez no se entiende, y la cantidad tiene que estar resuelta
     * para poder decir cuánto se está sumando.
     */
    fun preguntarOCargar(milesimas: Int) {
        val repetido = Repeticion.buscar(previos, articulo.ubicacion, ubicacionReal)
        if (repetido == null) cargar(milesimas) else confirmarRepetido = milesimas to repetido
    }

    fun confirmar() {
        when (val r = ReglasDeCarga.validar(texto, admiteDecimales)) {
            is ResultadoDeCarga.Valida -> preguntarOCargar(r.milesimas)
            is ResultadoDeCarga.PideConfirmacion -> confirmarDecimal = r
            is ResultadoDeCarga.Invalida -> aviso = r.motivo
        }
    }
```

En el cartel del decimal, cambiar la acción de «Sí, cargar» para que pase por
el mismo filtro:

```kotlin
                TextButton(onClick = {
                    confirmarDecimal = null
                    preguntarOCargar(pregunta.milesimas)
                }) { Text("Sí, cargar") }
```

Y agregar el cartel nuevo, junto al del decimal:

```kotlin
    confirmarRepetido?.let { (milesimas, repetido) ->
        val donde = ubicacionReal ?: articulo.ubicacion ?: "sin ubicación"

        AlertDialog(
            onDismissRequest = { confirmarRepetido = null },
            title = { Text("¿Ya lo contaste acá?") },
            text = {
                Text(
                    "Ya cargaste ${Cantidades.aTexto(repetido.milesimas)} ${articulo.unidad} " +
                        "de este producto en $donde a las ${horaLocal(repetido.cuando)}. " +
                        "¿Sumás otra carga?",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmarRepetido = null
                    cargar(milesimas)
                }) { Text("Cargar igual") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarRepetido = null }) { Text("Cancelar") }
            },
        )
    }
```

- [ ] **Step 5: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.FichaDelArticuloTest" --no-daemon`
Expected: PASS, 5 tests nuevos y los 2 de antes intactos

(La app todavía no compila entera: `MainActivity` no le pasa `previos`. Se
arregla en la Task 7. Si el compilador frena la corrida, agregar
`previos = emptyList()` en la llamada de `MainActivity` y dejar el cableado
de verdad para su tarea.)

- [ ] **Step 6: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui celular/app/src/testDebug
git commit -m "Avisa cuando el producto ya se conto en esa ubicacion

Un SKU se cuenta una sola vez por ubicacion: el segundo escaneo en el mismo
estante es que el operario perdio la cuenta, y si entra callado el
inventario termina con unidades de mas.

Avisa y deja decidir en vez de bloquear: si el estante tenia dos pallets
separados, el operario sabe mas que la regla, y sin forma de registrar lo
que ve termina anotando en un papel.

El teclado y el selector de ubicacion salen a su propio archivo: los va a
usar tambien la ficha del alta rapida, y dos teclados distintos para lo
mismo se desincronizan en cuanto uno cambia."
```

---

### Task 6: La ficha del alta y el botón de la franja

**Files:**
- Create: `celular/app/src/main/kotlin/com/controldestock/ui/FichaDeAlta.kt`
- Create: `celular/app/src/testDebug/kotlin/com/controldestock/ui/FichaDeAltaTest.kt`
- Modify: `celular/app/src/main/kotlin/com/controldestock/ui/PantallaEscaneo.kt`

**Interfaces:**
- Consumes: `TecladoNumerico`, `ElegirUbicacion`, `ReglasDeCarga`, `UnidadEntidad`
- Produces:
  - `FichaDeAlta(codigo, unidades, ubicaciones, alCancelar, alConfirmar)` con
    `alConfirmar: (descripcion: String, unidad: String, ubicacion: String?, milesimas: Int, observaciones: String?) -> Unit`
  - `PantallaEscaneo(..., alDarDeAlta: (() -> Unit)?, ...)`

- [ ] **Step 1: Escribir el test de la ficha del alta**

Crear `celular/app/src/testDebug/kotlin/com/controldestock/ui/FichaDeAltaTest.kt`:

```kotlin
package com.controldestock.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import com.controldestock.datos.UnidadEntidad
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Vive en `testDebug` por lo mismo que `FichaDelArticuloTest`: probar una
 * pantalla necesita una actividad que aporta `ui-test-manifest`, y eso no
 * puede viajar en el APK que se instala en el depósito.
 */
@RunWith(RobolectricTestRunner::class)
class FichaDeAltaTest {

    @get:Rule
    val compose = createComposeRule()

    private val unidades = listOf(
        UnidadEntidad("UN", "Unidad", 0),
        UnidadEntidad("KG", "Kilogramo", 1),
    )

    private var alta: List<Any?>? = null

    private fun abrir() {
        compose.setContent {
            FichaDeAlta(
                codigo = "7790999",
                unidades = unidades,
                ubicaciones = listOf("P-1"),
                alCancelar = {},
                alConfirmar = { descripcion, unidad, ubicacion, milesimas, observaciones ->
                    alta = listOf(descripcion, unidad, ubicacion, milesimas, observaciones)
                },
            )
        }
    }

    private fun tocar(texto: String) {
        compose.onNodeWithText(texto).performScrollTo().performClick()
    }

    @Test
    fun `muestra el codigo escaneado para poder confirmarlo`() {
        // El operario tiene que poder verificar que la app leyó el código que
        // él ve en la etiqueta, no el de la caja de al lado.
        abrir()

        compose.onNodeWithText("7790999", substring = true).assertExists()
    }

    @Test
    fun `sin descripcion no deja dar de alta`() {
        // Un artículo sin descripción es una fila que nadie va a poder
        // resolver después en el ERP.
        abrir()
        tocar("6")

        tocar("Dar de alta")

        assertNull(alta)
        compose.onNodeWithText("Escribí qué es el producto").assertExists()
    }

    @Test
    fun `da de alta con lo que cargo el operario`() {
        abrir()
        compose.onNodeWithText("¿Qué es?").performScrollTo().performTextInput("Pack por 6")
        tocar("6")

        tocar("Dar de alta")

        assertEquals(listOf("Pack por 6", "UN", null, 6000, null), alta)
    }

    @Test
    fun `la unidad se puede cambiar y habilita los decimales`() {
        // Media unidad suele ser un error; medio kilo no.
        abrir()
        compose.onNodeWithText("¿Qué es?").performScrollTo().performTextInput("Harina suelta")
        tocar("Unidad: UN")
        tocar("Kilogramo")
        tocar("3")
        tocar(",")
        tocar("5")

        tocar("Dar de alta")

        assertEquals(listOf("Harina suelta", "KG", null, 3500, null), alta)
    }

    @Test
    fun `sin cantidad no deja dar de alta`() {
        abrir()
        compose.onNodeWithText("¿Qué es?").performScrollTo().performTextInput("Pack por 6")

        tocar("Dar de alta")

        assertNull(alta)
    }
}
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.FichaDeAltaTest" --no-daemon`
Expected: FAIL con `Unresolved reference: FichaDeAlta`

- [ ] **Step 3: Implementar `FichaDeAlta.kt`**

```kotlin
package com.controldestock.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.controldestock.datos.UnidadEntidad
import com.controldestock.nucleo.ReglasDeCarga
import com.controldestock.nucleo.ResultadoDeCarga

/**
 * El alta de un código que no está en el maestro.
 *
 * Se llega a propósito, desde el botón de la franja roja: una lectura al
 * pasar no crea un artículo. Un código mal leído, o el de la caja en vez del
 * producto, también llega como desconocido, y si cada uno creara una fila el
 * inventario se llenaría de fantasmas que alguien tiene que limpiar después.
 *
 * El código se muestra arriba y en grande: el operario tiene que poder
 * verificar que la app leyó la etiqueta que él ve.
 */
@Composable
fun FichaDeAlta(
    codigo: String,
    unidades: List<UnidadEntidad>,
    ubicaciones: List<String>,
    alCancelar: () -> Unit,
    // Última para que quede como lambda final en la llamada.
    alConfirmar: (String, String, String?, Int, String?) -> Unit,
) {
    var descripcion by remember { mutableStateOf("") }
    var unidad by remember { mutableStateOf(unidades.firstOrNull { it.codigo == "UN" } ?: unidades.firstOrNull()) }
    var ubicacion by remember { mutableStateOf<String?>(null) }
    var texto by remember { mutableStateOf("") }
    var observaciones by remember { mutableStateOf("") }
    var aviso by remember { mutableStateOf<String?>(null) }
    var confirmarDecimal by remember {
        mutableStateOf<ResultadoDeCarga.PideConfirmacion?>(null)
    }
    var eligiendoUbicacion by remember { mutableStateOf(false) }
    var eligiendoUnidad by remember { mutableStateOf(false) }

    fun cargar(milesimas: Int) = alConfirmar(
        descripcion.trim(),
        unidad?.codigo ?: "UN",
        ubicacion,
        milesimas,
        observaciones.ifBlank { null },
    )

    fun confirmar() {
        if (descripcion.isBlank()) {
            // Sin descripción, la fila que queda no la puede resolver nadie
            // después: el servidor también la exige.
            aviso = "Escribí qué es el producto"
            return
        }

        when (val r = ReglasDeCarga.validar(texto, unidad?.admiteDecimales == 1)) {
            is ResultadoDeCarga.Valida -> cargar(r.milesimas)
            is ResultadoDeCarga.PideConfirmacion -> confirmarDecimal = r
            is ResultadoDeCarga.Invalida -> aviso = r.motivo
        }
    }

    Column(
        modifier = Modifier.fillMaxWidth().padding(16.dp).verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text("Producto nuevo", fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Text(codigo, fontSize = 24.sp, fontWeight = FontWeight.Bold)

        OutlinedTextField(
            value = descripcion,
            onValueChange = { descripcion = it; aviso = null },
            label = { Text("¿Qué es?") },
            modifier = Modifier.fillMaxWidth(),
        )

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Unidad: ${unidad?.codigo ?: "UN"}")
            TextButton(onClick = { eligiendoUnidad = true }) { Text("Cambiar") }
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Ubicación: ${ubicacion ?: "sin ubicación"}")
            TextButton(onClick = { eligiendoUbicacion = true }) { Text("Elegir") }
        }

        Text(
            "${texto.ifEmpty { "0" }} ${unidad?.codigo ?: "UN"}",
            fontSize = 40.sp,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        )

        TecladoNumerico(
            alTocar = { tecla ->
                aviso = null
                texto = if (tecla == "C") "" else texto + tecla
            },
            alBorrar = { texto = texto.dropLast(1) },
        )

        OutlinedTextField(
            value = observaciones,
            onValueChange = { observaciones = it },
            label = { Text("Observaciones (opcional)") },
            modifier = Modifier.fillMaxWidth(),
        )

        aviso?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            TextButton(onClick = alCancelar, modifier = Modifier.weight(1f)) {
                Text("Cancelar")
            }
            Button(
                onClick = { confirmar() },
                modifier = Modifier.weight(2f).height(56.dp),
            ) {
                Text("Dar de alta", fontSize = 18.sp)
            }
        }
    }

    confirmarDecimal?.let { pregunta ->
        AlertDialog(
            onDismissRequest = { confirmarDecimal = null },
            title = { Text("¿Va con decimales?") },
            text = { Text(pregunta.motivo) },
            confirmButton = {
                TextButton(onClick = {
                    confirmarDecimal = null
                    cargar(pregunta.milesimas)
                }) { Text("Sí, cargar") }
            },
            dismissButton = {
                TextButton(onClick = { confirmarDecimal = null }) { Text("Corregir") }
            },
        )
    }

    if (eligiendoUnidad) {
        AlertDialog(
            onDismissRequest = { eligiendoUnidad = false },
            title = { Text("¿Cómo se cuenta?") },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    unidades.forEach { u ->
                        TextButton(onClick = { unidad = u; eligiendoUnidad = false }) {
                            Text("${u.nombre} (${u.codigo})")
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { eligiendoUnidad = false }) { Text("Listo") }
            },
        )
    }

    if (eligiendoUbicacion) {
        ElegirUbicacion(
            ubicaciones = ubicaciones,
            alElegir = { ubicacion = it; eligiendoUbicacion = false },
            alCerrar = { eligiendoUbicacion = false },
        )
    }
}
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --tests "com.controldestock.ui.FichaDeAltaTest" --no-daemon`
Expected: PASS, 5 tests nuevos

Si el test de la unidad no encuentra «Kilogramo», mirar el texto exacto que
dibuja el botón —`"${u.nombre} (${u.codigo})"`— y usar `substring = true`.

- [ ] **Step 5: Agregar el botón a la franja**

En `PantallaEscaneo.kt`, la firma suma el parámetro, antes de `ficha`:

```kotlin
    /** Qué hacer con el código desconocido. Nulo si no hay ninguno. */
    alDarDeAlta: (() -> Unit)?,
```

Y la franja pasa a llevar el botón:

```kotlin
            avisoDeDesconocido?.let {
                Surface(
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.align(Alignment.BottomCenter).fillMaxWidth(),
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            it,
                            color = MaterialTheme.colorScheme.onError,
                            modifier = Modifier.weight(1f),
                        )
                        // Dar de alta es un acto deliberado: la ficha no se
                        // abre sola porque un codigo mal leido tambien llega
                        // como desconocido.
                        alDarDeAlta?.let { darDeAlta ->
                            Button(onClick = darDeAlta) { Text("Darlo de alta") }
                        }
                    }
                }
            }
```

Imports nuevos: `androidx.compose.material3.Button`.

- [ ] **Step 6: Compilar**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat :app:compileDebugKotlin --no-daemon`
Expected: falla solo en `MainActivity.kt`, que todavía no pasa los
parámetros nuevos. Se arregla en la Task 7.

- [ ] **Step 7: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/ui celular/app/src/testDebug
git commit -m "Agrega la pantalla del alta rapida

El codigo escaneado se muestra arriba y en grande: el operario tiene que
poder verificar que la app leyo la etiqueta que el ve, y no la de la caja de
al lado.

Se llega desde un boton en la franja roja y no abriendo la ficha sola. Un
codigo mal leido tambien llega como desconocido, y si cada lectura rara
creara una fila el inventario se llenaria de fantasmas que alguien tiene que
limpiar despues.

Sin descripcion no hay alta: una fila sin descripcion no la puede resolver
nadie despues en el ERP."
```

---

### Task 7: Cablear y probar en el celular

**Files:**
- Modify: `celular/app/src/main/kotlin/com/controldestock/MainActivity.kt`

**Interfaces:**
- Consumes: todo lo anterior

- [ ] **Step 1: Cablear `MainActivity`**

Imports nuevos:

```kotlin
import com.controldestock.datos.UnidadEntidad
import com.controldestock.nucleo.ConteoLocal
import com.controldestock.ui.FichaDeAlta
```

Estado nuevo, junto al que ya está:

```kotlin
    var codigoDesconocido by remember { mutableStateOf<String?>(null) }
    var dandoDeAlta by remember { mutableStateOf(false) }
    var unidades by remember { mutableStateOf<List<UnidadEntidad>>(emptyList()) }
    var previos by remember { mutableStateOf<List<ConteoLocal>>(emptyList()) }
```

En el `LaunchedEffect(Unit)` y en la rama `Vinculado`, después de
`ubicaciones = contador.ubicaciones()`, agregar:

```kotlin
        unidades = contador.unidades()
```

En `alLeer`, la guarda pasa a mirar también el alta abierta, y la rama
`Desconocido` recuerda el código:

```kotlin
                alLeer = { codigo ->
                    // La cámara avisa una lectura por cuadro: sin esta guarda
                    // se abrirían decenas de fichas del mismo código.
                    if (hallazgo == null && !dandoDeAlta) {
                        alcance.launch {
                            when (val h = contador.buscar(codigo)) {
                                is Hallazgo.Encontrado -> {
                                    avisos.leido()
                                    avisoDesconocido = null
                                    codigoDesconocido = null
                                    previos = contador.conteosDe(h.articulo)
                                    hallazgo = h
                                }
                                is Hallazgo.Desconocido -> {
                                    avisos.desconocido()
                                    codigoDesconocido = h.codigo
                                    avisoDesconocido =
                                        "Este código no está en el conteo: ${h.codigo}"
                                }
                            }
                        }
                    }
                },
```

`PantallaEscaneo` recibe los parámetros nuevos:

```kotlin
                fichaAbierta = hallazgo is Hallazgo.Encontrado || dandoDeAlta,
                alDarDeAlta = codigoDesconocido?.let { { dandoDeAlta = true } },
```

Y el contenido pasa a tener las dos fichas:

```kotlin
            ) {
                (hallazgo as? Hallazgo.Encontrado)?.let { encontrado ->
                    FichaDelArticulo(
                        articulo = encontrado.articulo,
                        admiteDecimales = encontrado.admiteDecimales,
                        ubicaciones = ubicaciones,
                        previos = previos,
                        alCancelar = { hallazgo = null },
                    ) { milesimas, ubicacionReal, observaciones ->
                        alcance.launch {
                            contador.registrar(
                                encontrado.articulo, milesimas, ubicacionReal, observaciones,
                            )
                            avisos.cargado()
                            hallazgo = null
                            pendientes = base.conteoDao().cantidadPendientes()

                            // Intento inmediato: con señal, el tablero se
                            // entera en el momento. Sin señal no pasa nada y
                            // el trabajo periódico lo sube más tarde. Va
                            // después de cerrar la ficha a propósito: al
                            // revés, el operario esperaría a la red para
                            // poder seguir contando.
                            sincronizador.sincronizar()
                            pendientes = base.conteoDao().cantidadPendientes()
                        }
                    }
                }

                if (dandoDeAlta) {
                    codigoDesconocido?.let { codigo ->
                        FichaDeAlta(
                            codigo = codigo,
                            unidades = unidades,
                            ubicaciones = ubicaciones,
                            alCancelar = { dandoDeAlta = false },
                        ) { descripcion, unidad, ubicacion, milesimas, observaciones ->
                            alcance.launch {
                                contador.darDeAlta(
                                    codigo, descripcion, unidad, ubicacion,
                                    milesimas, observaciones,
                                )
                                avisos.cargado()
                                dandoDeAlta = false
                                codigoDesconocido = null
                                avisoDesconocido = null
                                // La ubicación nueva pasa a estar disponible
                                // para corregir en las fichas siguientes.
                                ubicaciones = contador.ubicaciones()
                                pendientes = base.conteoDao().cantidadPendientes()

                                val resultado = sincronizador.sincronizar()
                                pendientes = base.conteoDao().cantidadPendientes()

                                // El servidor ya conocía ese código: lo dio de
                                // alta otro operario hace un minuto, o coincide
                                // con el SKU de uno del maestro. La descripción
                                // que escribió este operario se descartó, así
                                // que merece enterarse mientras sigue mirando.
                                resultado.yaExistian.firstOrNull()?.let {
                                    avisoDesconocido = "Ese código ya era: $it"
                                }
                            }
                        }
                    }
                }
            }
```

- [ ] **Step 2: Correr toda la suite**

Run: `cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon`
Expected: PASS

Run: `.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor`
Expected: PASS, 349 tests — este plan no toca el servidor

- [ ] **Step 3: Instalar y probar el circuito completo**

Levantar el servidor, crear la sesión, importar un maestro chico, dar de alta
un operario y vincular el celular escaneando el QR. Después:

1. Escanear un producto que **no** esté en el maestro (sirve cualquiera de la
   cocina). Tiene que sonar distinto y aparecer la franja roja **con el botón
   «Darlo de alta»**.
2. **Cortar la WiFi del celular** (`adb shell svc wifi disable`).
3. Tocar «Darlo de alta», escribir qué es, elegir la unidad, una ubicación y
   una cantidad. Confirmar: golpecito y vuelta a la cámara, sin ninguna queja
   por la falta de red.
4. Escanear **el mismo producto otra vez**: ahora tiene que subir su ficha
   normal, con la descripción que se escribió, en vez de decir «desconocido».
5. Cargar una cantidad y confirmar: tiene que aparecer **«¿Ya lo contaste
   acá?»** con lo cargado antes y la hora. Tocar «Cancelar».
6. Corregirle la ubicación a otra y confirmar: **no** tiene que avisar.
7. Prender la WiFi (`adb shell svc wifi enable`). Confirmar un conteo más.
8. En el panel: el artículo nuevo aparece en el tablero, marcado como alta
   rápida, con las cantidades cargadas, y el indicador del celular vuelve a
   «Todo al día».

Ninguno de estos ocho pasos lo cubre un test: la cámara, el sonido y el
comportamiento sin red solo se prueban en la mano.

- [ ] **Step 4: Probar la actualización en el mundo real**

Es la prueba que protege el trabajo de un operario, y solo vale hecha de
verdad:

1. `git stash` de lo que no esté commiteado y `git checkout` del commit
   anterior a este plan.
2. Compilar e instalar ese APK: `:app:assembleDebug` y `adb install -r`.
3. Vincular, contar dos artículos **con la WiFi cortada**, para que queden
   pendientes.
4. Volver a la rama de este plan, compilar e **instalar encima**
   (`adb install -r`, sin `pm clear`).
5. Abrir la app: tiene que arrancar sin cerrarse y el indicador tiene que
   seguir mostrando **los mismos pendientes**. Confirmarlo también en la base:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb exec-out run-as com.controldestock cat databases/control-de-stock.db > celular.db
& $adb exec-out run-as com.controldestock cat databases/control-de-stock.db-wal > celular.db-wal
.\servidor\.venv\Scripts\python.exe -c "import sqlite3;c=sqlite3.connect('celular.db');print([r for r in c.execute('select codigo,cantidad,estadoSync from conteo')])"
```

- [ ] **Step 5: Commit**

```bash
git add celular/app/src/main/kotlin/com/controldestock/MainActivity.kt
git commit -m "Conecta el alta rapida con la pantalla de escaneo

Mientras el alta esta abierta el escaneo se pausa, igual que con la ficha:
la camara avisa una lectura por cuadro y sin la guarda se abririan decenas
de altas del mismo codigo.

Al dar de alta se vuelven a leer las ubicaciones: la que acaba de nombrar el
operario tiene que estar disponible para corregir en las fichas siguientes."
```

---

## Verificación final del plan

```powershell
cd celular ; C:\Gradle\gradle-8.7\bin\gradle.bat test --no-daemon
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
```

Los dos en verde, el circuito del Step 3 de la Task 7 andando en el celular, y
la actualización del Step 4 sin perder un solo conteo.

Con esto, un código que no está en el maestro deja de ser una unidad perdida:
el operario lo da de alta con el producto en la mano, con o sin señal, y el
inventario sale completo. Y contar dos veces el mismo producto en el mismo
estante deja de entrar en silencio.

**Lo que queda para el plan siguiente:** «Mis conteos» con anulación, la
búsqueda para las etiquetas ilegibles, la linterna, vincular un alta rápida a
un SKU del maestro desde el panel, y el APK firmado para distribuir.
