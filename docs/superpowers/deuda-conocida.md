# Deuda conocida

Lo que se decidió no arreglar todavía, con el motivo. Sale de las revisiones
de cada rama: es lo que alguien ya miró, entendió y difirió a propósito.

Actualizado: 2026-08-13, al cerrar la rama del alta rápida.

## Al entregar

**El servidor se actualiza antes que los celulares.** Un celular con la app
nueva contra un servidor viejo trata el `400` de un cuerpo truncado como
«el servidor rechazó este artículo», y cierra el alta y sus conteos ante
cualquier corte de WiFi a mitad de envío. El servidor nuevo devuelve `422`
para ese caso y el celular lo reintenta. Mientras el orden dependa de que
alguien se acuerde, es una trampa: **el celular debería verificar la versión
del servidor al vincularse.**

## Pantalla de escaneo

**El estado tendría que ser un tipo cerrado, no tres variables sueltas.**
Hoy conviven `hallazgo`, `altaDe` y `codigoDesconocido`, y ya costaron tres
defectos de la misma familia: la app trabada con una ficha vacía, dos fichas
apiladas, y un alta abierta sin código. Cada uno se tapó por separado.
Un `Foco { Nada | Contando(hallazgo) | DandoDeAlta(codigo) }` los vuelve
imposibles en vez de improbables. Es lo primero que conviene hacer.

**El estado del escaneo no se puede probar.** Vive en las lambdas de un
`@Composable` privado que construye adentro la base, el contador y el
sincronizador, así que las guardas de reentrada y de lecturas tardías no las
cubre ningún test: se verifican a mano. Sacarlo a un objeto propio con
funciones suspend es lo que las haría probables.

**Quedan ventanas de un cuadro en las guardas de reentrada.** Las banderas se
liberan un instante antes de que la ficha se vaya de la pantalla, y Android
reparte el input antes de recomponer. Se cierran leyendo también el estado en
el toque, no solo la bandera.

**La cámara no ataja sus propios errores.** `VistaDeCamara` corre
`futuro.get()` y `bindToLifecycle` sin `try`: otra app con la cámara tomada,
o el permiso revocado desde Ajustes, cierran la app. Y la pantalla de escaneo
monta la cámara sin volver a mirar el permiso, que se pide una sola vez al
vincular. **Conviene atajarlo antes del APK firmado.**

## Alta rápida

**El aviso «Ese código ya estaba» no aparece en el caso central.** Se escribe
solo dentro de la confirmación de la ficha del alta, así que solo sale si el
alta se confirma con señal en ese momento. Un alta hecha **sin señal** —el
caso que la función existe para resolver— sube después por otro camino, y
ahí nadie escucha la respuesta del servidor. Verificado en el celular: el
dato queda bien y no se duplica nada; lo que falta es enterarse de que la
descripción que escribió el operario se descartó.

**Un alta rechazada por el servidor es indistinguible de un artículo normal.**
`estadoAlta` y `motivoRechazo` se escriben y no los lee nadie: el operario
sigue escaneando ese código, cuenta, y el conteo muere en el servidor uno por
uno como «código desconocido». Es de «Mis conteos».

**El código escaneado no es necesariamente el que se registra.**
`Hallazgo.Encontrado.codigo` no se lee nunca: el conteo viaja con el que
devuelve `codigoDe … LIMIT 1`. En un artículo con dos códigos de barras el
inventario cierra igual, pero no queda registrado cuál se leyó.

**Los conteos rechazados desaparecen del contador sin que nadie los muestre.**
Con tres pendientes y uno rechazado, el indicador termina en «Todo al día» y
ese conteo se perdió en silencio. También es de «Mis conteos».

## Base local del celular

**`borrarArticulos` y `borrarTodosLosArticulos` se llaman casi igual y hacen
cosas distintas** —una respeta las altas pendientes y la otra no—. Llamar a
la equivocada borra altas con conteos colgando. Los dos llamadores de hoy son
correctos; el riesgo es futuro.

**`porCodigo` usa `LIMIT 1` sin `ORDER BY`.** Si el maestro nuevo trae el
mismo código que un alta pendiente, cuál gana lo decide el plan de ejecución
de SQLite.

**Un alta rechazada pierde su motivo al reimportar el maestro**, junto con la
fila, antes de que el operario pueda verlo.

**Al reimportar quedan conteos apuntando a artículos que ya no están** —los de
las altas aceptadas—. No confunde identidades, pero «Mis conteos» no va a
saber de qué artículo eran.

## Servidor

**Los endpoints del panel no atajan un cuerpo JSON ilegible.** Los del
dispositivo sí, desde la rama del alta rápida: un cuerpo truncado devuelve
`422`. Los del panel siguen dejando subir la excepción cruda, o sea 500 con
traceback. El panel es nuestro propio JavaScript, así que hoy no pasa.

**`/api/dispositivo/conteos` no verifica que el cuerpo sea un objeto**: un
array JSON válido da 500. El de altas sí lo cubre.

**La carrera de KSP con los esquemas de Room.** `debug` y `release` escriben
en el mismo directorio: la primera corrida después de subir la versión de la
base falla con un error de deserialización que no dice nada de la causa. Va a
morder en la versión 3.

## Textos

**El aviso de repetido da la hora pero no el día.** En un inventario que cruza
turnos, «a las 23:50» no distingue hace diez minutos de hace nueve horas.

**«Ese código ya estaba» se muestra en la franja roja de error**, cuando no
falló nada: el alta subió y el conteo entró.
