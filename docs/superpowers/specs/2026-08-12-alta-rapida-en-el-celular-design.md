# Alta rápida de códigos desconocidos en el celular — diseño

Fecha: 2026-08-12

## El problema

El operario escanea un producto y el código no está en el maestro. Hoy la
app suena distinto y muestra una franja roja: se entera de que ese producto
no se puede contar, y nada más. En un inventario real esto pasa seguido —el
pack por seis, el código del proveedor, la etiqueta vieja, el producto que
entró después de exportar el maestro— y cada uno es una unidad que queda sin
contar.

El servidor ya sabe resolverlo: `POST /api/dispositivo/articulos` crea el
artículo en la sesión con `origen = alta_rapida` y le asocia el código
escaneado, y si ese código ya identifica a un artículo devuelve ese en vez
de duplicarlo. El cliente HTTP del celular ya tiene el método
(`ClienteServidor.altaRapida`) con sus tests. **Falta la pantalla y lo que
la sostiene.**

## Lo que manda sobre todo el diseño

El servidor **rechaza definitivamente** un conteo cuyo código no conoce
(`Código desconocido`, `reintentable = false`). No hay reintento que lo
salve. Por eso el artículo tiene que llegar al servidor **antes** que sus
conteos, y por eso el orden de la sincronización es parte del diseño y no un
detalle de implementación.

## Alcance

**Entra:** dar de alta un código desconocido como artículo nuevo, con su
cantidad, desde el celular, con o sin señal.

**No entra:** vincular el código escaneado a un artículo que ya está en el
maestro. Buena parte de las altas rápidas son eso —el pack por seis de algo
que ya existe— pero se resuelve después desde el panel, con el buscador que
ya está previsto. Hacerlo desde el celular necesitaría un endpoint nuevo y
un buscador en la app; queda para más adelante.

## 1. Lo que ve el operario

La franja roja de una lectura desconocida suma un botón **«Darlo de alta»**.

Dar de alta es un acto deliberado: la ficha **no se abre sola**. Un código de
barras mal leído, o el de la caja en vez del producto, también llega como
desconocido; si cada lectura rara creara un artículo, el inventario se
llenaría de fantasmas que alguien tiene que limpiar después.

La ficha de alta es la del artículo conocido con el código escaneado arriba,
en grande, para confirmar que es ese, y estos campos:

| Campo | Cómo se completa |
|---|---|
| Descripción | A mano. **Obligatoria**: sin ella no hay alta, y el servidor también la exige. |
| Unidad | De la lista que bajó con el maestro. `UN` puesta de entrada. |
| Ubicación | El mismo selector de la ficha (buscar entre las del maestro, o escribir otra). |
| Cantidad | El mismo teclado grande de siempre, con las mismas reglas de carga. |

Al confirmar: golpecito corto y vuelta a la cámara, igual que un conteo
normal. Cancelar no crea nada.

El teclado numérico y el selector de ubicación viven hoy adentro de
`FichaDelArticulo`. Salen a su propio archivo para que las dos fichas los
compartan.

## 2. Lo que se guarda en el celular

El alta crea **un artículo local de verdad** —con su fila en `codigo`— y el
conteo de siempre, todo en una transacción. Que el artículo exista localmente
es lo que hace que el segundo escaneo del mismo pack muestre su ficha normal
en vez de volver a decir «desconocido»; en una estantería de packs iguales
eso se repite diez veces seguidas.

`ArticuloEntidad` suma dos columnas:

- **`estadoAlta`** — vacía si el artículo vino del maestro; `PENDIENTE`,
  `ENVIADO` o `RECHAZADO` si nació en el celular. Con eso, «lo que falta
  crear en el servidor» son los artículos con la columna en `PENDIENTE`, sin
  una tabla aparte que haya que mantener en sincronía con esta.
- **`motivoRechazo`** — por qué el servidor no lo aceptó, para que el
  operario pueda verlo.

**El id provisional no se persigue.** El artículo local nace con un id que no
existe del otro lado, y así se queda. El conteo viaja con el código de
barras, nunca con el id, así que al celular no le hace falta enterarse del
número que le puso el servidor: perseguirlo obligaría a reescribir la clave
primaria y todo lo que la referencia, a cambio de nada. Cuando se baje el
maestro de nuevo, el artículo llega con su id real y el provisional se
descarta.

