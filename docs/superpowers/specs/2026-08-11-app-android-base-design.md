# App Android base — Diseño

Fecha: 2026-08-11
Estado: aprobado, listo para plan de implementación

Este documento detalla la primera versión de la app Android descrita en la
sección 6 del diseño general (`2026-08-10-control-de-stock-design.md`), que
sigue siendo la referencia para todo lo que acá no se contradiga.

## 1. Objetivo

Que un operario cuente mercadería escaneando códigos de barras con su
celular, sin señal, y que lo contado aparezca en el tablero del panel apenas
haya red.

El núcleo del servidor ya está construido y probado: recibe conteos
idempotentes por `uuid`, los atribuye al operario, consolida el tablero y
exporta. Esta app reemplaza el único paso que hoy se hace a mano.

## 2. Alcance

### Entra

- Vinculación del dispositivo escaneando un QR del panel.
- Descarga del maestro completo y trabajo enteramente offline.
- Escaneo continuo con la cámara, con ficha de carga de cantidad.
- Corrección de ubicación y observaciones.
- Alta rápida cuando el código no está en el maestro.
- «Mis conteos», con anulación.
- Búsqueda offline contra el maestro local.
- Sincronización en segundo plano con reintento.

### Queda para la fase siguiente

Cada una depende de servidor que todavía no existe:

| Función | Qué falta del lado servidor |
|---|---|
| Pasadas sucesivas y lista a recontar | Abrir la pasada N con su conjunto de SKUs; marcarlos desde el panel |
| Mis ubicaciones | Reparto de ubicaciones entre operarios y avance por ubicación |
| Vinculación de códigos a un SKU | Traslado de conteos por eventos hacia el SKU destino |

El cálculo del valor vigente entre pasadas —cada pasada reemplaza a la
anterior; un SKU no incluido conserva el valor de la última en que fue
contado— **ya está implementado y cubierto con tests** en
`servicios/tablero.py`. La fase siguiente agrega la apertura de pasadas, no
el cálculo.

### Preparación explícita para esa fase

La base local del celular incluye desde el arranque dos campos que hoy
tienen un solo valor posible:

- `articulo.pasada_numero` — a qué pasada pertenece el artículo (hoy
  siempre 1).
- `conteo.fuera_asignacion` — si el conteo cayó fuera de lo asignado (hoy
  siempre `false`).

Sin ellos, agregar pasadas sucesivas obligaría a migrar la base de cada
dispositivo en medio de un inventario. Dos columnas ahora evitan eso.

## 3. Arquitectura

Tres capas, en dos módulos Gradle:

```
app/          Android: pantallas, cámara, base local, sincronizador
nucleo/       Kotlin puro: reglas y conversiones, sin una sola clase de Android
```

La separación no es decorativa: **todo lo que se puede probar sin un celular
enchufado vive en `nucleo/`**, y se prueba con `gradle test` en segundos. Es
la misma decisión que en el servidor, donde la lógica se prueba sin levantar
FastAPI.

### `nucleo/` — Kotlin puro

| Componente | Responsabilidad |
|---|---|
| `Cantidades` | Texto ↔ milésimas, con los mismos casos que `cantidades.py` |
| `EventoConteo` | Arma el evento que viaja al servidor, con su `uuid` |
| `ReglasDeCarga` | Decide si una cantidad es válida y si necesita confirmación |
| `PlanDeSincronizacion` | Dado el estado local, qué mandar y en qué orden |
| `ContratoApi` | Tipos de pedido y respuesta, serializables |

### `app/` — Android

| Componente | Responsabilidad |
|---|---|
| `BaseLocal` (Room) | Maestro descargado, códigos, unidades, conteos propios |
| `ClienteServidor` (OkHttp) | Llamadas HTTP con el encabezado `X-Token` |
| `Sincronizador` (WorkManager) | Empuja pendientes cuando hay red, reintenta cuando no |
| `Escaner` (CameraX + ML Kit) | Cámara siempre activa y decodificación |
| Pantallas (Compose) | Cámara, ficha, alta rápida, mis conteos, buscar, vinculación |

