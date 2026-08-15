# Mostrar los códigos de barra en el tablero — diseño

Fecha: 2026-08-15

## El problema

El maestro guarda el código o los códigos de barra de cada artículo —en la
tabla `codigo_barras`—, pero hoy no se ven en ningún lado del panel: ni en
el tablero, ni en la exportación. Para saber con qué código está cargado un
SKU hay que abrir la base a mano.

## Un artículo puede tener más de un código

La tabla `codigo_barras` no impone un límite: un artículo nace con uno —el
que trae el maestro, o el SKU si no viene ninguno— pero puede sumar otros
después, por un reimport del maestro con un código distinto para el mismo
SKU, o por un alta rápida que reutiliza un código ya asociado a otro
artículo. Este diseño los muestra todos, no solo el primero: esconder
códigos en la pantalla principal es justo donde alguien los necesitaría
para resolver un duplicado.

## Dónde se ve

- **El tablero**: una columna nueva, **"Códigos de barra"**, al lado del
  SKU —son las dos formas de identificar el mismo artículo—. Con más de
  uno, se muestran todos juntos separados por `, `.
- **La exportación de resumen por SKU**: la misma columna, en la misma
  posición, con el mismo formato.
- **La exportación de detalle no la lleva.** Es una fila por escaneo, y
  ningún escaneo guarda cuál código particular se leyó —la tabla `conteo`
  no tiene ese dato—. Mostrar los códigos del artículo ahí repetiría el
  mismo valor en cada fila del mismo SKU sin agregar nada que el resumen
  no diga ya.

## Cómo se calcula

Una subconsulta agregada, con el mismo patrón que ya usa `tablero.py` para
concatenar las observaciones de un artículo, con un `ORDER BY` explícito
por el orden de carga: sin eso, el orden de los códigos podría cambiar
entre una consulta y la siguiente sin que nadie lo pidiera. Un artículo sin
ningún código —caso raro, pero la tabla lo permite— muestra la columna
vacía, no rompe nada.

## Lo que ya existe y no se toca

**`codigo_aprendido`** es otra tabla del esquema sin ningún código que la
use, pensada —a juzgar por sus columnas— para recordar códigos entre
sesiones. Resuelve un problema distinto del que pide este diseño y queda
afuera a propósito: no es "mostrar los códigos que ya existen", es "que un
código aprendido en una sesión sobreviva a la siguiente". Se anota acá para
que quede visible, no para resolverla ahora.

## Cómo se prueba

- **`tablero.py`**: un artículo con un código trae ese código; con dos
  códigos los trae en el orden en que se cargaron, separados por `, `; sin
  ningún código no rompe la fila.
- **La exportación de resumen**: la columna nueva sale con el valor
  correcto; la de detalle no cambia.
- **El panel**, con los tests de escapado que ya existen: el código de
  barras se escribe escapado, como cualquier otro dato que viene del
  maestro.
- **En el navegador**: importar un maestro, ver la columna en el tablero,
  exportar el resumen y confirmar que el CSV la tiene.

## Lo que queda afuera, a propósito

- **`codigo_aprendido`**, ver arriba.
- **Editar o agregar códigos desde el panel.** Hoy los códigos entran por
  el maestro o por el alta rápida del celular; agregar una forma de
  cargarlos a mano desde el panel es una función distinta, sin pedido
  todavía.
- **Mostrarlos en la exportación de detalle**, ver arriba.
