# Identificarse sin QR, contar tocando el SKU y marcar lo agregado — diseño

Fecha: 2026-09-14

## El problema

Tres faltantes de la app del celular, juntos porque los tres tocan el mismo
camino —vincularse, contar, dar de alta— y conviene resolverlos de una vez:

1. **Vincularse hoy es escanear un QR**, siempre. Si el operario está lejos de
   la PC que muestra el QR —otro sector, otro turno, el mismo celular
   compartido entre varias personas— no tiene forma de identificarse sin
   caminar hasta ahí.
2. **Contar es escanear, siempre.** Si el operario ya está mirando el
   producto en la lista de lo asignado, no hay forma de tocarlo y cargar la
   cantidad: tiene que buscar el código de barras y escanearlo, aunque lo
   tenga en la mano. Y si el código está roto o tapado, la única salida es
   escanear una etiqueta distinta o escribir el código a mano dígito por
   dígito, sin saber si existe.
3. **Nada distingue, ni en el celular ni en el panel, un producto que estaba
   en el maestro original de uno que un operario agregó a mitad de conteo.**
   El responsable no puede saber de un vistazo cuáles son altas rápidas sin
   cruzar datos.

## A. Identificarse sin escanear el QR

Sirve **solo en un celular que ya se vinculó alguna vez** —tiene URL y un
token guardados—. No reemplaza el QR: sigue siendo la única forma de dejar un
celular nuevo listo para contar. Esto es para el caso de un celular que ya
está en uso y cambia de manos, o de un operario que no puede llegar hasta la
PC.

### El PIN que ya existía y no se usaba

El esquema ya tiene una columna `pin` en `operario`, opcional, que se puede
cargar al dar de alta un operario desde el panel — pero hoy no la lee nadie.
Este cambio le da su primer uso: identificarse sin QR pide el nombre siempre,
y el PIN **solo si ese operario lo tiene cargado**. El que no tiene PIN se
identifica con solo elegir su nombre — así lo pidió el cliente a propósito,
para no trabar a la mayoría por un caso que puede resolver con un PIN el que
lo necesite.

El PIN viaja y se guarda como texto plano, igual que hoy: no es una
contraseña de un sistema con usuarios, es una traba liviana para un nombre
que cualquiera que mire la pantalla del celular puede leer. Subirle el nivel
de seguridad es una decisión aparte, no de esta rama.

### Los endpoints nuevos

Los dos exigen `X-Token` de **algún** operario ya vinculado — es la prueba de
que el pedido viene de un celular que ya pasó por el QR alguna vez, no de
cualquiera que le pegue a la IP del servidor:

- **`GET /api/dispositivo/operarios`** → `{"operarios": [{"id", "nombre",
  "tiene_pin"}, ...]}`, todos los operarios activos. Nunca el PIN ni el
  token de nadie — ni siquiera el propio: esta lista es para elegir un
  nombre en una pantalla, no para vincularse con ella.
- **`POST /api/dispositivo/identificar`**, con `{"nombre", "pin"}` (`pin`
  ausente si el operario no lo tiene). Devuelve la misma forma que
  `/vincular` —`operario`, `proyecto`, `pasada`— más `"token"`, el token del
  operario elegido, porque a diferencia de `/vincular` acá el celular no lo
  trae puesto: se lo tiene que llevar de la respuesta para usarlo de ahí en
  adelante.

  Rechaza con **400** y un texto explicando qué falta: `"Ese operario no
  existe"` (nombre que no está o está inactivo), `"Ese operario necesita un
  PIN"` (tiene uno cargado y no vino ninguno) o `"El PIN no coincide"`. Con
  **409** si no hay proyecto abierto, igual que `/vincular`.

  El repositorio de operarios suma dos funciones: `listar_para_identificar`
  (la lista de arriba, sin token ni PIN) y `para_identificar` (una consulta
  aparte que sí trae el PIN, porque es la única que lo necesita para
  compararlo — nunca sale de adentro de esa función hacia una respuesta).

### El celular