### Dependencias

Mínimo indispensable, todas resueltas en tiempo de compilación:

- CameraX `1.3.3` — vista previa y análisis de imagen.
- ML Kit `barcode-scanning` `17.2.0`, **variante con el modelo incluido en
  el APK**. La variante que lo descarga de Play Services fallaría
  exactamente donde se usa la app: un depósito sin internet.
- Room `2.6.1`, WorkManager `2.9.0`, Compose BOM `2024.05.00`.
- OkHttp `4.12.0` y `kotlinx.serialization` `1.6.3`.

`minSdk 26` (Android 8, como fija el diseño general), `targetSdk 34`,
Kotlin `1.9.23`, AGP `8.4.0`, Gradle `8.7`, JDK 17.

## 4. Base local

Room sobre SQLite. Es la fuente de verdad del celular: **la app nunca
consulta al servidor para trabajar**, solo para sincronizar. Con o sin
señal, se comporta igual.

```
vinculacion(url, token, operario_id, operario_nombre, sesion_id,
            pasada_id, pasada_numero, pasada_etiqueta)

articulo(id, id_orden, tipo, material, sku, descripcion, grupo,
         ubicacion, unidad, pasada_numero)

codigo(codigo, articulo_id)          -- índice por código
unidad(codigo, nombre, admite_decimales)

conteo(uuid PK, articulo_id, cantidad, ubicacion_real, observaciones,
       fuera_asignacion, timestamp_dispositivo, anula_uuid,
       estado_sync, motivo_rechazo)  -- pendiente | enviado | rechazado
```

`rechazado` existe porque un conteo que el servidor no puede aceptar nunca
—no por falta de red— no debe reintentarse para siempre ni desaparecer sin
dejar rastro: queda visible en «Mis conteos» con su motivo.

Las cantidades se guardan como **enteros en milésimas**, igual que en el
servidor y por el mismo motivo: sumar decimales en punto flotante acumula
error y un inventario suma miles de veces.

Nada se edita ni se borra: una corrección genera un conteo de anulación que
apunta al `uuid` original, exactamente como en el servidor.

## 5. Sincronización

- Cada conteo nace en el celular con su `uuid` y se guarda primero en la
  base local. La pantalla confirma contra la base local, no contra la red.
- Un trabajo de WorkManager empuja los pendientes cuando hay conexión. Si no
  hay, se acumulan sin interrumpir nada.
- El servidor descarta los `uuid` ya recibidos: reenviar es inofensivo, y
  ese comportamiento ya está probado del lado servidor.
- Un conteo rechazado como **no reintentable** (por ejemplo, código
  desconocido) se marca y se muestra en «Mis conteos» con su motivo, en vez
  de reintentarse para siempre. El servidor ya distingue los dos casos.
- El indicador de pendientes es discreto y **nunca bloquea el escaneo ni
  abre diálogos**.

## 6. Pantallas

### Vinculación

Solo la primera vez. La app abre la cámara y lee el QR que muestra el panel,
que contiene la dirección del servidor y el token del operario. Al leerlo:
llama a `/api/dispositivo/vincular`, guarda la vinculación, descarga el
maestro y queda lista.

Si el QR es válido pero el servidor no responde, el error lo dice en
castellano llano —«No se pudo llegar al servidor. ¿El celular está en la
misma red WiFi?»— y ofrece reintentar.

### Cámara

Pantalla principal. La cámara está **siempre activa**: el operario apunta y
lee, no aprieta botones. Arriba, discretos: pasada, operario y conteos
pendientes de subir. Abajo: linterna, buscar y mis conteos.

