# Ingresar el código a mano — diseño

Fecha: 2026-08-15

## El problema

Hoy el único camino para contar un artículo es que la cámara lea su código de
barras. Cuando eso falla —una etiqueta rota, arrugada, o mal impresa, un
código que quedó tapado por otro producto— el operario no tiene forma de
seguir contando ese artículo salvo pedir ayuda.

## Cómo se activa

En el encabezado de la pantalla de escaneo, al lado del indicador de
pendientes, un botón de texto — **"A mano"** — siempre visible, con la misma
pinta que el indicador (`OutlinedButton`). Sin ícono: el proyecto no usa
íconos en ningún lado todavía, y sumar una librería de íconos para un solo
botón no se justifica.

Solo hace algo cuando no hay ya una ficha o un alta abiertos — la misma
ventana que hoy habilita la lectura de cámara (`hallazgo == null && altaDe ==
null`). Con una ficha abierta, tocarlo no hace nada: dos cosas pidiendo
atención a la vez es la clase de problema que este proyecto ya viene
evitando en otros lados (ver `docs/superpowers/deuda-conocida.md`).

## El diálogo

Al tocarlo se abre un cuadro modal: arriba un texto grande con lo tipeado
—como el visor de cantidad en la ficha del artículo—, abajo el **mismo
teclado numérico grande** que ya se usa para cargar cantidades
(`TecladoNumerico`, reutilizado tal cual). "C" borra todo, la flecha borra
el último dígito. La coma se ignora si la tocan: un código de barras no
lleva decimales.

Confirmar queda deshabilitado con el campo vacío. Cancelar cierra sin hacer
nada.

**Mientras el diálogo está abierto, la cámara se pausa.** Se suma como una
tercera condición a la misma regla que hoy pausa la cámara con una ficha
abierta, para que una lectura de cámara no le pise el código que el
operario está tipeando.

## Qué pasa al confirmar

El código escrito a mano entra **exactamente por el mismo camino que un
código leído por cámara** (`alLeer(codigo)`). No hay lógica de negocio
nueva ni duplicada:

1. `Contador.buscar()` lo busca contra el maestro.
2. **Si está**, se abre la ficha del artículo con sus datos —descripción,
   unidad, ubicación—, igual que con un código de cámara. Al confirmar la
   cantidad, si ya se había contado ahí, sale el mismo aviso de siempre
   («¿Ya lo contaste acá?»).
3. **Si no está**, aparece la misma franja roja y el mismo camino al alta
   rápida que ya existe para un código desconocido de cámara.

Ingresarlo a mano es, para el resto del sistema, una forma más de que
llegue un código — no un camino distinto. Esto es a propósito: cualquier
comportamiento que la app ya tenga bien probado para cámara (el timbre de
sonido, el aviso de repetido, el alta rápida) se hereda gratis, sin volver
a escribirlo ni volver a probarlo.

## Dónde vive

`fichaAbierta` pasa a ser una función pura —`fichaAbierta(hallazgo, altaDe,
ingresandoAMano): Boolean`— al lado de `pantallaSegun` y `hayQueAnunciar`
en `ui/Pantalla.kt`, que ya reúne las decisiones puras de la pantalla de
escaneo. Hoy esa combinación de estados se arma en línea dentro de
`MainActivity.kt`; sumar una tercera variable sin una función que la cubra
repetiría el patrón que ya causó tres defectos parecidos, documentado en
`docs/superpowers/deuda-conocida.md`.

El diálogo (`DialogoCodigoAMano`) va en su propio archivo,
`celular/app/src/main/kotlin/com/controldestock/ui/DialogoCodigoAMano.kt`,
siguiendo el mismo patrón de un archivo por ficha/diálogo que ya usa el
proyecto (`FichaDelArticulo.kt`, `FichaDeAlta.kt`, `PantallaVinculacion.kt`).
Vive aparte de `PantallaEscaneo` por el mismo motivo que `FranjaDeDesconocido`:
la pantalla monta la cámara real y CameraX no arranca sin celular, así que
adentro nada de ese archivo lo cubriría un test.

## Cómo se prueba

- **`fichaAbierta`**, función pura, sin Android: las ocho combinaciones de
  sus tres entradas.
- **`DialogoCodigoAMano`**, con Robolectric como el resto de la UI del
  proyecto: tipear arma el texto, "C" lo vacía, la coma no hace nada,
  confirmar queda deshabilitado con el campo vacío, confirmar con texto
  llama al callback con lo tipeado.
- **En el celular**: escribir un código que está en el maestro y ver que
  abre su ficha con los datos correctos; escribir uno que no está y ver la
  franja roja con el camino al alta; confirmar que mientras el diálogo está
  abierto, un código delante de la cámara no lo interrumpe.

## Lo que queda afuera, a propósito

- **Un aviso de "ya contado" que salga antes de abrir la ficha.** Se
  evaluó y se descartó: hoy ese aviso no existe en ningún lado de la app,
  ni para cámara ni para carga manual — sale al confirmar la cantidad,
  parejo para los dos orígenes. Adelantarlo sería una función nueva, sin
  pedido claro que la justifique todavía.
- **Validar el código contra un formato de código de barras** (largo fijo,
  dígito verificador de EAN/UPC). El maestro y la base local ya tratan el
  código como texto libre; agregar una validación de formato es un cambio
  de reglas de negocio que no pidió nadie.
