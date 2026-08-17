# Recuento por diferencias — Plan de implementación

> **Para quien lo ejecute:** SUB-SKILL OBLIGATORIA: usar
> superpowers:subagent-driven-development (recomendada) o
> superpowers:executing-plans para implementarlo tarea por tarea. Los pasos
> usan casillas (`- [ ]`) para llevar la cuenta.

**Objetivo:** una pestaña «Recuento» en el panel para marcar SKU con
diferencias y abrirles una pasada de recuento, asignada por ubicación a
operarios; el celular bloquea contar SKU fuera del recuento activo, y se
entera solo de en qué pasada está trabajando.

**Arquitectura:** hoy todo el sistema asume una sola pasada vigente por
sesión. Con pasadas concurrentes hace falta resolver, en los puntos que
deciden algo, la *pasada activa de cada operario* (no de la sesión) — una
regla nueva que reemplaza `pasada_abierta`/`ultima_pasada` exactamente donde
importa, sin tocar lo que ya calcula bien por artículo (`tablero.py`).

**Tech Stack:** FastAPI, SQLite (SQL directo), pytest; Kotlin, Jetpack
Compose, Room, JUnit; JavaScript sin dependencias.

**Especificación:**
`docs/superpowers/specs/2026-08-17-recuento-por-diferencias-design.md`

## Global Constraints

- **`stock_sistema` y `costo_unitario` no salen por `/api/dispositivo/*`.**
- **Nada se edita ni se borra.** Una corrección es una fila nueva.
- **Cantidades en milésimas, importes en centavos, siempre `int`.**
- **Nada externo en el navegador del panel.**
- **Todo dato del servidor se escapa antes de ir al HTML.** El guardián de
  `test_panel_estatico.py` no ve variables sueltas: escapar a mano,
  interpolando en línea.
- **Castellano rioplatense en todos los textos**, incluidos los de error.
- **Mensajes de commit en castellano, en presente, describiendo el
  efecto**, con el cuerpo explicando *por qué*. Terminan con
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.
- **Servidor antes que celular**: el celular tolera campos nuevos
  (`ignoreUnknownKeys = true`) pero no al revés.

## Entorno

```powershell
.\servidor\.venv\Scripts\python.exe -m pytest .\servidor\tests -q --rootdir .\servidor
C:\Gradle\gradle-8.7\bin\gradle.bat :nucleo:test --no-daemon
C:\Gradle\gradle-8.7\bin\gradle.bat :app:testDebugUnitTest --no-daemon
```

## Lo que ya existe y se consume

- **`pasada_item`** (`servidor/app/esquema.sql:102-106`): `pasada_id,
  articulo_id`, `PRIMARY KEY (pasada_id, articulo_id)`. Sin código propio
  hoy.
- **`sesiones.ultima_pasada`/`pasada_abierta`** (`servidor/app/repos/sesiones.py`):
  se mantienen para los usos puramente informativos; los que deciden algo
  migran a la regla nueva.
- **`tablero.CTE_VIGENTES`** (`servidor/app/servicios/tablero.py`): ya
  calcula lo vigente por artículo vía `MAX(pasada_numero)`. No se toca.
- **`asignaciones.reemplazar`** (`servidor/app/repos/asignaciones.py:12-34`):
  ya recibe `pasada_id` como parámetro explícito. Se reutiliza tal cual para
  las asignaciones de recuento.
- **El diálogo «Sectores»** (`servidor/panel/app.js`, funciones
  `abrirSectores`/`guardarSectores`) y su dialog `#dialogo-sectores`
  (`index.html`): se reutilizan para la asignación dentro de la pestaña
  Recuento, parametrizando `pasada_id`.
- **`LifecycleEventEffect(ON_START)`** en `MainActivity.kt`: el mecanismo de
  refresco ya existe, se extiende para traer también la pasada activa.
- **`MIGRACION_2_3`** en `celular/.../datos/BaseLocal.kt`: el patrón a
  seguir para `MIGRACION_3_4`, con el procedimiento anotado contra la
  carrera de KSP en `docs/superpowers/deuda-conocida.md`.