Al leer un código: vibración, sonido y la ficha sube desde abajo.
**Mientras la ficha está abierta, el escaneo se pausa** — es lo que evita la
lectura duplicada accidental cuando el celular sigue apuntando al mismo
código.

### Ficha del artículo

La descripción domina la pantalla; SKU, grupo y material quedan en segundo
plano. El operario tiene que confirmar de un vistazo que tiene el producto
correcto en la mano.

- Cantidad con teclado numérico propio, teclas grandes, coma siempre
  disponible.
- Si la unidad no admite decimales y se carga uno, **pide confirmación pero
  no bloquea**.
- Ubicación del sistema visible, con un lápiz que abre una lista con
  buscador poblada del maestro local, más «Otra…» para las ubicaciones
  físicas que el ERP no tiene.
- Observaciones en texto libre, siempre disponibles, siempre opcionales.
- Al confirmar: vibración corta, se guarda en la base local y vuelve a la
  cámara.

Sin scroll: todo lo necesario para confirmar entra en la pantalla.

### Alta rápida

Se abre sola cuando el código escaneado no está en el maestro, con un sonido
distinto del de lectura correcta. Pide descripción, unidad, ubicación y
cantidad.

El artículo se crea en la sesión con `origen = 'alta_rapida'` y el código
escaneado asociado. En el panel y en la exportación salen identificados
aparte, para resolverlos después en el ERP.

A diferencia del conteo, el alta rápida **necesita red**: el artículo lo
crea el servidor, que es quien asigna el identificador. Sin señal, la app lo
dice y ofrece anotarlo para más tarde, guardando el escaneo como pendiente
de alta.

### Mis conteos

Las cargas propias de la sesión, de la más reciente a la más vieja, con SKU,
cantidad, ubicación y hora. Deslizar una línea la anula, mostrando qué se
está anulando antes de confirmar. **Solo lo propio**: no se ve el total del
SKU ni lo contado por otros.

### Buscar

Contra el maestro local, sin señal, por descripción, SKU o ubicación. Es lo
que destraba la etiqueta rota o ilegible, que de otro modo frena el conteo.

## 7. Cambios en el servidor

Tres agregados, chicos, con sus tests:

### QR de vinculación

`GET /api/operarios/{id}/qr` devuelve un SVG con la dirección del servidor y
el token. Se genera con **segno**, que es Python puro y no arrastra
dependencias de imagen.

La dirección sale de la IP local de la máquina, que ya se calcula en
`iniciar.py`. Esa función se muda a `app/red.py` para que la use también la
API, e `iniciar.py` la importa de ahí: una sola implementación.

El contenido del QR es un JSON compacto:

```json
{"u": "http://172.16.11.12:8000", "t": "<token del operario>"}
```

En el panel, cada operario muestra su QR junto al token en texto, que sigue
sirviendo para vincular a mano si hace falta.

### Alta rápida

`POST /api/dispositivo/articulos` con descripción, unidad, ubicación y el
código escaneado. Crea el artículo en la sesión abierta con
`origen = 'alta_rapida'`, `creado_por` = el operario del token, y asocia el
código.

El SKU del artículo nuevo es **el código escaneado**. Si el alta se hace sin
código (producto sin etiqueta), se genera `AR-<número>` correlativo dentro
de la sesión. El `id_orden` se asigna por encima del mayor existente, con el
mismo criterio que ya usa la importación.

Si el código escaneado **coincide con el SKU de un artículo que ya está en
la sesión**, no se crea nada: se asocia el código a ese artículo y se
devuelve el existente. Pasa cuando el maestro trajo un código de barras
propio distinto del SKU, y el artículo quedó sin su SKU como código. Crear
un duplicado ahí violaría la unicidad de SKU por sesión y, peor, partiría el
conteo de un mismo producto en dos filas del tablero.

La respuesta **no incluye `stock_sistema` ni `costo_unitario`**, como todo
lo que sale por los endpoints de dispositivo.

