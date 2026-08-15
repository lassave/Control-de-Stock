# Asignar sectores a cada operario — diseño

Fecha: 2026-08-15

## El problema

Hoy nadie puede decirle a la app "a Juan le toca el Depósito A, a María el
B": cada operario cuenta lo que va apareciendo frente a la cámara, sin que
el responsable pueda repartir el trabajo ni enterarse después si alguien
contó fuera de lo que le tocaba.

## Lo que ya existía y no se usaba

La base de datos **ya tiene** una tabla `asignacion` (pasada, operario,
ubicación) y una columna `conteo.fuera_asignacion` — pero ningún código las
usa: `fuera_asignacion` se graba siempre en `0`. El modelo estaba pensado y
nunca se terminó de construir encima. Este diseño completa esa idea.

## Qué significa "sector" acá

El proyecto ya usa la palabra **"ubicación"** para esto en todos lados: la
columna `ubicacion` del maestro, el filtro "Todas las ubicaciones" del
tablero, el selector "¿Dónde estaba?" del celular. Se sigue usando
"ubicación" acá también, para no meter una palabra nueva para lo mismo. Las
ubicaciones que se pueden asignar son las que ya trae el maestro de la
sesión abierta.

## Qué hace la asignación

Es informativa con rastro, no un bloqueo. Un operario puede contar
cualquier cosa; si cuenta algo de una ubicación que no es la suya, el
conteo se guarda igual, pero queda marcado como fuera de asignación para
poder revisarlo después. Nada se frena en el momento.

## Cuándo se puede asignar

La tabla `asignacion` está atada a una **pasada** (un "Conteo N" dentro de
una sesión), no a la sesión entera. Si se abre un reconteo (Conteo 2),
arranca sin nadie asignado: un reconteo suele existir justamente para que
otra persona revise el sector de alguien más, así que copiar la asignación
vieja repetiría el problema que el reconteo busca corregir.

**La asignación solo tiene sentido con una sesión abierta.** Sin sesión
abierta no hay pasada a la cual asignar nada, así que en la pestaña
Operarios no aparece la forma de asignar.

## Cómo se calcula "fuera de asignación"

Se calcula **una sola vez, al guardar el conteo** — no se recalcula cada
vez que se mira el tablero. Es coherente con "nada se edita ni se borra":
un conteo es un hecho que ya pasó, y si más tarde cambia a quién le toca
cada ubicación, los conteos viejos no cambian de opinión con efecto
retroactivo. Solo lo que se cuenta de ahí en más se juzga con la asignación
vigente en ese momento.

La regla exacta, evaluada en `conteos.registrar`:

1. Se determina la ubicación efectiva del conteo: `ubicacion_real` si el
   operario corrigió, si no la `ubicacion` del artículo.
2. Si esa ubicación efectiva es `NULL` (el artículo no tiene ubicación
   conocida y el operario no corrigió ninguna), **no se marca nada**: no
   hay con qué comparar.
3. Si el operario no tiene ninguna fila en `asignacion` para esa pasada,
   **no se marca nada**: sin asignación no hay restricción. Si se marcara
   todo, el tablero se llenaría de avisos el primer día que se usa la
   función, antes de terminar de repartir sectores a todo el equipo.
4. Si el operario tiene asignaciones y la ubicación efectiva **no** está
   entre ellas, el conteo se graba con `fuera_asignacion = 1`.

## Dónde se ve

Dos lugares, porque son dos preguntas distintas:

- **En el tablero principal.** Un artículo con algún conteo fuera de
  asignación en su pasada vigente muestra una marca al lado del estado —
  el mismo tratamiento que ya tiene "posible error de carga": un ícono con
  el detalle al pasar el mouse. Si el mismo artículo lo contaron dos
  personas y una estaba fuera de asignación, el artículo queda marcado
  igual: es una señal de "hay algo para revisar acá", no un desglose
  conteo por conteo.
- **En la exportación de detalle** (el CSV existente, una fila por
  escaneo, con operario y ubicación). Columna nueva `fuera_asignacion`
  (`SI` o vacío), al lado de `anulado`. Ahí se ve exactamente quién, cuándo
  y en qué ubicación — el tablero solo avisa que hay algo para mirar, el
  detalle contesta la pregunta.

## La asignación en la pestaña Operarios

Al lado de cada operario, un enlace **"Sectores"** que abre un cuadro
(`<dialog>` nativo del navegador, sin librerías) con la lista de
ubicaciones del maestro actual, cada una con su casilla — tildadas las que
ya tiene asignadas. Se guardan todas juntas al cerrar el cuadro, con un
solo pedido al servidor con la lista completa, no una llamada por casilla.

Sin sesión abierta, ese enlace no aparece.

## La API nueva

- `GET /api/ubicaciones` — las ubicaciones distintas del maestro de la
  sesión abierta, ordenadas. Hoy el tablero arma su propio filtro con lo
  que ya bajó al navegador; esta es la primera vez que hace falta pedirlas
  aparte, porque la pestaña Operarios no carga el tablero. Lista vacía si
  no hay sesión abierta.
- `GET /api/operarios` — gana un campo `ubicaciones_asignadas` por
  operario: la lista de ubicaciones que tiene asignadas en la pasada
  abierta, o `[]` si no hay sesión abierta o no se le asignó nada.
- `PUT /api/operarios/{id}/asignacion` — reemplaza la lista completa de
  ubicaciones asignadas a ese operario en la pasada abierta. Cuerpo:
  `{"ubicaciones": ["Depósito A", "Depósito B"]}`. Sin sesión abierta,
  devuelve un error explicando que hace falta una sesión abierta.

## Cómo se prueba

- **El repositorio de asignaciones**: guardar, reemplazar por completo,
  listar por operario y pasada; que una pasada nueva arranque vacía aunque
  la anterior tuviera asignaciones.
- **El cálculo de `fuera_asignacion`** en `registrar()`: con asignación y
  ubicación coincidente (no se marca), con asignación y ubicación distinta
  (se marca), sin ninguna asignación (no se marca), sin ubicación conocida
  en ningún lado (no se marca).
- **El tablero**: un artículo con un conteo fuera de asignación en la
  pasada vigente aparece marcado; conteos de una pasada anterior no
  contaminan la marca de la pasada vigente.
- **La exportación de detalle**: la columna nueva sale con el valor
  correcto fila por fila, y no rompe la exportación de resumen.
- **El panel**, con los tests de escapado y estructura que ya existen:
  todo dato que venga del servidor —nombres de ubicación incluidos— se
  escribe escapado.
- **En el navegador**: asignar ubicaciones a un operario, contar con el
  celular fuera de lo asignado, ver la marca en el tablero y en el CSV
  exportado.

## Lo que queda afuera, a propósito

- **Bloquear o avisar en el celular.** Se evaluó y se descartó: el
  operario cuenta a ciegas y sin trabas; frenar un conteo válido por una
  asignación mal cargada sería peor que no tener la función. Queda la
  puerta abierta a hacerlo más adelante, con su propio diseño.
- **Copiar asignaciones entre pasadas.** Cada pasada arranca sin nadie
  asignado, a propósito (ver arriba).
- **Restringir qué ubicaciones puede corregir el celular** al guardar un
  conteo. El selector "¿Dónde estaba?" sigue mostrando todas las
  ubicaciones del maestro, no solo las asignadas al operario: limitarlo
  bloquearía a alguien que cubre a otro compañero por un motivo válido, el
  mismo argumento por el que se descartó bloquear el conteo.
