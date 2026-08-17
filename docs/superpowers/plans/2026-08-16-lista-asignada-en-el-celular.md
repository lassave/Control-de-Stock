# La lista asignada en el celular y el avance por ubicación — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [x]`) para llevar la cuenta.

**Objetivo:** que el operario abra la app y vea qué le tocó y qué ya contó,
sin señal; y que desde el panel se vea el reparto completo, fila por
artículo, exportable.

**Arquitectura:** el celular ya tiene todo lo que necesita para armar la
lista —el maestro con la ubicación de cada artículo, sus códigos de barra y
sus propios conteos—, así que lo único que baja del servidor es la lista de
ubicaciones asignadas. El armado vive en `celular/nucleo` como función pura,
para que tenga tests de verdad. Del lado del panel, la pestaña nueva reusa
`tablero.filas(...)` para que «estado» y «cuánto» sean, por construcción, el
mismo número que muestra el tablero.

**Tech Stack:** FastAPI, SQLite (SQL directo), pytest; Kotlin, Jetpack
Compose, Room, JUnit; JavaScript sin dependencias.

**Especificación:**
`docs/superpowers/specs/2026-08-16-lista-asignada-en-el-celular-design.md`

## Global Constraints

- **`stock_sistema` y `costo_unitario` no salen por `/api/dispositivo/*`.**
  El endpoint nuevo devuelve nombres de ubicación y nada más.
- **Todo dato del servidor se escapa antes de ir al HTML.** El guardián de
  `test_panel_estatico.py` es una lista blanca por nombre de variable y **no
  ve las variables sueltas** (deuda conocida). Escapar a mano igual, e
  interpolar en línea (`${fila.contado_por.map(esc).join(", ")}`) para que el
  guardián sí lo vea.
- **Nada externo en el navegador.** Ni CDN, ni fuentes, ni librerías.
- **Ninguna dependencia nueva en el celular.** `BackHandler`
  (`activity-compose:1.9.0`) y `LifecycleEventEffect`
  (`lifecycle-runtime-compose:2.8.0`) ya están en el classpath.
- **Cantidades en milésimas, siempre `int`.**
- **Textos en castellano rioplatense**, sin jerga técnica.
- **Mensajes de commit en castellano, en presente, describiendo el efecto**,
  y el cuerpo explica *por qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- **Esta rama se mergea con fast-forward o merge normal, nunca squash**: el
  `versionCode` del APK sale de `git rev-list --count HEAD`.

## Entorno

El `python` del PATH es el acceso directo de la Microsoft Store y no ejecuta
nada: siempre el intérprete del venv por ruta.

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon
C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon
```

## Lo que ya existe y se consume

- **`asignaciones.de_operario(con, pasada_id, operario_id)`**
  (`servidor/app/repos/asignaciones.py:37-43`) devuelve la lista de
  ubicaciones ordenada. No hay que escribir SQL nuevo para el endpoint.
- **`dispositivos._contexto(request, token)`**
  (`servidor/app/api/dispositivos.py:45-55`) ya resuelve token inválido
  (401) y sin sesión abierta (409).
- **`tablero.filas(con, sesion_id, filtros)`** y `_pasa_filtros`
  (`servidor/app/servicios/tablero.py`) ya calculan estado, total vigente y
  filtrado. La pestaña nueva los reusa en vez de recalcularlos.
- **`panel._filtros(...)`** (`servidor/app/api/panel.py:127`) arma el dict de
  filtros desde la query.
- **`GET /api/sesiones/{id}/exportar/{tipo}`** ya pone el BOM, el
  `Content-Disposition` y el 404 del tipo desconocido: la exportación nueva
  entra ahí, no en un endpoint propio.
- **El conmutador de pestañas de `app.js:463-467`** es genérico sobre
  `data-vista` → `#vista-${...}`: la pestaña nueva no necesita JS de
  navegación.
- **En el celular**: `articulo` ya guarda `idOrden`, `sku`, `descripcion`,
  `ubicacion` y `unidad`; la tabla `codigo` guarda los códigos de barra; la
  tabla `conteo` guarda `cantidad`, `anulaUuid` y `estadoSync`.
  `MIGRACION_1_2` (`datos/BaseLocal.kt:76-81`) es el modelo de migración a
  seguir.
- **`fichaAbierta` y `PantallaTest`** (`ui/Pantalla.kt`) son el lugar donde
  ya vive lógica pura de UI con tests JUnit comunes.

## Decisiones ya tomadas, que no se reabren