`PantallaMiLista` no muestra hoy el nombre del operario — solo la etiqueta de
la pasada. Se agrega al encabezado, junto a un botón **«Cambiar»** que abre
un diálogo con la lista de operarios activos; tocar uno sin PIN identifica
directo, tocar uno con PIN pide el PIN antes.

`Vinculador` suma un método `identificar(nombre, pin)`: llama al endpoint
nuevo con la URL y el token que el celular ya tiene guardados, arma una
`VinculacionEntidad` con el operario, el token y la pasada que devuelve el
servidor —proyecto y URL quedan igual— y la guarda con `BaseLocal.vincularA`,
la misma función que ya usa `vincular()`. Reutilizarla importa: ya sabe
limpiar el reparto de quien tenía el celular antes cuando cambia el operario,
sin tocar el maestro ni los conteos pendientes, que son del proyecto y no de
la persona. No hace falta bajar el maestro de nuevo: es el mismo proyecto.

Después de identificarse, se llama a `refrescarListaAsignada()` — la misma
función que ya corre al vincularse y al volver del fondo —, así el reparto,
`esParcial` y `pasada_item` quedan al día para el operario nuevo sin lógica
extra.

**Queda anotado y afuera:** un conteo pendiente de subir no lleva hoy qué
operario lo hizo — se le atribuye al que tenga el token puesto en el momento
de subirlo. Cambiarse de operario con conteos sin subir en el medio ya podía
mezclar la autoría hoy, re-vinculando por QR; esta rama no lo empeora ni lo
arregla.

## B. Contar tocando el SKU

### Tocar la tarjeta en «Mi Lista»

Todo lo que aparece en Mi Lista ya está en el maestro — no hay «no
encontrado» posible acá, es la lista de lo asignado. Se agrega:

- `articuloId` a `RenglonAsignado` (el dato ya está disponible en
  `ArticuloParaLista`, solo falta pasarlo).
- `Contador.buscarPorId(articuloId): Hallazgo?` — la misma lógica que
  `buscar(codigo)` (chequeo de `esParcial`/`pasada_item`, si la unidad admite
  decimales), pero resolviendo por `porId` en vez de `porCodigo`. Devuelve
  `null` si el artículo ya no existe (la lista se armó con la base de un
  refresco anterior y mientras tanto se reimportó el maestro); en ese caso no
  pasa nada, no hay ficha que abrir.
- `TarjetaProducto` se vuelve tocable (`Modifier.clickable`) y sube un
  `onTocar: () -> Unit`; `PantallaMiLista` suma el parámetro `alTocarProducto:
  (Int) -> Unit`.
- En `MainActivity`: tocar navega a `Pantalla.Escaneando` y llama a
  `buscarPorId`; si devuelve un hallazgo, se asigna a `hallazgo` como hace
  hoy una lectura de cámara, y la ficha se abre sola. La cámara sigue viva
  detrás, en pausa mientras la ficha está abierta, igual que siempre.

### Buscar por descripción o SKU

Ya existe, sin usar, el método `MaestroDao.buscar(texto)`: busca contra la
columna `busqueda` (descripción + SKU + ubicación, en minúscula y sin
acentos) y estaba pensado —dice su propio comentario— para «destrabar la
etiqueta rota», el caso de un código que no se puede escanear ni escribir
porque la etiqueta está arruinada.

Se agrega:

- Un botón **«Buscar»**, al lado de **«A mano»** en el encabezado de la
  pantalla de escaneo.
- `Contador.buscarTexto(texto): List<Hallazgo.Encontrado>` — envuelve
  `MaestroDao.buscar`, descarta lo que caiga fuera de la pasada activa (mismo
  filtro de `esParcial`/`pasada_item` que el resto), y arma cada resultado
  con `buscarPorId`.
- Un diálogo nuevo, `DialogoBuscarProducto`: un campo de texto que busca en
  cada tecla (la consulta es local, sin red, y corta en 50 resultados como ya
  hace `buscarPlegado`) y una lista de coincidencias — SKU, descripción,
  ubicación. Tocar una abre su ficha de conteo, igual que tocar la tarjeta en
  Mi Lista.