- **`Hallazgo`** (`celular/.../Contador.kt`): sealed class con
  `Encontrado`/`Desconocido`, gana `FueraDePasada`.

## Decisiones ya tomadas, que no se reabren

1. **Pueden convivir varias pasadas abiertas a la vez.** No hay que cerrar
   el Conteo 1 para abrir un recuento.
2. **El celular bloquea**: solo acepta los SKU marcados de su pasada activa,
   cuando esa pasada es un recuento.
3. **Un operario nunca está en dos recuentos abiertos a la vez** — se
   impide al asignar, no se resuelve después.
4. **La anulación queda exenta del bloqueo de SKU.**
5. **El listado A RECONTAR de la pestaña arranca vacío.**
6. Fuera de alcance: cerrar un recuento individual sin cerrar la sesión, y
   un sonido distinto para "fuera de recuento".

---

## Tareas

Dos frentes: servidor+panel (T1–T10) y celular (T11–T17). El celular
depende del contrato acordado en la Fase B (T3–T6) pero no de la pestaña del
panel (T8–T10) — puede avanzar en paralelo con esa parte.

### Fase A — La base de la regla

**T1 — `servidor/app/repos/pasada_item.py`**
- [ ] Test: `agregar(con, pasada_id, articulo_ids)` inserta las filas sin
      duplicar (reintentar con los mismos ids no falla).
- [ ] Test: `es_parcial(con, pasada_id)` da `False` para una pasada sin
      filas y `True` para una con al menos una.
- [ ] Test: `contiene(con, pasada_id, articulo_id)` — presente y ausente.
- [ ] Test: `de_pasada(con, pasada_id)` devuelve la lista de `articulo_id`.
- [ ] Implementar las cuatro funciones.

**T2 — `sesiones.pasadas_abiertas` / `pasada_general_abierta` /
`pasada_activa_de_operario`**
- [ ] Test: `pasadas_abiertas` devuelve todas las abiertas de una sesión,
      ordenadas por número.
- [ ] Test: `pasada_general_abierta` devuelve la de número más bajo sin
      filas en `pasada_item`; `None` si no hay ninguna abierta que no sea
      un recuento.
- [ ] Test: `pasada_activa_de_operario` — con asignación en un recuento
      abierto, devuelve esa; sin ninguna, devuelve la general; sin
      ninguna de las dos, `ValueError` con mensaje claro.
- [ ] Implementar las tres, en `servidor/app/repos/sesiones.py`.

### Fase B — La regla en los puntos que deciden (dependen de A; independientes entre sí)

**T3 — `conteos.registrar`: resolución nueva + bloqueo de SKU**
- [ ] Test: un conteo en la pasada general de un artículo cualquiera sigue
      aceptándose igual que hoy.
- [ ] Test: un conteo en un recuento de un SKU marcado se acepta.
- [ ] Test: un conteo en un recuento de un SKU **no** marcado se rechaza
      con `EventoInvalido("Este artículo no está en el conteo actual",
      reintentable=False)`.
- [ ] Test: una anulación no pasa por el chequeo de bloqueo, aunque el
      artículo original no esté en `pasada_item`.
- [ ] Test: un operario sin pasada activa (caso límite: general cerrada,
      sin recuento asignado) recibe un error claro, no una excepción
      cruda.
- [ ] Implementar: `pasada = sesiones.pasada_activa_de_operario(con,
      sesion_id, operario_id)` reemplaza a `sesiones.pasada_abierta(...)`
      en la línea que hoy la usa; agregar el chequeo de `pasada_item`
      después de resolver el artículo, antes de insertar.

**T4 — `dispositivos.vincular`: resolución nueva + manejo del error**
- [ ] Test: vincular funciona igual que hoy cuando solo existe la pasada
      general.
- [ ] Test: vincular con un operario que tiene su pasada activa en un
      recuento devuelve los datos de esa pasada, no de la general.
- [ ] Test: el `ValueError` de `pasada_activa_de_operario` se traduce a un
      código de error explícito (409), no a un 500.
- [ ] Implementar.