La respuesta trae además **`creado: true | false`**. Sin ese campo, la app no
tiene forma de distinguir «se dio de alta» de «ese código ya estaba», que es
justo lo que necesita para avisarle al operario que el producto que escaneó
resultó ser uno del maestro con otra descripción. Cada cliente inventaría su
heurística —comparar la descripción que mandó contra la que volvió— y esa
falla cuando el operario escribió lo mismo.

El alta es **idempotente**: si dos operarios escanean la misma etiqueta
desconocida a la vez, el segundo recibe el artículo del primero con
`creado: false`, en vez de un error. La excepción es el alta **sin** código:
ahí no hay identidad compartida —dos productos sin etiqueta no son el mismo
producto— así que el segundo recibe su propio `AR-<n>` con `creado: true`.

### Distribución del APK

`GET /app.apk` sirve el archivo si está presente junto al servidor, y el
panel muestra un QR que apunta ahí. Es lo que permite instalar la app en un
celular del depósito sin cable ni tienda. Si el APK no está, el panel no
muestra el QR en vez de ofrecer una descarga rota.

## 8. Errores y avisos

Tres avisos, cada uno con **sonido, vibración y color propios**: leído
correctamente, código desconocido, y error. En un depósito ruidoso no se
escucha; con el celular en movimiento no se ve. Al menos uno de los tres
siempre llega.

Los mensajes se escriben en castellano llano y dicen qué hacer:

| Situación | Mensaje |
|---|---|
| Código no está en el maestro | «Este código no está en el conteo. Podés darlo de alta.» |
| Sin red al dar de alta | «Sin conexión. El alta se hace cuando vuelva la señal.» |
| Token inválido o revocado | «Este celular ya no está vinculado. Escaneá de nuevo el QR.» |
| Sesión cerrada en el servidor | «El inventario se cerró. No se pueden cargar más conteos.» |

Nada que se pueda tocar sin querer borra trabajo: anular pide un gesto
deliberado y muestra qué se anula.

## 9. Testing

### Unitarios en la PC (`gradle test`, sin dispositivo)

El grueso. Todo `nucleo/`:

- **Cantidades**: los mismos casos que `test_cantidades.py`, portados. Si el
  celular redondea distinto que el servidor, aparecen diferencias fantasma
  que nadie va a poder explicar frente al cliente.
- **Evento de conteo**: `uuid` único, timestamp en formato ISO 8601 UTC,
  anulación que referencia el original.
- **Plan de sincronización**: qué se manda, en qué orden, qué se reintenta y
  qué no.
- **Reglas de carga**: decimal en unidad entera pide confirmación; cantidad
  vacía o fuera de rango se rechaza.

### Contrato con el servidor

Las respuestas reales del servidor (maestro, vinculación, envío de conteos,
alta rápida) se capturan como archivos de referencia. La app se prueba
contra ellos y **un test del lado Python verifica que el servidor sigue
produciendo esa misma forma**. Si alguien renombra un campo, rompe de los
dos lados a la vez, en la PC, en vez de fallar en el depósito.

### Instrumentados (requieren el celular conectado)

Base local —lo guardado sobrevive al cierre de la app— y navegación entre
pantallas.

### Manual, con el celular en la mano

Escaneo de etiquetas reales con poca luz, linterna, vibración, y el circuito
completo en modo avión: contar sin señal, salir del avión, ver que sube
solo y aparece en el tablero.

**La calidad de lectura sobre etiquetas gastadas no la cubre ningún test.**
Se verifica a mano antes de dar la app por lista.

## 10. Fuera de alcance

- Pasadas sucesivas, lista a recontar, mis ubicaciones y vinculación de
  códigos: fase siguiente, con el servidor que las sostiene.
- Variante PWA para iPhone (sección 7 del diseño general).
- Publicación en Google Play: la app se instala desde el servidor local.
- Autenticación por PIN del operario: el token del dispositivo alcanza para
  esta versión.
