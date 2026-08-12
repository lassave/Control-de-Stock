# Aviso de producto repetido en la misma ubicación — diseño

Fecha: 2026-08-12

## El problema

Así se cuenta en el depósito: un SKU se cuenta **una sola vez por
ubicación**. Todo lo que hay de ese producto en ese estante se cuenta junto
y se carga junto. Un segundo escaneo del mismo SKU en la misma ubicación no
es un estante nuevo: es que el operario perdió la cuenta de qué ya había
cargado, y si entra sin decir nada el inventario termina con unidades de más
que nadie va a poder explicar después.

Hoy la app hace lo contrario, y a propósito: dos escaneos del mismo artículo
son dos conteos que suman, porque **el mismo producto puede estar en dos
estantes**. Esa regla no se cae; se le pone un límite. Suman entre
ubicaciones distintas. Dentro de la misma ubicación, el segundo escaneo
pregunta antes.

## La regla

Al **confirmar** una carga, la app busca si ese mismo artículo ya tiene un
conteo en esa misma ubicación. Si lo encuentra, pregunta:

> **¿Ya lo contaste acá?**
> Ya cargaste 24 UN de este producto en P-1 a las 10:32. ¿Sumás otra carga?
>
> `Cancelar` `Cargar igual`

Es el mismo diálogo que ya usan los decimales: el operario no aprende nada
nuevo.

**Avisa, no bloquea.** Frenar el error cubre el 99% de los casos, pero
impedir la carga sería peor que el error: si el estante tenía dos pallets
separados, el operario sabe más que la regla, y sin forma de registrar lo que
ve termina anotando en un papel — que es exactamente lo que el sistema vino a
eliminar.

Si elige cargar igual, entra un conteo más y suman, como hasta ahora. **Nada
se pisa ni se reemplaza**: la regla de que nada se edita ni se borra sigue
intacta, y las dos cargas quedan visibles en el historial.

## Los detalles que definen el comportamiento

**Cuándo se pregunta.** Al confirmar, no al escanear. La ubicación recién es
definitiva ahí: el operario puede corregirla dentro de la ficha, y preguntar
antes sería preguntar sobre una ubicación que todavía puede cambiar.

**Qué se compara.** El mismo artículo, en la misma **ubicación efectiva**: la
corregida si el operario la corrigió, la del maestro si no. Un artículo sin
ubicación cuenta como «sin ubicación», que también se repite consigo misma.

**Contra qué conteos.** Los de este celular, en esta sesión, ya subidos o
pendientes por igual: que un conteo haya viajado no lo hace menos contado.
Los **rechazados** no cuentan: el servidor no los aceptó, así que nunca
entraron al inventario y avisar por ellos sería frenar al operario por algo
que no existe.

**Qué pasa al cancelar.** El aviso se cierra y la ficha queda como estaba,
con la cantidad puesta: desde ahí el operario corrige la ubicación, si el
producto estaba en otro lado, o cierra la ficha sin cargar nada.

**Vale también para el alta rápida.** El segundo escaneo del pack recién dado
de alta, en el mismo estante, avisa igual.

## Lo que la app no puede ver

El celular conoce **sus propios** conteos. Si otro operario cargó ese SKU en
esa ubicación desde su celular, este no se entera y no avisa.

Es una limitación aceptada, no un olvido. Preguntarle al servidor en cada
escaneo ataría el aviso a tener señal justo en ese momento, y en el rincón
sin WiFi habría que elegir entre frenar al operario o avisar a medias, que es
la peor combinación posible. El aviso cubre las repeticiones del propio
operario, que son la enorme mayoría porque cada uno cuenta su zona, y los
cruces entre operarios los muestra el panel, que ya marca los SKU contados
por más de uno.

## La hora

Es la primera vez que la app le muestra una hora al operario. Los conteos se
guardan en UTC, como todo en el sistema; el aviso la muestra en **hora
local**. Sin eso, en Argentina diría tres horas menos y el operario leería
que lo cargó alguien más, o que fue otro día.

La conversión vive junto al reloj, que es la única fuente del formato de
fecha de la app.

## Cómo se prueba

- **La decisión es una función pura**: recibe los conteos previos del
  artículo y la ubicación efectiva, y devuelve si hay repetido, con qué
  cantidad y a qué hora. Se prueba sin celular, sin base y sin red — incluidos
  los bordes: sin ubicación contra sin ubicación, ubicación corregida que
  esquiva el repetido, y el mismo artículo en dos ubicaciones distintas, que
  **no** tiene que avisar.
- **La consulta a la base**, con la base en memoria: que traiga los conteos
  de ese artículo, subidos y pendientes.
- **La pantalla**, con la herramienta de Compose: que el aviso salga al
  confirmar, que «Cargar igual» registre el conteo y que «Cancelar» no
  registre nada.
- **La hora local**, con un reloj fijo y una zona distinta de UTC: que el
  texto muestre la hora del depósito y no la de Greenwich.
- **En el celular de verdad**: escanear un producto, cargarlo, y escanearlo
  otra vez en el mismo lugar para ver el aviso; después corregirle la
  ubicación y comprobar que ahí no avisa.

## Lo que queda afuera, a propósito

- Ver los conteos de los otros operarios desde el celular.
- Reemplazar la carga anterior en vez de sumar. Corregir es anular, y eso
  llega con «Mis conteos».
- Avisar en la pantalla de escaneo, antes de abrir la ficha. La ubicación
  todavía no es definitiva ahí.