**T5 — `asignaciones.de_operario_en_sesion`: resolución nueva + campos de
respuesta**
- [ ] Test: devuelve la pasada activa del operario (no necesariamente la
      general), con `pasada_id`, `pasada_numero`, `pasada_etiqueta`,
      `es_parcial`.
- [ ] Test: cuando `es_parcial` es `True`, incluye `articulos_permitidos`
      (lista de ids); cuando es `False`, lista vacía.
- [ ] Implementar. Actualizar `GET /api/dispositivo/mis-ubicaciones`
      (`servidor/app/api/dispositivos.py`) para exponer los campos nuevos.
      Actualizar `celular/contrato/mis-ubicaciones.json` y
      `capturar.py`/`test_contrato.py` para reflejar la forma nueva.

**T6 — `asignaciones.asignados_por_articulo` / `operarios_con_ubicaciones`
generalizadas**
- [ ] Test: `asignados_por_articulo` sigue devolviendo lo mismo que hoy
      cuando solo hay una pasada general (sin regresión).
- [ ] Test: con un recuento abierto, un artículo marcado para ese recuento
      y asignado ahí muestra a quien le toca en el recuento, no en la
      general.
- [ ] Test: `operarios_con_ubicaciones` sigue funcionando igual con una
      sola pasada.
- [ ] Implementar. Correr `test_tablero.py`/`test_reparto.py` completos:
      no deberían necesitar cambios (la firma pública no cambia).

### Fase C — Corrige el endpoint de asignación (depende de B)

**T7 — `PUT .../asignacion` exige `pasada_id` + valida exclusividad**
- [ ] Test: sin `pasada_id` en el cuerpo, 400.
- [ ] Test: asignar a la pasada general funciona igual que hoy (con
      `pasada_id` explícito en vez de resuelto solo).
- [ ] Test: asignar un operario a un recuento cuando ya tiene asignación
      en **otro** recuento abierto se rechaza con un mensaje que explica
      qué hacer.
- [ ] Test: reasignar dentro del **mismo** recuento (reemplazar sus
      ubicaciones) no se bloquea a sí mismo.
- [ ] Implementar en `servidor/app/api/panel.py` y
      `servidor/app/repos/asignaciones.py`.
- [ ] En el mismo commit: actualizar `servidor/panel/app.js`
      (`guardarSectores`) para mandar `pasada_id` explícito (el de la
      pasada general, obtenido de `GET /api/sesiones/{id}/pasadas`) — no
      dejar el panel roto entre este commit y el de la tarea T10.

### Fase D — La pestaña Recuento (depende de A, B, C)

**T8 — `sesiones.listar_pasadas` / `abrir_pasada` + endpoints**
- [ ] Test: `listar_pasadas` devuelve todas las pasadas de una sesión con
      etiqueta, estado, y si es general o recuento (`es_parcial`).
- [ ] Test: `abrir_pasada(con, sesion_id, articulo_ids)` crea la pasada
      siguiente y sus filas de `pasada_item`, todo en una transacción.
- [ ] Test: `abrir_pasada` con lista vacía de artículos, rechaza (400).
- [ ] Test: `abrir_pasada` sobre una sesión cerrada, rechaza.
- [ ] Implementar `GET`/`POST /api/sesiones/{id}/pasadas` en
      `servidor/app/api/panel.py`.

**T9 — `reparto.avance_de_pasada` + endpoint**
- [ ] Test: para una pasada de recuento, cuenta cuántos de sus SKU
      marcados ya tienen un conteo **con ese `pasada_id`** (no el vigente
      global), agrupado por operario asignado a esa pasada.
- [ ] Test: un SKU marcado sin ningún conteo en esa pasada cuenta como
      pendiente, aunque tenga un valor vigente de una pasada anterior.
- [ ] Implementar en `servidor/app/servicios/reparto.py` y
      `GET /api/sesiones/{id}/pasadas/{pasada_id}/avance` en `panel.py`.

**T10 — Panel HTML/CSS/JS**
- [ ] Test estático: pestaña `data-vista="recuento"` y sección
      `#vista-recuento` existen (`test_panel_estatico.py`, siguiendo
      `test_el_panel_tiene_la_pestana_de_reparto` como modelo).
