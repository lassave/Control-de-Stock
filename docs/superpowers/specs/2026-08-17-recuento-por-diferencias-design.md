# Recuento por diferencias — diseño

Fecha: 2026-08-17

## El problema

El diseño original del proyecto (día 1,
`docs/superpowers/specs/2026-08-10-control-de-stock-design.md`) ya describía
esta función con bastante detalle: al cerrar el Conteo 1, el panel lista las
diferencias fuera de tolerancia; se marcan los SKU a recontar —a mano, o de
una tomando todos los que quedaron en estado `A RECONTAR`—; se abre el
Conteo 2; y durante ese recuento parcial el celular **solo acepta los SKU
marcados**, avisando y sin cargar si el operario escanea otra cosa.

Nunca se construyó. La tabla `pasada_item` (`pasada_id, articulo_id`) existe
en el esquema desde ese primer día, sin una sola línea de código que la use
en ningún repo, servicio o endpoint — es groundwork muerto, exactamente como
lo fue `asignacion` antes de la rama de asignación de sectores.

## Lo que el cliente pidió, y por qué es más grande de lo que parece

Una pestaña nueva en el panel con: el listado de SKU con diferencias, un
campo de tolerancia, y la posibilidad de asignar esos SKU por ubicación a un
operario para recuento.

Tres decisiones tomadas con el cliente durante el diseño hacen que esto sea
más ambicioso que el diseño original de 2026-08-10 y que la rama de
asignación de sectores ya en producción:

1. **Pueden convivir varias pasadas abiertas a la vez** en una misma sesión.
   No hace falta cerrar el Conteo 1 para abrir el Conteo 2 — a diferencia
   del diseño original, que sí las hacía secuenciales.
2. **El celular bloquea de verdad**: durante un recuento, solo acepta
   contar los SKU marcados para esa pasada. Es fiel al diseño original,
   pero nunca se había implementado —ni el bloqueo, ni nada que lo
   sostenga—.
3. **El celular tiene que enterarse de en qué etapa está**, sin que el
   operario tenga que volver a escanear el QR de vinculación, y sin que un
   tilde de "ya contado" de una pasada vieja contamine la pasada nueva.
   Cita textual del cliente: *"cuando haya más de 1 recuento el celular
   tiene que entender que se vuelve a contar en una nueva etapa."*

Esto rompe una suposición que hoy está en el corazón de todo el sistema: que
existe **"la" pasada vigente** de una sesión. `sesiones.pasada_abierta` y
`sesiones.ultima_pasada` (`servidor/app/repos/sesiones.py`) resuelven las dos
con `ORDER BY numero DESC LIMIT 1` — con una sola pasada nunca importó cuál
de las dos se usaba; con varias abiertas a la vez, dejan de significar lo
mismo. Hace falta saber **en qué pasada está trabajando cada operario en
particular**, y esa pregunta toca el punto más sensible de todo el sistema:
`conteos.registrar`, la función que decide a qué pasada pertenece cada
conteo que llega.

**Lo que ya funciona y no hay que tocar:** `servidor/app/servicios/tablero.py`
calcula el valor vigente de cada artículo agrupando por `articulo_id` con
`MAX(pasada_numero)` — opera sobre `conteo.pasada_id`, que siempre queda bien
grabado en cada fila sin importar cuántas pasadas estén abiertas al mismo
tiempo. El tablero ya estaba listo para esto, sin saberlo.

## La regla: "pasada activa de un operario"

Reemplaza el uso de `pasada_abierta`/`ultima_pasada` en los puntos que
**deciden** algo — no en los puramente informativos, como mostrar una fecha.

1. Si el operario tiene una fila en `asignacion` dentro de una pasada
   abierta que sea un recuento (tiene filas en `pasada_item`), **esa** es su
   pasada activa.
2. Si no tiene ninguna, la **pasada general** abierta: la de número más bajo
   que no es un recuento (hoy, mientras esté abierta, siempre el Conteo 1).
3. Si no existe ninguna de las dos —la general se cerró y el operario no
   está en ningún recuento abierto—, error explícito. No se lo mete en una
   pasada que no le corresponde.

