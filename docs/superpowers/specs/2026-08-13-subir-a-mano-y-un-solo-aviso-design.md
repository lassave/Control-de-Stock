# Subir a mano y un solo aviso por código — diseño

Fecha: 2026-08-13

Dos cambios chicos en la pantalla de escaneo, los dos salidos de usar la app
en el celular y no de leer el código.

## 1. Un código desconocido se anuncia una vez

### El problema

La cámara avisa una lectura por cuadro. Con un código que **está** en el
maestro eso no se nota: la ficha sube en la primera lectura y ahí el escaneo
se pausa. Con uno **desconocido** no se pausa nada: cada cuadro lo lee de
nuevo, vuelve a sonar el timbre y vuelve a reescribir la franja roja.
Apuntando quieto a la misma etiqueta es un zumbido continuo, varias veces por
segundo, hasta que el operario saca el celular de encima.

El timbre existe para avisar que pasó algo. Repetido veinte veces deja de
avisar y pasa a estorbar, y es lo primero que enseña a ignorarlo.

### La regla

Una lectura **no se anuncia** cuando es del mismo código que ya está en la
franja: no suena, no vibra y no se reescribe nada. La franja lo sigue
mostrando, así que no se pierde ninguna información — se pierde la
repetición.

Vuelve a anunciarse cuando el código es otro, o cuando la franja se limpió:
porque se leyó uno que sí está en el maestro, o porque el que estaba se dio
de alta.

Un código que **está** en el maestro se anuncia siempre. No hace falta la
excepción: al abrirse su ficha el escaneo se pausa solo.

### Dónde vive

La decisión —«¿hay que anunciar esta lectura?»— es una función pura que
recibe el hallazgo y el código que ya está en pantalla, y devuelve si
corresponde anunciar. Va al lado de `pantallaSegun`, que es la otra decisión
pura de pantalla que el proyecto ya tiene, y se prueba igual que ella: sin
celular, sin cámara y sin base.

## 2. El indicador de pendientes es el botón para subir

### El problema

Hoy la única forma de que suba lo que falta es **confirmar un conteo**: la
sincronización se dispara ahí, y el trabajo de fondo la reintenta recién cada
quince minutos. Un operario que terminó de contar y volvió a la zona con WiFi
no tiene cómo decir «subí lo que quedó»: tiene que inventarse un escaneo, o
esperar sin saber cuánto.

### La regla

El texto del encabezado que hoy informa pasa también a resolver. Toma forma
de botón, para que no haya que adivinar que se toca, y tiene cuatro estados:

| Estado | Qué muestra | Tocable |
|---|---|---|
| Nada pendiente | **Todo al día**, verde | no |
| Hay pendientes | **3 sin subir**, ámbar | sí |
| Subiendo | **Subiendo…** | no |
| No pudo | **No se pudo subir**, rojo | sí, reintenta |

Es el lugar donde el operario ya mira para saber si le falta algo: que sea
también donde toca para resolverlo ahorra una pantalla y un aprendizaje.

Usa la misma sincronización que ya corre después de cada conteo, así que
manda las altas antes que los conteos igual que siempre, con las mismas
reglas sobre qué se reintenta y qué se cierra.

**No bloquea nada.** Mientras sube, el operario puede seguir escaneando y
contando; lo que cargue en el medio entra en la vuelta siguiente. Un toque
mientras ya está subiendo no hace nada, con la misma guarda de reentrada que
el resto de la pantalla.

**El indicador refleja cualquier sincronización, no solo la que él pidió.**
La que se dispara sola al confirmar un conteo también lo pone en «Subiendo…».
Tener dos estados para lo mismo —uno para la automática y otro para la
manual— haría que el operario vea «3 sin subir» mientras esos tres están
viajando.

**El error, en cambio, es solo de la sincronización que él pidió.** Cada
conteo dispara una, así que contando sin señal —el caso normal del depósito—
todas fallan: si el error se mostrara igual, el indicador diría «No se pudo
subir» todo el tiempo, tapando el dato que el operario necesita —cuántos
lleva sin subir— para decirle algo que ya sabe, que no hay WiFi. Cuando la
subida la pidió él, el silencio sería lo malo: tocó un botón y tiene que
saber en qué quedó.

*(Esta regla salió de probarlo en el celular: el diseño original hacía que
cualquier sincronización mostrara el error, y contando sin señal el indicador
quedaba en «No se pudo subir» en vez de decir cuántos faltaban.)*

**El aviso de que no pudo dura hasta el intento siguiente**: se va cuando el
operario vuelve a tocar, o cuando una sincronización posterior termina. No se
limpia solo con el tiempo: si falló, que se vea que falló.

## Cómo se prueba

- **La función pura del anuncio**, sin Android: el mismo código no se
  anuncia; uno distinto sí; con la franja vacía sí; y uno que está en el
  maestro se anuncia siempre.
- **Los estados del indicador**, con la herramienta de Compose que el
  proyecto ya usa: que con pendientes sea tocable y llame a la
  sincronización, y que con cero no lo sea.
- **En el celular**: apuntar a un código desconocido y escuchar **un** timbre
  en vez de veinte; y con la WiFi cortada tocar el indicador para verlo
  avisar que no pudo, prenderla y tocar de nuevo para verlo terminar en «Todo
  al día».

## Lo que queda afuera, a propósito

- **Que suba solo al volver la señal.** Se puede agregar más adelante sin
  tocar nada de esto; el botón le da al operario el control que la
  automatización sola no da, sobre todo cuando falla.
- **Avisar de los conteos que el servidor rechaza.** Hoy desaparecen del
  contador sin que nadie los muestre: con tres pendientes y uno rechazado, el
  indicador termina en «Todo al día» y ese conteo se perdió en silencio. Es
  un hueco real y conocido, y es de «Mis conteos», que es la pantalla que
  existe para mostrarlos.