1. **La respuesta del endpoint va envuelta en un objeto**, no como lista
   pelada: `forma()` de `test_contrato.py:32-46` devuelve el conjunto vacío
   para una lista de strings, así que un contrato de lista pelada no fijaría
   nada.
2. **Sin pasada abierta → 409**, no lista vacía. Una lista vacía es mentira y
   el celular la escribiría encima de la que tenía.
3. **Las ubicaciones asignadas van en una tabla propia** de la base local, no
   en una columna de `vinculacion`: `VinculacionDao.guardar` es
   `@Insert(REPLACE)` de la fila entera y actualizar el reparto por ahí puede
   pisar `url` y `token` y desvincular el celular.
4. **El tilde cuenta lo `PENDIENTE`.** Dice «yo ya lo conté», no «ya subió».

---

## Tareas

Dos frentes independientes: servidor/panel (T0–T5) y celular (T6–T12). El
único punto de encuentro es T13.

### T0 — `ultima_pasada` y el `ValueError` que hoy rompe

- [x] Test: `sesiones.ultima_pasada(con, sesion_id)` devuelve la pasada de
      mayor `numero`, esté abierta o cerrada; y `None` si no hay ninguna.
- [x] Test: `asignaciones.operarios_con_ubicaciones(con)` no rompe cuando la
      sesión abierta no tiene pasada abierta (hoy sube el `ValueError` de
      `sesiones.pasada_abierta` y sale 500; está anotado en la deuda).
- [x] Implementar las dos cosas.

*Por qué primero:* la pestaña del panel necesita la última pasada aunque la
sesión esté cerrada —justo cuando alguien mira quién hizo qué—, y
`pasada_abierta` tira `ValueError` ahí.

### T1 — `GET /api/dispositivo/mis-ubicaciones`

- [x] Test: con ubicaciones asignadas devuelve
      `{"pasada_id": N, "ubicaciones": [...]}`, ordenadas.
- [x] Test: sin asignaciones devuelve 200 con `"ubicaciones": []`.
- [x] Test: token inválido → 401. Sin sesión abierta → 409.
- [x] Test: sin pasada abierta → **409**, no 500 ni lista vacía.
- [x] Test: `set(respuesta) == {"pasada_id", "ubicaciones"}` — lo que impide
      que alguien «aproveche el viaje» y le cuelgue el maestro con stock.
- [x] `asignaciones.de_operario_en_sesion(con, sesion_id, operario_id)`,
      reusando `de_operario`. El router traduce el `ValueError` a 409.
- [x] `celular/contrato/mis-ubicaciones.json`, agregado a `ARCHIVOS` en
      `test_contrato.py` y a `capturar.py`. **El fixture `vivo` y
      `capturar.py` tienen que asignarle una ubicación al operario antes de
      capturar**, si no el archivo queda vacío y no documenta nada.

*Nombre:* `mis-ubicaciones` sigue la convención de `mis-conteos`, que ya
existe y significa lo mismo: lo mío, resuelto por el token.

### T2 — Extraer `CTE_VIGENTES` de `tablero.py` [independiente]

- [x] Mover las CTE `vigentes` y `ultima_pasada` de
      `tablero._consulta_base()` a una constante del módulo, **sin cambiar un
      solo carácter del SQL**.
- [x] La suite entera en verde sin tocar ningún test. Commit solo.

*Por qué:* «quién lo contó» tiene que significar exactamente lo mismo que en
el tablero (anulaciones descartadas de a pares, solo la última pasada
contada). Reescribir esa regla garantiza que tarde o temprano las dos
pestañas digan cosas distintas del mismo SKU.

### T3 — `servidor/app/servicios/reparto.py`

- [x] Test: un artículo con dos operarios asignados a su ubicación devuelve
      los dos, ordenados por nombre.
- [x] Test: un artículo contado por dos operarios devuelve los dos, sin
      repetir al que contó tres veces.
- [x] Test: un artículo sin ubicación sale con `asignado_a` vacío.
- [x] Test: una ubicación que nadie tiene asignada sale con `asignado_a`
      vacío (es la fila que más importa de la pestaña).
- [x] Test: un conteo anulado no aparece en `contado_por` ni suma en el
      total.
- [x] Test: el total y el estado coinciden con los que da `tablero.filas`
      para el mismo artículo.
- [x] Test: `stock_sistema` y `costo_unitario` **no** son claves de la fila.
- [x] `filas(con, sesion_id, filtros=None)` que llama a `tablero.filas` y le
      agrega `asignado_a` y `contado_por`.

*Sin `GROUP_CONCAT`:* las dos consultas devuelven pares crudos y Python los
agrupa en listas. Un nombre como «Pérez, Juan» vuelve ambiguo cualquier
separador; con listas de verdad el panel escapa nombre por nombre y el CSV
los une con `" | "` —no con `;`, que es el separador del archivo—.

