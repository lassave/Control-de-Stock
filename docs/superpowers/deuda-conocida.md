# Deuda conocida

Lo que se decidió no arreglar todavía, con el motivo. Sale de las revisiones
de cada rama: es lo que alguien ya miró, entendió y difirió a propósito.

Actualizado: 2026-08-15, al cerrar la rama de asignación de sectores.

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

**El encabezado se puede apretar con un nombre de operario largo.** El botón
«A mano» y el indicador de pendientes van en un `Row` sin peso al lado de
`pasada` y `operario`, así que un nombre inusualmente largo podría empujarlos
fuera de la pantalla —el único camino al ingreso manual—. No se verificó en
un celular real con un nombre largo; si aparece, la solución es acotar los
dos `Text` con `maxLines = 1` y `Modifier.weight(1f, fill = false)`.

**`fichaAbierta` es el nombre de una función y de un parámetro en el mismo
paquete.** La función pura vive en `ui/Pantalla.kt`; `PantallaEscaneo` tiene
un parámetro con el mismo nombre. Compila sin ambigüedad, pero es doble
sentido para quien lea `PantallaEscaneo.kt`. Conviene renombrar el parámetro
—por ejemplo a `hayFichaAbierta`— la próxima vez que se toque ese archivo.

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

## APK firmado

**El respaldo de `C:\clientes\claves\` es parte de la entrega.** Si se
pierde, ningún celular con la app instalada puede volver a actualizarse sin
desinstalar, y desinstalar borra los conteos que todavía no subieron. Lo
guarda Pablo (el desarrollador), en su gestor de contraseñas más una copia
de la carpeta completa fuera de esta máquina.

**Que la app avise sola cuando hay una versión nueva**, en vez de que
alguien tenga que ir a escanear el QR de instalación otra vez. Quedó afuera
a propósito, es la extensión natural de este plan.

**El control de escapado del panel es una lista blanca de nombres de
variable, no una que detecte el peligro.** `estado` se agregó porque la
revisión de esta rama lo encontró por señalamiento explícito en la
bitácora, no porque el test lo hubiera detectado solo. Cualquier
interpolación adentro de una plantilla con `<` que no pase por una de las
variables de la lista pasa sin auditar. Conviene invertirlo: auditar toda
interpolación adentro de una plantilla con marcado salvo que esté envuelta
en un escape explícito, y poner la lista blanca del lado de las
excepciones.

*(Instancia concreta, rama de asignación de sectores: `dibujarCasillaUbicacion`
interpola `ubicacion` —un nombre de ubicación del maestro, dato del
cliente— y el guardián no lo puede ver porque exige un prefijo tipo
`variable.algo`, y acá es una variable suelta. Está escapado a mano, bien,
pero el guardián no lo hubiera detectado si no lo hubiera estado.)*

**Nada conecta la ruta que escribe Gradle con la que lee Python.** El
nombre `servidor/app.apk` y `servidor/app.apk.txt` está escrito a mano en
`celular/app/build.gradle.kts` y en `servidor/app/api/panel.py`, en dos
lenguajes, sin ningún test que cruce los dos. Si `celular/` cambia de
lugar, `publicar` puede terminar escribiendo en una carpeta que nadie lee,
y el único síntoma es que el bloque de instalación no aparece. La tarea
`publicar` ahora verifica que la carpeta de destino sea la del servidor
(ver arriba), lo cual mitiga el síntoma pero no reemplaza una prueba real
de punta a punta.

## Asignación de sectores

**`GET /api/operarios` puede devolver 500 si una sesión abierta se queda sin
pasada abierta.** `asignaciones.operarios_con_ubicaciones` llama a
`sesiones.pasada_abierta` sin atajar el `ValueError` que tira si no hay
ninguna. Hoy es inalcanzable: `sesiones.crear` y `cerrar` abren y cierran
sesión y pasada juntas, atómicamente, y no hay otro código que toque
`pasada`. El reconteo (pasada 2, 3...) que el propio diseño de este plan
menciona como futuro es exactamente lo que abriría una ventana entre cerrar
una pasada y abrir la siguiente — y el radio de la falla es un endpoint
global, no algo acotado. Vale la pena un `try/except ValueError` que
devuelva listas vacías en vez de romper, cuando se construya el reconteo.

**La ubicación asignada se guarda recortada, pero la del conteo no.**
`asignaciones.reemplazar` hace `.strip()` a cada ubicación al guardar;
`conteos.registrar` compara la ubicación efectiva del conteo tal cual
llega, sin recortar. Hoy no muerde: el maestro ya viene recortado al
importarse, el alta rápida también, y el celular solo ofrece ubicaciones
que ya salieron recortadas del maestro. Pero `/api/dispositivo/conteos`
acepta `ubicacion_real` como texto libre, así que un cliente que no sea el
celular oficial —o un bug futuro ahí— podría mandar `" P-1 "` y marcarlo
fuera de asignación por un espacio. Un `.strip()` en `conteos.py` antes de
comparar lo cierra del todo.

**La asignación no valida que la ubicación exista en el maestro, ni que el
operario siga activo.** Es a propósito hasta cierto punto —la asignación es
logística libre, no un dato con reglas de negocio duras— pero asignar una
ubicación que no existe (typo, o quedó de un maestro viejo) marca fuera de
asignación *todos* los conteos futuros de esa persona en silencio, sin que
nadie se entere de por qué. Ninguno de los dos caminos es alcanzable desde
el panel hoy (el selector solo ofrece ubicaciones reales, y
`operarios_con_ubicaciones` ya filtra por activo), así que solo importa si
se agrega otra forma de escribir en `asignacion`.

**Un conteo anulado puede quedar con `fuera_asignacion = SI` en el CSV de
detalle.** Es correcto —el conteo, cuando se hizo, estaba fuera de lo
asignado— pero alguien que filtre el CSV solo por esa columna sin mirar
también `anulado` va a contar de más. El tablero no tiene este problema: la
consulta agregada ya excluye los conteos anulados antes de calcular la
marca.

## Textos

**El aviso de repetido da la hora pero no el día.** En un inventario que cruza
turnos, «a las 23:50» no distingue hace diez minutos de hace nueve horas.

**«Ese código ya estaba» se muestra en la franja roja de error**, cuando no
falló nada: el alta subió y el conteo entró.
