# La lista asignada en el celular y el avance por ubicación — diseño

Fecha: 2026-08-16

## El problema

Desde la rama anterior el responsable puede repartir ubicaciones entre
operarios: pestaña Operarios, botón «Sectores», y listo. Pero ese reparto no
llega a ningún lado.

El operario no se entera nunca. Abre la app y cae directo en la cámara, igual
que antes de que la función existiera. Camina el depósito escaneando lo que
aparece, sin lista, sin saber cuándo terminó lo suyo, y termina
preguntándole al responsable.

Y el responsable tampoco ve el reparto. El tablero le da el avance global —
«1.240 de 3.000» — pero no por ubicación ni por persona. Para saber si Juan
terminó P-3 tiene que filtrar por ubicación y contar filas a ojo.

O sea: hoy se puede repartir el trabajo, pero nadie puede *ver* el reparto.
Esta rama cierra las dos puntas.

## Lo que esto NO hace

**No frena nada.** Un operario sigue pudiendo contar cualquier cosa, esté o no
en su sector, exactamente como hoy. Se conversó bloquear —impedir contar
fuera de lo asignado, impedir que dos cuenten lo mismo— y se dejó afuera a
propósito: son decisiones grandes, con su propio diseño, y no tiene sentido
tomarlas antes de que alguien haya usado la lista en un depósito de verdad.

Esta rama es **solo mostrar**.

## Lo que este cambio revierte

Dos decisiones escritas en el código se dan vuelta acá. Quedan anotadas
porque el motivo por el que se tomaron sigue en pie, y quien lea esto dentro
de seis meses merece saber que no fue un descuido.

**1. `pantallaSegun` decía que no había menú.** Textual, en
`celular/app/.../ui/Pantalla.kt`:

> *«El operario abre la app para contar, no para ver un menú: si ya está
> vinculado, la cámara arranca sin que tenga que tocar nada.»*

Ahora hay una pantalla antes. El costo es real y no es teórico: quien cuenta
abre la app decenas de veces por día —se apaga la pantalla, atiende el
teléfono, la vuelve a abrir— y ahora suma un toque cada vez. Se acepta porque
la lista resuelve un problema más grande que el toque que cuesta, pero **hay
que mirarlo en un celular real antes de dar la rama por buena**. Si molesta,
la salida es recordar la última pantalla, que se evaluó y se descartó por
tener más estado que puede fallar.

**2. El diseño de asignación de sectores dejó afuera el celular.** En
`2026-08-15-asignacion-de-sectores-design.md`, bajo «Lo que queda afuera»,
está escrito que no se avisa nada en el celular. Esto no lo contradice del
todo —sigue sin haber bloqueo ni aviso al contar— pero sí lleva la asignación
al celular por primera vez, que era la puerta que ese diseño dejaba abierta.

## La pantalla de inicio del celular

Una pantalla nueva, entre la vinculación y el escaneo. Es donde la app abre
siempre.

Muestra las ubicaciones que le fueron asignadas al operario **en la pasada
abierta**, y dentro de cada una sus artículos. Por cada artículo:

| Qué | De dónde sale |
|---|---|
| `id_orden` | `articulo.idOrden` — el correlativo del maestro |
| SKU | `articulo.sku` |
| Descripción | `articulo.descripcion` |
| Código de barras | tabla `codigo` local; si hay varios, separados por coma |
| Unidad | `articulo.unidad` |
| Lo que contó | suma de sus conteos vigentes en la tabla `conteo` local |
| Tilde de contado | si esa suma existe |

Los artículos van **ordenados por `id_orden`**, que es el orden de recorrido
que define el maestro y el mismo que ya usa la planilla del operario y la
primera columna del tablero. No se inventa un orden nuevo.

Arriba de cada ubicación, su avance: **«P-3 — 12 de 40»**.

### Por qué todo sale de la base local

El tilde y la cantidad salen **exclusivamente de la base del celular**, no del
servidor. Es la decisión que hace que la pantalla sirva: en un depósito la
señal se corta a cada rato, y una lista que se pone en blanco cuando no hay
WiFi es peor que no tener lista. El celular ya tiene el maestro completo con
la ubicación de cada artículo y ya tiene sus propios conteos: alcanza.

### Un defecto viejo que esto destapa

`BaseLocal.vincularA` borra los conteos locales solo si **cambió la sesión**.
O sea: revincular el mismo celular con **otro operario dentro de la misma
sesión** deja los conteos del anterior en la base. Eso ya pasa hoy, pero es
invisible. Con el tilde deja de serlo: el operario nuevo va a ver tildado lo
que contó el otro.