### T4 — Los endpoints del panel

- [x] Test: `GET /api/sesiones/{id}/reparto` devuelve `{"filas": [...]}` y
      respeta los filtros de la query.
- [x] Test: 404 con una sesión que no existe.
- [x] Test: `GET /api/sesiones/{id}/exportar/reparto` devuelve el CSV con las
      columnas esperadas, los nombres unidos con `" | "` y los filtros
      aplicados.
- [x] Test: el 404 del tipo de exportación desconocido sigue funcionando.
- [x] `exportacion.reparto(...)` con
      `COLUMNAS_REPARTO = ["ubicacion", "id_orden", "sku", "descripcion",
      "asignado_a", "contado_por", "contado", "estado"]`, coma decimal y `;`
      como las otras dos.

### T5 — La pestaña «Avance por ubicación»

- [x] Test: `test_panel_estatico.py` ve cinco pestañas y la sección
      `#vista-reparto`.
- [x] Test: el enlace de exportación apunta a `exportar/reparto?`.
- [x] Test literal: las columnas de operarios usan `.map(esc)`. Es tosco,
      pero es lo único que atrapa este caso mientras el guardián siga siendo
      una lista blanca; se anota como deuda.
- [x] Los tests que ya existen (nada externo, todo escapado, `node --check`)
      siguen en verde.
- [x] `<button data-vista="reparto">Avance por ubicación</button>` y
      `<section id="vista-reparto" class="vista oculta">`. El CSS no se toca:
      `.vista.oculta` ya cubre la sección nueva.
- [x] `estado.reparto = { filtros: {...} }`, **separado** de `estado.filtros`:
      cada pestaña tiene sus propios `<select>` y compartir un objeto haría
      que filtrar el tablero cambie en silencio lo que exporta el reparto.
- [x] El refresco automático agrega una sola condición: refrescar el reparto
      solo si su sección no tiene `oculta`. `refrescarTablero` queda intacto.
- [x] Las ubicaciones sin dueño se marcan visualmente como **sin asignar**.

### T6 — `celular/nucleo/ListaAsignada.kt` [independiente]

El corazón del valor de esta rama: hoy casi nada de la lógica del celular se
puede probar, y esto se puede hacer bien de entrada.

- [x] Test: un conteo `PENDIENTE` cuenta como contado (es el requisito de que
      ande sin señal, y merece un test con ese nombre).
- [x] Test: un conteo `RECHAZADO` no cuenta.
- [x] Test: una anulación descarta el par —el que anula y el anulado—.
- [x] Test: la cantidad es la **suma** de los conteos vigentes, no el último.
- [x] Test: los renglones salen ordenados por `idOrden`.
- [x] Test: un artículo con dos códigos de barra los muestra separados por
      coma, en el orden en que están.
- [x] Test: una ubicación asignada sin artículos igual aparece, con «0 de 0»
      (esconderla le haría creer al operario que no se la asignaron).
- [x] Test: un artículo de una ubicación no asignada no aparece, aunque lo
      haya contado.
- [x] Test: sin ninguna ubicación asignada devuelve lista vacía.
- [x] Test: el texto del avance es exactamente `"P-3 — 12 de 40"`.
- [x] Los tipos y la función:

```kotlin
data class ArticuloParaLista(
    val id: Int, val idOrden: Int, val sku: String, val descripcion: String,
    val ubicacion: String?, val unidad: String, val codigos: List<String>,
)
data class ConteoParaLista(
    val articuloId: Int, val uuid: String, val cantidad: Long,
    val anulaUuid: String?, val estadoSync: EstadoSync,
)
data class RenglonAsignado(
    val idOrden: Int, val sku: String, val descripcion: String,
    val codigos: String, val unidad: String, val contado: Long?,
) { val fueContado: Boolean get() = contado != null }

data class UbicacionAsignada(val ubicacion: String, val renglones: List<RenglonAsignado>) {
    val contados: Int get() = renglones.count { it.fueContado }
    val total: Int get() = renglones.size
    val avance: String get() = "$ubicacion — $contados de $total"
}

object ListaAsignada {
    fun contadoPorArticulo(conteos: List<ConteoParaLista>): Map<Int, Long>
    fun armar(asignadas: List<String>, articulos: List<ArticuloParaLista>,
              conteos: List<ConteoParaLista>): List<UbicacionAsignada>
}
```

*El texto del avance se arma acá*, no en el composable, para que un test
clave el formato exacto.