**Un operario nunca está en dos recuentos abiertos a la vez.** Esto se
**impide al momento de asignar**, no se resuelve después comparando números:
el mismo endpoint que asigna ubicaciones para un recuento rechaza la
asignación si ese operario ya tiene algo asignado en **otra** pasada de
recuento abierta, con un mensaje que le dice al responsable que lo
desasigne ahí primero. Esta restricción simplifica la regla de arriba: no
hace falta ningún criterio de desempate, porque el empate no puede llegar a
existir.

**La anulación queda exenta del bloqueo de SKU.** Anular no agrega cantidad
a un SKU bloqueado —solo cancela algo que ya estaba cargado—, así que
bloquearla le impediría a un operario corregir un error viejo justo cuando
se le abre un recuento nuevo, sin ningún beneficio real a cambio.

## El bloqueo de SKU fuera del recuento

**Servidor.** En `conteos.registrar`, después de resolver la pasada activa
del operario: si esa pasada tiene filas en `pasada_item` (es un recuento) y
el artículo escaneado no está entre ellas, se rechaza con
`EventoInvalido("Este artículo no está en el conteo actual", reintentable=False)`
— el mensaje es literal al del diseño original de 2026-08-10. Las
anulaciones no pasan por este chequeo, por lo explicado arriba.

**Celular.** Bloquea localmente, sin ida y vuelta al servidor —el conteo es
offline-first y esto no puede ser la excepción—. `Contador.buscar` gana un
tercer resultado, donde hoy solo existen `Encontrado` y `Desconocido`:
`Hallazgo.FueraDePasada(codigo, descripcion)`, cuando el artículo existe en
el maestro pero no está en el conjunto de SKU permitidos que el celular ya
tiene guardado localmente. Se muestra igual que "código desconocido" hoy —un
aviso, sin bloquear la pantalla— pero **sin** ofrecer "Darlo de alta": el
artículo existe, simplemente no toca en esta pasada.

`/api/dispositivo/mis-ubicaciones` se extiende para traer, además de las
ubicaciones asignadas, el estado de la pasada activa del operario:
`pasada_numero`, `pasada_etiqueta`, `es_parcial`, y `articulos_permitidos`
—ids internos de artículo, no es stock ni costo, no rompe el conteo a
ciegas—. Vacío + `es_parcial=false` sigue significando "sin restricción",
como hoy.

## Cómo el celular se entera del cambio de etapa

Ningún mecanismo nuevo: se aprovecha el que ya existe para el reparto de
ubicaciones —`LifecycleEventEffect(ON_START)` en `MainActivity.kt`, más el
botón «Actualizar»—. `refrescarListaAsignada()` pasa a guardar también la
pasada activa del operario, no solo sus ubicaciones, y a releer la
vinculación local después de guardar.

**Room sube de versión 3 a 4.** Mismo procedimiento ya documentado contra la
carrera de KSP entre `debug` y `release` (generar primero el `schemas/4.json`
compilando una sola variante, copiar el `createSql` textual a la migración,
nunca escribirlo a mano):

- `VinculacionEntidad` gana `esParcial: Boolean`.
- `ConteoEntidad` gana `pasadaId: Int` (mismo patrón que ya tiene
  `sesionId`, resuelto ahí para el mismo problema de fondo: sin esto, un
  conteo local no se puede atribuir a la pasada correcta).
- Tabla nueva `pasada_item`, un solo campo (`articuloId`), tan simple como
  `AsignacionEntidad`.

`ListaAsignada.armar` (`celular/nucleo`) filtra los conteos locales por
`pasadaActivaId` antes de sumar —así un tilde de "ya contado" del Conteo 1
no contamina el Conteo 2— y, cuando la pasada es parcial, acota los
artículos mostrados al conjunto permitido. `PantallaMiLista` muestra la
etiqueta de la pasada activa bajo el título: el mismo dato que
`PantallaEscaneo` ya muestra hoy en su encabezado, solo faltaba acá.

## El panel — pestaña «Recuento»

### Una corrección necesaria antes de construir la pestaña