**Si no hay ninguna coincidencia**, el diálogo no inventa un camino de alta
propio: muestra el aviso y un botón que cierra la búsqueda y abre
directamente **«A mano»** — el mismo `DialogoCodigoAMano` que ya existe, que
ya sabe decir «desconocido» y ofrecer «Darlo de alta» cuando corresponde.

Esto fue una decisión a propósito y no la primera que se consideró. La
alternativa —que la propia ficha de alta acepte un código escrito a mano
cuando se llega desde la búsqueda— exigía revalidar ahí mismo que ese código
no chocara con uno que ya existe, duplicando una lógica que `leerCodigo` ya
resuelve bien desde hace rato. Reusar «A mano» no le suma ningún paso al
operario que no tenga ya hoy quien escanea una etiqueta rota, y no puede
crear un artículo duplicado por el mismo camino que ya lo evita.

**Deuda que ya existía y esto no toca:** el teclado de «A mano» es numérico.
Un SKU alfanumérico no se puede escribir ahí. No es nuevo — ya pasa hoy con
cualquier código de barras que tenga letras — y arreglarlo es una decisión de
teclado, no de esta rama.

`buscando` (el estado que abre `DialogoBuscarProducto`) se suma a la lista de
causas que `fichaAbierta` y `atrasCierra` (`Pantalla.kt`) ya combinan con
`hallazgo`, `altaDe` e `ingresandoAMano`: pausa la cámara y el botón atrás lo
cierra antes de volver a la lista, con el mismo criterio que las demás.

**Verificar en un celular real:** el encabezado de escaneo ya está apretado
—pasada, operario, «A mano», pendientes— y hay una nota vieja sobre nombres
largos de operario empujando «A mano» fuera de la pantalla. Sumar «Buscar» lo
aprieta más; si en un celular real no entra cómodo, la salida es acortar los
textos o unificar «A mano» y «Buscar» en un solo menú, no agregar scroll
horizontal.

## C. La etiqueta «AGREGADO»

El servidor ya guarda de dónde salió cada artículo: la columna `origen` de
`articulo`, `'importado'` o `'alta_rapida'`, puesta desde que existe el alta
rápida. El tablero del panel ya la calcula y ya cuenta cuántas altas rápidas
hay en el resumen (`resumen.altas_rapidas`) — nadie la pintaba todavía.

### En el panel

Una sola línea en `dibujarFila` (`panel/app.js`): si `fila.origen ===
"alta_rapida"`, se agrega un `<span class="marca">AGREGADO</span>` al lado
del SKU — la misma clase que ya usan las otras marcas del tablero (sin
asignar, fuera de sector), para que se vea como parte de la misma familia de
avisos y no como algo nuevo.

### En el celular

Acá sí hace falta bajar el dato, porque hoy `/api/dispositivo/maestro` no lo
manda:

- Se agrega `a.origen` al `SELECT` de `descargar_maestro`
  (`servidor/app/api/dispositivos.py`) y `origen: String` a `ArticuloRemoto`
  (`celular/nucleo/.../ContratoApi.kt`), con valor por defecto `"importado"`
  para no romper si un celular viejo habla con un servidor nuevo a mitad de
  actualización.
- `ArticuloEntidad` (Room) suma la columna `origen`, con
  `DEFAULT 'importado'` — sube la versión de la base local de 5 a 6, con su
  migración, siguiendo el mismo patrón que las migraciones anteriores
  (agregar la columna, nada más, sin tocar el resto).
  `Vinculador.vincular` y `Contador.darDeAlta` la completan: el maestro
  bajado copia lo que manda el servidor, y un alta nacida en el celular nace
  ya con `origen = "alta_rapida"` sin esperar a que suba, para que se vea
  marcada de entrada.
- `RenglonAsignado` suma `agregado: Boolean` (`origen == "alta_rapida"`), y
  `TarjetaProducto` (`PantallaMiLista.kt`) le agrega una tercera etiqueta
  junto a CONTADO/PENDIENTE cuando corresponde. Color nuevo en `Tema.kt`
  —`Violeta`, para no repetir Verde (contado), Ambar (pendiente) ni Rojo
  (error), y para no usar `Acento`, que ya es el color primario de toda la
  app y se confundiría con un botón.