### T7 — Room versión 3: la tabla `asignacion` [independiente]

- [x] Test de migración 2→3 con datos poblados: los conteos y el maestro
      sobreviven, la tabla nueva existe y arranca vacía.
- [x] Test: `vincularA` limpia el reparto al cambiar de sesión **y** al
      cambiar de operario.
- [x] `AsignacionEntidad` (una sola columna `ubicacion`, PK), `AsignacionDao`
      (`todas()`, `reemplazar()` en transacción).
- [x] Consultas nuevas: `MaestroDao.deUbicacionesAsignadas()` con `JOIN
      asignacion` (sin lista dinámica ni el borde del `IN ()` vacío),
      trayendo `id, idOrden, sku, descripcion, ubicacion, unidad`; los códigos
      por artículo; y `ConteoDao.paraLista()` crudo: `articuloId, uuid,
      cantidad, anulaUuid, estadoSync`. **Nada de decidir vigencia en SQL** —
      si la regla queda adentro del SQL, vuelve a no tener test.

⚠ **Procedimiento contra la carrera de KSP** (deuda anotada: «va a morder en
la versión 3» — es ahora). `room.schemaLocation` es uno solo para `debug` y
`release` (`celular/app/build.gradle.kts:162`), así que la primera
compilación falla con un error de deserialización que no menciona la causa:

1. Borrar `celular/app/build/generated/ksp/` y `celular/app/build/kspCaches/`.
2. Generar con **una sola variante**:
   `gradle :app:kspDebugKotlin --no-daemon --no-parallel`.
3. Confirmar que apareció `schemas/.../3.json` y commitearlo.
4. Copiar el `createSql` de ese JSON —byte a byte, reemplazando
   `${TABLE_NAME}`— a `MIGRACION_2_3`. Room compara la estructura al abrir y
   una diferencia de comillas lo hace fallar.
5. Recién entonces compilar el resto.

### T8 — El cliente HTTP [independiente]

- [x] Test con MockWebServer: `misUbicaciones()` parsea el JSON del contrato.
- [x] Test: un 409 se traduce a un error reintentable que **no** borra nada.
- [x] `RespuestaMisUbicaciones` en `ContratoApi` + `ClienteServidor.misUbicaciones()`.

*No tocar `ClienteServidor.traducir`*: hoy mapea 409 a «El inventario está
cerrado», que para este endpoint es un mensaje equivocado. La pantalla de
inicio no muestra el texto del servidor —muestra siempre el mismo aviso
discreto—, así que el código de estado no se filtra y el 409 sigue
significando lo que significa en los otros endpoints.

### T9 — `Pantalla.EnLaLista` y `atrasCierra` [independiente]

- [x] Test: con el diálogo de código a mano abierto, atrás cierra el diálogo.
- [x] Test: con el alta abierta, atrás cierra el alta.
- [x] Test: con una ficha de artículo, atrás cierra la ficha.
- [x] Test: sin nada abierto, atrás vuelve a la lista.
- [x] `Pantalla.EnLaLista` en el `sealed class` y `atrasCierra(...)` al lado
      de `fichaAbierta`.
- [x] **`pantallaSegun` todavía NO cambia**: si cambiara acá, la app quedaría
      mostrando una rama vacía con la suite en verde.
- [x] Reescribir el docstring de `Pantalla.kt`. Hoy dice «el operario abre la
      app para contar, no para ver un menú» y era correcto para el mundo
      anterior. **No es un test que se rompió: es una decisión que cambió**, y
      el commit tiene que decirlo así.

*Volver a la lista con una ficha a medio cargar tiraría lo que el operario
tipeó: por eso el orden importa y cada caso es un test.*

### T10 — `ui/PantallaMiLista.kt`

- [x] Test (Robolectric): el cartel «Todavía no te asignaron ninguna
      ubicación» aparece con la lista vacía, y el botón de contar sigue
      funcionando igual.
- [x] Test: el tilde aparece solo en los contados.
- [x] Test: el avance por ubicación se muestra.
- [x] Test: el botón «Actualizar» llama a lo suyo.
- [x] La pantalla, con los seis datos por renglón: `id_orden`, SKU,
      descripción, códigos de barra, unidad y la cantidad contada.
- [x] No toca `MainActivity`: la app sigue igual hasta T12.

### T11 — La flecha de volver y el encabezado [independiente]

- [x] Test: con un nombre de operario absurdamente largo, «A mano» sigue
      visible y clickeable.
- [x] Test: la flecha llama a `alVolver`.
- [x] `PantallaEscaneo` gana `alVolver: () -> Unit`, **sin valor por
      defecto**, para que nadie se olvide de cablearlo. Se actualizan los
      llamados de `PantallaEscaneoTest.kt`.