- [ ] Test estático: los datos del servidor en la pestaña nueva están
      escapados (`esc(` en línea, para que el guardián los vea).
- [ ] Implementar: formulario de tolerancia; listado A RECONTAR con
      casillas (arranca vacío), «Seleccionar todos»/«Deseleccionar
      todos», buscador para sumar SKU fuera de A RECONTAR; botón «Abrir
      recuento»; tarjetas de recuentos abiertos con asignación (diálogo
      «Sectores» reutilizado) y avance.
- [ ] Verificar en el navegador: ver el flujo completo de punta a punta.

### Fase E — Celular (depende del contrato de la Fase B; en paralelo con D)

**T11 — `ContratoApi.kt`: campos nuevos**
- [ ] Test: `RespuestaMisUbicaciones` parsea `pasada_numero`,
      `pasada_etiqueta`, `es_parcial`, `articulos_permitidos` desde el
      contrato capturado en T5.
- [ ] Implementar en `celular/nucleo/.../ContratoApi.kt`.

**T12 — Room 3 → 4**
- [ ] Test de migración (`MigracionV4Test.kt`, calcado de
      `MigracionV3Test.kt`): los conteos y el maestro sobreviven, las
      columnas y la tabla nuevas existen.
- [ ] Implementar: `VinculacionEntidad.esParcial`, `ConteoEntidad.pasadaId`,
      `PasadaItemEntidad`, `PasadaItemDao`, `MIGRACION_3_4`.
      ⚠ Seguir el procedimiento contra la carrera de KSP: generar
      `schemas/4.json` compilando una sola variante antes de escribir la
      migración a mano.

**T13 — `Contador.buscar`: `Hallazgo.FueraDePasada`**
- [ ] Test: un código de un artículo que existe pero no está en
      `articulosPermitidos` (cuando la pasada es parcial) devuelve
      `FueraDePasada`, no `Encontrado`.
- [ ] Test: con pasada no parcial, cualquier artículo del maestro sigue
      devolviendo `Encontrado` igual que hoy.
- [ ] Implementar en `celular/app/.../Contador.kt`.

**T14 — `ListaAsignada.armar`: filtros nuevos**
- [ ] Test: conteos de una `pasadaId` distinta a la activa no suman en el
      tilde.
- [ ] Test: con pasada parcial, los artículos mostrados se acotan a
      `articulosPermitidos`.
- [ ] Test: con pasada no parcial, se muestran todos los asignados, como
      hoy (sin regresión).
- [ ] Implementar en `celular/nucleo/.../ListaAsignada.kt`.

**T15 — `ListaDeTrabajo`: wiring de los DAO nuevos**
- [ ] Test: arma la lista pasando la pasada activa y los permitidos desde
      `PasadaItemDao`/`VinculacionEntidad`.
- [ ] Implementar en `celular/app/.../ListaDeTrabajo.kt`.

**T16 — `PantallaMiLista`: etiqueta de pasada**
- [ ] Test: muestra la etiqueta de la pasada activa bajo el título.
- [ ] Implementar.

**T17 — `MainActivity.kt`: wiring final**
- [ ] `refrescarListaAsignada()` guarda también la pasada activa y relee la
      vinculación.
- [ ] El aviso de `Hallazgo.FueraDePasada` se muestra igual que "código
      desconocido", sin ofrecer alta.
- [ ] Sin test automatizado del estado (gap ya documentado en
      `deuda-conocida.md`) — verificación manual en celular real.

### Fase F — Publicación

**T18 — Verificación de punta a punta**
- [ ] Suite completa del servidor, `:nucleo:test`, `:app:testDebugUnitTest`.
- [ ] En el navegador: el flujo completo de la pestaña Recuento.
- [ ] En un celular real por USB: contar en el Conteo 1; reasignar a un
      recuento; confirmar que "Lo mío" cambia de etiqueta y de lista sin
      revincular; escanear fuera del recuento (aviso, no bloquea la app);
      escanear dentro (carga bien).
- [ ] Actualizar `README.md` y `docs/superpowers/deuda-conocida.md`.