Esta rama arregla la parte que le toca —limpia el reparto cuando cambia la
sesión **o** cuando cambia el operario— y anota el resto como deuda. Borrar
los conteos pendientes de otro operario perdería trabajo sin subir: es una
decisión propia, no un detalle de esta rama.

### El tilde habla solo de él

La consecuencia hay que decirla: **el tilde habla solo de lo que contó él.**
Si dos operarios comparten una ubicación, cada uno ve sin tilde lo que contó
el otro. Se aceptó porque con el reparto hecho cada uno tiene lo suyo, y
porque la alternativa —consultar al servidor— rompe justamente el caso que la
pantalla tiene que cubrir.

### La cantidad es la suma de los conteos vigentes

No es «el último conteo» ni «la cantidad del primer escaneo»: es la suma, y
descarta los anulados —tanto los que anulan a otro como los anulados por
otro— y los que el servidor rechazó. Un artículo escaneado en dos estantes de
la misma ubicación suma, que es como cuenta el resto del sistema.

**El `stock_sistema` sigue sin salir nunca al celular.** El operario ve lo que
él contó, nunca lo que el sistema dice que debería haber. El conteo sigue
siendo a ciegas.

### Sin ubicaciones asignadas

Lista vacía y un cartel: **«Todavía no te asignaron ninguna ubicación»**. El
botón de contar funciona igual — no se bloquea nada, y sin asignación el
operario puede contar cualquier cosa, como hoy.

Se descartó mostrarle el maestro completo: una lista de 3.000 artículos que no
son de nadie no le sirve a nadie, y tapa el hecho de que falta un paso del
responsable.

### Actualizar

Lo único que el celular no puede saber solo es **qué ubicaciones le tocan**.
Se piden al servidor:

- Cuando la app arranca y cuando vuelve del fondo.
- Cuando el operario toca **«Actualizar»**, porque el caso real es que el
  responsable se la cargue mientras él ya está en el depósito y le avise de
  viva voz.

Sin señal no pasa nada malo: queda la última lista que bajó. No es un error
que haya que mostrar — apenas un renglón discreto, «No se pudo actualizar. Se
muestra la última lista que bajó», nunca el texto crudo del servidor.

**La lista local se escribe solo con una respuesta exitosa.** Hay que
distinguir «pregunté y no tenés nada» de «no pude preguntar»: confundirlas le
borraría el reparto al operario cada vez que se aleja del router.

Las ubicaciones asignadas se guardan en una **tabla propia** de la base local,
no como una columna de `vinculacion`. `VinculacionDao.guardar` reemplaza la
fila entera, así que actualizar el reparto reconstruyendo esa fila podría
pisar la URL y el token y **desvincular el celular**. La vinculación es «quién
soy»; el reparto es logística de la pasada, que cambia varias veces por día.

Esto es una novedad de fondo: **hasta hoy el celular bajaba datos del servidor
una sola vez, al escanear el QR, y nunca más.** El maestro sigue funcionando
así; esta es la primera bajada repetida.

### Ir a contar y volver

Un botón grande **«Contar»** lleva a la pantalla de escaneo actual, sin
cambios: la cámara y el ingreso «A mano» quedan como están.

Se vuelve a la lista de dos maneras: con el **botón atrás de Android** y con
una **flecha visible arriba a la izquierda**. Las dos, porque la flecha de
Android es lo que cualquiera espera pero es invisible, y el que cuenta con
guantes y usa esto tres veces al año necesita verla.

El encabezado de escaneo ya está apretado —pasada, operario, «A mano»,
pendientes— y ya hay deuda anotada sobre nombres de operario largos
empujando el botón «A mano» fuera de la pantalla. **La flecha no puede
empeorar eso**; si hace falta, es el momento de acotar los textos con
`maxLines = 1` como dice esa nota.

## La pestaña «Avance por ubicación» en el panel

Una pestaña nueva junto a Tablero / Importar maestro / Operarios / Sesiones.

Se llama «Avance por ubicación» y no «Sectores» a propósito: el sistema ya usa
**«ubicación»** en todos lados —la columna del maestro, el filtro del tablero,
el «¿Dónde estaba?» del celular—, y meter una segunda palabra para la misma
cosa es exactamente lo que el diseño anterior evitó.

Es una **tabla plana, una fila por artículo**: ubicación, `id_orden`, SKU,
descripción, a quién le toca, quién lo contó, cuánto y estado. Con los mismos
filtros que el tablero de hoy, y exportable a CSV por el camino que ya existe.

Se eligió plana y no desplegable por ubicación porque es lo más parecido a lo
que el cliente ya sabe usar y lo que mejor se exporta, que es donde termina
todo inventario.