- [x] Reacomodar el encabezado, **cerrando la deuda anotada** del nombre
      largo: la izquierda (flecha + pasada/operario en dos renglones) con
      `weight(1f)` y `maxLines = 1`; la derecha («A mano» + pendientes) sin
      peso, para que nunca se achique.
- [x] Ícono: `Icons.AutoMirrored.Filled.ArrowBack` viene de
      `material-icons-core`, que `material3` ya arrastra. Si no resolviera,
      plan B inmediato: `TextButton { Text("←") }` — un carácter, cero
      dependencias, y escala con el tamaño de fuente del sistema.

### T12 — El cableado

Único commit que cambia lo que el operario ve.

- [x] `ListaDeTrabajo(base)` en el módulo `app`: sin lógica, solo traduce
      entidades de Room a los tipos de núcleo, del mismo tamaño que `Contador`.
- [x] `pantallaSegun` → `EnLaLista`, la rama nueva del `when`, `BackHandler`
      registrado **solo en `Escaneando`** (en la lista, atrás sale de la app,
      que es lo que el operario espera).
- [x] `LifecycleEventEffect(ON_START)` en `App(...)`, **no adentro de la rama
      `EnLaLista`**: si el panel le reasigna una ubicación mientras cuenta, el
      reparto tiene que estar bien cuando toque la flecha. `ON_START` y no
      `ON_RESUME`, que también dispara al cerrar un diálogo del sistema.
- [x] La tabla local se escribe **solo con respuesta exitosa**; una lista
      vacía que vino del servidor **sí** se escribe (hay que distinguir
      «pregunté y no tenés nada» de «no pude preguntar»).
- [x] Guarda de reentrada con `AtomicBoolean`, como `subiendo` y `leyendo`.
- [x] La vinculación se lee de la base **adentro** de la corrutina, no del
      estado del composable: el efecto puede dispararse antes de que el
      `LaunchedEffect(Unit)` haya terminado.
- [x] Refrescar el reparto justo después de vincular, para que la primera
      entrada a la lista no esté vacía.
- [x] `TrabajoDeSincronizacion` **no se toca**.

### T13 — Verificación real y documentación

- [x] Automático: la suite del servidor entera en verde (429), `:nucleo:test`
      (96) y `:app:testDebugUnitTest` (172). Sin celular real conectado ni
      navegador en este entorno — quedan pendientes de quien ejecute el
      plan, ver más abajo.

En el navegador:

- [ ] Un artículo con dos operarios asignados y dos que lo contaron.
- [ ] Filtrar y exportar; abrir el CSV en Excel: acentos, coma decimal y los
      nombres separados con `|`.
- [ ] Una ubicación que nadie tiene asignada, marcada como tal.

En un celular real por USB (`adb devices`; no hay emulador):

- [ ] **La migración 2→3 con datos de verdad**: instalar el APK actual,
      contar dos o tres cosas sin subir, instalar el nuevo encima, confirmar
      que los pendientes siguen ahí.
- [ ] **El tilde en modo avión**: contar, modo avión, matar la app, abrirla;
      el tilde y la cantidad tienen que estar.
- [ ] **El refresco al volver del fondo**: asignar una ubicación desde el
      panel con la app en el fondo, traerla al frente, la lista aparece sola.
- [ ] **Actualizar sin señal**: aviso discreto y la lista **sigue como
      estaba**, no vacía.
- [ ] **Sin nada asignado**: el cartel, y el botón de contar funcionando.
- [ ] **La navegación con el pulgar**: ir a contar, volver con la flecha y
      con el atrás de Android; con una ficha abierta, atrás cierra la ficha y
      no salta a la lista; desde la lista, atrás cierra la app.
- [ ] **Un nombre de operario largo**: «A mano», el indicador y la flecha
      siguen todos en pantalla.
- [ ] **Una lista de 40 artículos**: el botón de contar sigue alcanzable.

Documentación:

- [x] `README.md` con la pantalla nueva y la pestaña nueva.
- [x] `docs/superpowers/deuda-conocida.md`: revincular con otro operario en
      la misma sesión no limpia los conteos pendientes del anterior
      (destapado por el tilde); el guardián de escapado sigue sin ver las
      variables sueltas y el reparto se apoya en un test literal de
      `.map(esc)`; el reparto no se refresca en segundo plano; falta un
      filtro por operario en la pestaña, que es el pedido obvio siguiente; el
      matcheo de ubicaciones sigue siendo igualdad exacta sin `.strip()` del
      lado del conteo.