`PUT /api/sesiones/{id}/operarios/{id}/asignacion` —el endpoint detrás del
diálogo «Sectores» que ya existe en la pestaña Operarios— hoy **no recibe
`pasada_id`**: lo resuelve solo, con `pasada_abierta` ("la abierta de número
más alto"). En cuanto exista un recuento abierto, este endpoint empezaría a
asignar sectores al recuento en vez de al Conteo 1, y el diálogo «Sectores»
se rompería en silencio —sin ningún error visible, solo asignando mal—.

Pasa a exigir `pasada_id` en el cuerpo del pedido. El diálogo «Sectores» que
ya existe lo manda explícito (el de la pasada general), y la pestaña
Recuento reutiliza el mismo diálogo, pasando el id del recuento
correspondiente en cada caso.

### Estructura de la pestaña

- **Tolerancia.** Un formulario que llama al endpoint que ya existe y
  funciona (`PUT /api/sesiones/{id}/tolerancia`) pero que hoy no tiene
  ninguna interfaz —confirmado por búsqueda: cero menciones de "tolerancia"
  en `index.html` ni en `app.js`—.
- **Listado A RECONTAR.** Reusa `GET /api/sesiones/{id}/tablero?estado=A RECONTAR`,
  que ya existe sin cambios, con una casilla por fila. **Arranca vacío**: se
  tilda a propósito lo que entra al recuento, no al revés. Con «Seleccionar
  todos» y «Deseleccionar todos» como atajos, y un buscador para sumar algún
  SKU que no haya quedado en A RECONTAR pero que el responsable igual quiera
  recontar.
- **Abrir recuento.** Un botón que llama a `POST /api/sesiones/{id}/pasadas`
  con los SKU tildados. Crea la pasada siguiente y sus filas de
  `pasada_item`, todo en una sola transacción: una pasada sin sus SKU, o al
  revés, no puede existir nunca.
- **Recuentos abiertos.** Una tarjeta por cada pasada de recuento abierta,
  con su etiqueta, cuántos SKU tiene, el diálogo de asignación por operario
  —el mismo de Operarios, reutilizado con el `pasada_id` de esa tarjeta— y
  su avance. El avance es una función nueva y chica,
  `reparto.avance_de_pasada`, y no una reutilización forzada de
  `avance_por_operario`: son preguntas distintas. `avance_por_operario`
  contesta "qué es vigente hoy" —la pasada de número más alto en que cada
  SKU fue contado—, mientras que acá la pregunta es sobre *esta* pasada
  puntual, que puede no ser la vigente si se abrió otro recuento después.

## Restricciones que no se negocian

- `stock_sistema` y `costo_unitario` nunca salen por ningún endpoint
  `/api/dispositivo/*`.
- Nada se edita ni se borra — una corrección es una fila nueva.
- Cantidades en milésimas, importes en centavos, siempre `int`.
- Nada externo en el navegador del panel.
- Todo dato del servidor escapado antes de ir al HTML — el guardián de
  `test_panel_estatico.py` es una lista blanca por nombre de variable y no
  ve las variables sueltas: escapar a mano igual.
- Castellano rioplatense en todos los textos, incluidos los de error.
- TDD sin excepciones: test que falla, implementación, test que pasa,
  commit.
- Servidor antes que celular: el celular tolera campos nuevos en las
  respuestas (`ignoreUnknownKeys = true`) pero no lo contrario.

## Cómo se prueba

- La suite completa del servidor en verde (hoy 449 tests) más los nuevos de
  `pasada_item`, la regla de pasada activa, el bloqueo, y los endpoints de
  recuento.
- `celular/nucleo` y `celular/app` con sus tests unitarios.
- En el navegador: cargar tolerancia, marcar SKU A RECONTAR, abrir un
  recuento, asignarlo por ubicación a un operario, intentar asignar ese
  mismo operario a un segundo recuento abierto y confirmar que se rechaza,
  ver el avance de la tarjeta.
- En un celular real por USB: contar normalmente en el Conteo 1; reasignar
  ese operario a un recuento recién abierto; sin volver a vincularse,
  confirmar que «Lo mío» muestra la etiqueta nueva y solo los SKU del
  recuento; escanear uno fuera del recuento y ver el aviso sin que la app
  se trabe; escanear uno del recuento y confirmar que carga.

## Lo que queda deliberadamente afuera

- **Cerrar un recuento individual sin cerrar toda la sesión.** No fue
  pedido. Sin esto, un operario que terminó su recuento sigue "atado" a esa
  pasada —según la regla de arriba— hasta que se cierre la sesión entera o
  se lo desasigne a mano. Es una extensión chica si hace falta más adelante.
- **Un sonido distinto para "fuera de recuento" contra "código
  desconocido"** en el celular. Usa el mismo aviso sonoro por ahora;
  separar los dos es un detalle menor de una sola tarea futura.