**Al reemplazar el maestro se conservan las altas todavía pendientes.** Si se
borraran, quedarían conteos de un código que ya no existe en la base local, y
el servidor los rechazaría para siempre.

## 3. Cómo sube

En cada sincronización: **primero las altas, después los conteos**. En la
misma corrida, así un alta que entra deja viajar sus conteos atrás sin
esperar a la próxima vuelta.

| Qué pasa | Qué hace la app |
|---|---|
| No hay red | No viaja nada. Todo sigue pendiente, como hoy. |
| El servidor acepta el alta | Queda `ENVIADO`; sus conteos entran en el mismo envío. |
| El servidor rechaza el alta para siempre | El alta queda `RECHAZADO` con su motivo, **y los conteos de ese código quedan `RECHAZADO` con ese mismo motivo**. |
| El código ya existía (`creado: false`) | No es error: el alta queda `ENVIADO` y los conteos entran. |

Un alta que no pudo subir **retiene solamente a los conteos de su propio
código**. Todo lo demás viaja igual: el operario contó cincuenta artículos
del maestro y uno nuevo, y los cincuenta no tienen por qué esperar a que se
resuelva el que falta.

**Por qué los conteos se cierran con el alta.** Si el servidor no va a
aceptar el artículo —una unidad que no está en su catálogo, la sesión
cerrada— sus conteos no van a poder entrar nunca. Dejarlos pendientes deja la
cola girando para siempre, quema batería y red, y el indicador de «sin subir»
pasa a mentir. Es exactamente la trampa que ya resolvieron las anulaciones
huérfanas, entrando por otra puerta, y se resuelve en el mismo lugar:
`PlanDeSincronizacion`, que es lógica pura y se prueba en milisegundos.

**Cuando el código ya existía.** Puede ser que otro operario lo diera de alta
hace un minuto, o que coincida con el SKU de un artículo del maestro. El
conteo entra igual, contra el artículo que ya estaba. Si el operario todavía
está mirando —hubo señal en el momento— la franja le avisa **«Ese código ya
era: Tornillo»**, que es información y no un error. La descripción que
escribió se descarta: manda la del servidor, y el celular la corrige la
próxima vez que baje el maestro.

## 4. La migración de la base

La base local está en la versión 1 y se construye sin migraciones: agregarle
una columna sin más la haría explotar al abrirse. Sube a la **versión 2** con
una migración que solo agrega las dos columnas.

Nada de borrón y cuenta nueva. Un operario que actualiza la app en medio de
un inventario perdería los conteos que todavía no subió, que es justo lo que
la base local existe para proteger.

## 5. Cómo se prueba

- **Lógica pura**, en `PlanDeSincronizacion`, sin Android: qué altas se
  mandan, qué conteos quedan retenidos detrás de un alta pendiente, y qué
  conteos se cierran cuando un alta se rechaza.
- **La creación local**, con la base en memoria: que el alta deje artículo,
  código y conteo, y que el segundo escaneo del mismo código lo encuentre.
- **La subida**, con el servidor simulado: el orden —alta antes que conteo—,
  el rechazo definitivo que arrastra los conteos, el `creado: false`, y el
  corte de red que no pierde nada.
- **La pantalla**, con la herramienta de Compose que ya está: que sin
  descripción no deje confirmar.
- **La migración**, que es la que puede arruinarle el día a alguien: abrir una
  base de la versión 1 con conteos sin subir, migrarla y verificar que siguen
  ahí. Requiere guardar los esquemas de la base en el repo, hoy apagados.
- **En el celular de verdad**: escanear algo que no esté en el maestro, darlo
  de alta **sin señal**, comprobar que el segundo escaneo ya lo encuentra,
  prender la WiFi y ver el artículo aparecer en el tablero marcado como alta
  rápida.

## Lo que queda afuera, a propósito

- Vincular un código desconocido a un artículo del maestro desde el celular.
- Editar o borrar un alta ya hecha desde el celular. Nada se edita ni se
  borra: la corrección es una anulación, y eso llega con «Mis conteos».
- Avisar en el celular que otro operario dio de alta el mismo producto
  mientras tanto, más allá del aviso del momento.