La etiqueta es **permanente**, no solo mientras el alta está pendiente de
subir: sale de `origen`, que el servidor conserva para siempre, y no del
`estadoAlta` local (que sí se limpia cuando el maestro se reimporta). Un
alta rápida se sigue viendo agregada en el celular de cualquier operario que
la vea después, no solo en el que la creó.

## La API nueva, resumida

- `GET /api/dispositivo/operarios` — 200 con la lista para elegir, 401 con
  token inválido, 409 sin proyecto abierto.
- `POST /api/dispositivo/identificar` — 200 con la vinculación nueva y el
  token del operario elegido, 400 si el nombre no existe o el PIN falta o no
  coincide, 401 con token inválido, 409 sin proyecto abierto.
- `GET /api/dispositivo/maestro` — sin cambio de forma, un campo más
  (`origen`) por artículo.

## Cómo se prueba

- **Los endpoints nuevos**: operario sin PIN se identifica con solo el
  nombre; operario con PIN exige y valida el PIN; nombre inexistente o de
  operario inactivo da 400; PIN incorrecto da 400; token inválido en el
  encabezado da 401; sin proyecto abierto da 409; la lista de operarios
  nunca trae `pin` ni `token_dispositivo`.
- **El contrato** (`servidor/tests/test_contrato.py` y
  `celular/contrato/capturar.py`): el maestro capturado de nuevo con la
  columna `origen`, y dos archivos nuevos —`operarios.json` e
  `identificacion.json`— sumados a `ARCHIVOS`, capturados y comparados igual
  que los demás. Sin esto, `ContratoApiTest.kt` no tiene contra qué parsear
  los DTO nuevos.
- **`Contador.buscarPorId` y `buscarTexto`**, en `celular/app` con Robolectric
  o en `celular/nucleo` si la lógica de filtrado se puede separar: encuentra
  por id, respeta `esParcial`, no encuentra un id borrado, busca por SKU y
  por descripción, ignora mayúsculas y acentos, no devuelve lo fuera de
  pasada, corta en 50.
- **La migración de Room** (5→6): sigue el patrón de
  `MigracionV5Test.kt` — una base con el esquema viejo, migra, y el dato
  existente sigue ahí con `origen = 'importado'`.
- **El panel**: con los tests que ya existen — nada externo en el navegador,
  todo dato escapado (`fila.origen` no es dato libre del cliente, pero la
  marca se arma igual con el guardián de siempre).
- **En un celular real por USB**: identificarse sin PIN y con PIN, con PIN
  incorrecto; tocar una tarjeta de Mi Lista y cargar la cantidad; buscar un
  producto por parte de la descripción, contarlo, buscar algo que no existe
  y llegar a «A mano»; ver la etiqueta AGREGADO en un alta rápida recién
  creada y en una ya subida, después de reimportar el maestro; probar que
  «Buscar» al lado de «A mano» no rompe el encabezado con un nombre de
  operario largo.

## Lo que queda afuera, a propósito

- **Escribir el PIN con más seguridad que texto plano.** Es una traba
  liviana, no una contraseña; si el cliente pide más, es una rama aparte.
- **Elegir servidor sin haber escaneado nunca un QR.** Identificarse sin QR
  necesita una URL que el celular ya tenga guardada; un celular nuevo sigue
  necesitando el QR una vez.
- **Un teclado alfanumérico para «A mano».** Sigue siendo numérico, como
  hoy; un SKU con letras solo se puede dar de alta escaneándolo.
- **Saber quién contó qué cuando el celular cambia de operario con conteos
  sin subir en el medio.** Deuda que ya existía con el QR; esta rama no la
  toca.
- **Bloquear que dos operarios cuenten el mismo artículo**, o cualquier otra
  regla de negocio sobre el conteo. Nada de esto cambia qué se puede contar,
  solo cómo se llega a la ficha.