**«A quién le toca» y «quién lo contó» pueden ser varios.** El panel permite
asignar una ubicación a más de una persona, y un artículo lo pueden haber
contado dos. Se muestran separados por coma.

### Las ubicaciones sin dueño

La tabla muestra **todas** las ubicaciones del maestro, no solo las
repartidas. Las que nadie tiene asignadas salen con «Le toca a» vacío y
marcadas como **sin asignar**.

Esa es la fila más valiosa de la pestaña: avisa que hay un pasillo que nadie
va a contar **antes** de cerrar el inventario, en vez de descubrirlo después
como un montón de artículos en «SIN CONTAR» sin explicación.

## La API nueva

- **`GET /api/dispositivo/asignacion`** → `{"ubicaciones": ["P-3", "P-4"]}`.
  Solo nombres de ubicación. Como todo endpoint de dispositivo, no puede
  devolver `stock_sistema` ni `costo_unitario` — acá ni siquiera hay ocasión.
  Sin asignaciones devuelve **lista vacía con 200**: es una respuesta válida,
  no un error.
  Sin pasada abierta, en cambio, devuelve **409**. Hoy ese caso saldría como
  500 con traceback, porque `sesiones.pasada_abierta` tira `ValueError` y
  nadie lo ataja. Y no puede devolver lista vacía: sería mentira, y el celular
  la escribiría encima de la que tenía, borrándole el reparto al operario. El
  409 dice «ahora no puedo contestarte» y el celular conserva lo suyo.
  La respuesta va envuelta en un objeto y no como lista pelada por un motivo
  concreto: `forma()`, el comparador de `test_contrato.py`, devuelve el
  conjunto vacío para una lista de strings — un contrato que no fija nada.
- **`GET /api/sesiones/{id}/reparto`** — las filas de la pestaña nueva, con
  los mismos filtros que el tablero.
- La exportación entra por el endpoint que ya existe,
  `GET /api/sesiones/{id}/exportar/{tipo}`, sumando el tipo nuevo.

## Cómo se prueba

- **El endpoint del dispositivo**: con asignación, sin asignación, token
  inválido (401), sin sesión abierta (409), y el caso de la pasada faltante
  que hoy daría 500.
- **El armado de la lista del celular**, en `celular/nucleo` con tests
  unitarios: el orden por `id_orden`, la suma de conteos vigentes, el descarte
  de anulados y rechazados, varios códigos de barra en un artículo, sin
  ninguna ubicación asignada, y una ubicación asignada que ya no está en el
  maestro.
  Esto importa más de lo que parece: hoy casi nada de la lógica del celular se
  puede probar —está anotado en la deuda conocida desde hace varias ramas— y
  esta función se puede hacer bien de entrada en vez de dejarla adentro de un
  `@Composable`.
- **El servicio del reparto**, sin levantar el servidor: artículos sin
  ubicación, ubicaciones sin dueño, varios asignados, varios contadores,
  conteos anulados que no tienen que sumar.
- **La exportación**: que la columna nueva salga bien y que no rompa las dos
  exportaciones que ya existen.
- **El panel**, con los tests que ya existen: nada externo en el navegador y
  todo dato del servidor escapado. El guardián de escapado es una lista blanca
  por nombre de variable y **no ve las variables sueltas** (deuda conocida):
  escapar a mano igual.
- **En el navegador**: repartir ubicaciones, abrir la pestaña, filtrar,
  exportar el CSV y abrirlo en Excel.
- **En un celular real por USB** (no hay emulador): abrir la app y ver la
  lista, tocar «Actualizar» con WiFi y sin WiFi, contar un artículo y ver
  aparecer el tilde y la cantidad, volver con las dos formas, y probar con un
  nombre de operario largo que el encabezado no se rompa.

## Lo que queda afuera, a propósito

- **Bloquear el conteo fuera del sector asignado**, e **impedir que dos
  operarios cuenten el mismo artículo en la misma ubicación.** Las dos se
  conversaron en detalle y se dejaron para su propio diseño. Frenar tiene un
  costo que esta rama no paga: si la asignación está mal cargada, el operario
  queda parado hasta que alguien vaya a la PC.
- **Que el tilde sepa lo que contaron los demás.** Necesitaría consultar al
  servidor y rompería el funcionamiento sin señal, que es el caso normal.
- **Recordar la última pantalla al reabrir la app.** La app abre siempre en la
  lista: una sola regla, sin estado que persistir ni que pueda fallar.
- **Bajar el maestro de nuevo.** Sigue bajándose una sola vez, al vincular.
  Solo la asignación se actualiza sola.
