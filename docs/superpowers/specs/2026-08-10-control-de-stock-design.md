# Control de Stock — Diseño

**Fecha:** 2026-08-10
**Estado:** Aprobado para planificación

---

## 1. Objetivo

Sistema de toma de inventario físico con escaneo de códigos de barras. Varios operarios cuentan en simultáneo con celulares Android, contra un servidor que corre en la PC del responsable, en la misma red WiFi del cliente. El resultado se exporta a CSV para volcarlo al ERP.

El inventario puede extenderse varios días y admite conteos sucesivos sobre los artículos con diferencias, hasta acordarlas con el cliente.

## 2. Contexto y restricciones

- **El maestro de artículos sale de un ERP** cuyo formato de exportación varía según el cliente. El mapeo de columnas se resuelve en pantalla, no en código.
- **Conectividad irregular:** hay WiFi pero con zonas muertas. La app debe funcionar completa sin señal y sincronizar cuando vuelve.
- **El servidor corre en la PC del responsable**, presente físicamente en el lugar del conteo, en la misma red que los celulares.
- **Escala variable:** distintos clientes, desde ~1.000 hasta 50.000+ SKUs y de 2 a 10+ operarios.
- **Mantenimiento:** el responsable tiene perfil web (HTML/JS/Python). El backend y el panel quedan en ese terreno; la app Android es código estable que se toca poco.
- **Conteo a ciegas:** el operario no debe conocer el stock teórico.

## 3. Arquitectura

Tres componentes:

| Componente | Tecnología | Rol |
|---|---|---|
| **Servidor** | Python + FastAPI + SQLite | Única fuente de verdad. Expone la API y sirve el panel y la PWA. |
| **Panel web** | HTML + JS | Tablero de control, importación, exportación, administración. |
| **App Android** | Kotlin + CameraX + ML Kit + Room | Camino principal de conteo. Offline-first. |
| **PWA** | HTML + JS + Service Worker + IndexedDB | Alternativa para iPhone y celulares donde no se puede instalar el APK. |

```
ERP → CSV → [Panel web] → Servidor (SQLite)
                           ↕ WiFi, red local
                    ┌──────┴───────┐
              HTTP  │              │  HTTPS
        [App Android nativa]  [PWA: iPhone y
         escaneo → cola        Android sin APK]
         local → sync          escaneo → cola local → sync
                    └──────┬───────┘
                           ↓
                  Panel: tablero en vivo
                           ↓
                     CSV final → ERP
```

**Vinculación de celulares:** el panel genera códigos QR que contienen la dirección del servidor. No se configuran IPs a mano. Si la IP cambia, se regenera el QR.

**Por qué la app nativa es el camino principal:** la velocidad y tolerancia del escaneo (códigos gastados, poca luz, reflejos) determina si la herramienta se usa o se abandona en un conteo de miles de ítems. ML Kit es netamente superior a las alternativas web, y la app nativa no depende de certificados ni de permisos de navegador.

**Por qué existe igual la PWA:** cubre los iPhone y los celulares donde no se puede instalar el APK (políticas del equipo, versión de Android, restricciones corporativas). Sin ella, un operario con el celular equivocado queda sin poder trabajar. Ver sección 7.

**Ambas hablan la misma API y comparten las mismas reglas de negocio.** El servidor no distingue de dónde viene un conteo: recibe eventos con `uuid`, los aplica igual y responde igual. Eso evita mantener dos lógicas en paralelo.

## 4. Modelo de datos

### Principio: todo es un evento, nada se pisa

Cada escaneo genera una fila nueva. El total contado de un SKU es la suma de sus filas dentro de la pasada vigente. Nada se sobreescribe ni se borra. Esto hace que la sincronización sea idempotente y que el conteo sea auditable de punta a punta.

### Tablas del servidor

**`sesion`** — cada inventario (cliente + fecha)
```
id, nombre, fecha_creacion, estado (abierta | cerrada),
tolerancia_pct, tolerancia_min_abs
```

**`pasada`** — cada vuelta de conteo dentro de una sesión
```
id, sesion_id, numero, estado (abierta | cerrada), fecha_apertura, fecha_cierre
```

**Nomenclatura visible.** El campo `numero` es correlativo (1, 2, 3…) y la etiqueta es directamente **"Conteo n"**: `numero = 1` → **Conteo 1**, `numero = 2` → **Conteo 2**, y así sucesivamente.

Esa etiqueta es la que aparece en la app, en el panel y en los encabezados del CSV exportado (`conteo_1`, `conteo_2`, …). Etiqueta y número interno coinciden, sin conversiones intermedias.

El **Conteo 1** abarca todo el maestro; los siguientes son parciales, sobre los SKUs marcados a recontar. Esa diferencia no vive en el nombre: el panel muestra cuántos SKUs incluye cada pasada.

**`articulo`** — el maestro, congelado dentro de la sesión
```
id, sesion_id, id_orden, tipo, material, sku, descripcion, grupo,
ubicacion, unidad, stock_sistema, origen (importado | alta_rapida)
```

**`codigo_barras`** — tabla aparte: un SKU puede tener varios códigos
```
id, articulo_id, codigo
```

**`operario`** — dado de alta desde el panel, global (se reutiliza entre sesiones)
```
id, nombre, pin (opcional), token_dispositivo, activo
```

**`unidad`** — catálogo configurable de unidades de medida
```
id, codigo, nombre, admite_decimales
```
Precargado con: `UN`, `KG`, `GR`, `LT`, `ML`, `MT`, `CJ`, `PACK`.

**`ubicacion`** — catálogo derivado del maestro, más las agregadas por operarios
```
id, sesion_id, nombre, origen (importada | nueva)
```

**`conteo`** — cada escaneo
```
uuid, sesion_id, pasada_id, articulo_id, cantidad, operario_id,
ubicacion_real (nullable), observaciones (nullable),
timestamp_dispositivo, timestamp_servidor,
anula_uuid (nullable)
```

**`pasada_item`** — qué SKUs entran en una pasada parcial
```
pasada_id, articulo_id
```

**`mapeo_columnas`** — formatos de importación guardados
```
id, nombre, definicion_json
```

### Decisiones de modelado

**El maestro se congela dentro de la sesión.** Los artículos se copian al importar. Si el ERP cambia una descripción o se reimporta el listado a mitad del conteo, el inventario ya hecho no se altera y el CSV final refleja el maestro con el que efectivamente se contó.

**`codigo_barras` es tabla aparte, no una columna del artículo.** Permite que un SKU tenga varios códigos (proveedor, pack, reetiquetado) sin duplicar el artículo. Si el ERP entrega el código en la misma columna que el SKU, se crea el artículo y un código idéntico; no se pierde nada.

**Las correcciones no editan ni borran.** Un conteo erróneo se anula con una fila nueva que referencia el `uuid` original vía `anula_uuid`. El total lo ignora, el registro queda. La anulación sincroniza con la misma lógica que cualquier otro evento.

## 5. Reglas de negocio

### Acumulación

Dentro de una misma pasada, escanear repetidamente el mismo SKU **suma**. Cubre el caso de un producto presente en varias ubicaciones o contado por dos personas. Dos operarios contando el mismo SKU en simultáneo no generan conflicto: cada uno aporta su parte.

### Conteos sucesivos

- El **Conteo 1** es la primera pasada y abarca todo el maestro.
- Al cerrarlo, el panel lista las diferencias. Se marcan los SKUs a recontar (manualmente o tomando de una todos los que quedaron en estado `A RECONTAR`) y se abre el **Conteo 2**.
- En una pasada parcial, la app **solo acepta los SKUs marcados**. Si el operario escanea otro, la app avisa *"este artículo no está en el conteo actual"* y no lo carga.
- **Cada pasada cuenta desde cero y reemplaza a la anterior** para esos SKUs. Si en el Conteo 1 se registraron 48 y en el Conteo 2 se cuentan 50, el valor vigente es 50. Sumar daría 98, que no significa nada.
- Un SKU no incluido en una pasada conserva como vigente el valor de la última en que fue contado.
- **Los conteos sucesivos también son a ciegas:** el operario no ve lo que se contó en la pasada anterior, ni propio ni ajeno. De lo contrario tendería a confirmar el primer número en lugar de verificarlo.
- Se pueden abrir tantas pasadas como haga falta (Conteo 2, Conteo 3, Conteo 4…), en días distintos. Todas quedan visibles en paralelo en el tablero.
- La sesión permanece abierta hasta que las diferencias se acuerdan con el cliente. Al cerrarla se congela todo.

**Valor vigente de un SKU:** suma de sus conteos no anulados en la pasada de número más alto en la que fue contado. Se expone en el tablero y en la exportación como **`ultimo_conteo`**.

### Tolerancia

Un artículo está **dentro de tolerancia** si:

```
|ultimo_conteo - stock_sistema| <= max(|stock_sistema| * tolerancia_pct, tolerancia_min_abs)
```

El valor absoluto sobre `stock_sistema` cubre el caso de stock teórico negativo, que algunos ERP arrastran por errores de carga.

Valores por defecto: **2%** con mínimo de **1 unidad**. Configurables por sesión desde el panel.

### Estado de cada artículo

El campo `estado` resume la situación de cada SKU:

| Estado | Condición |
|---|---|
| ⬜ **SIN CONTAR** | Nunca se registró un conteo del artículo. |
| ✅ **CONSOLIDADO** | La diferencia contra el sistema es 0, o entra dentro de la tolerancia. El artículo se da por cerrado. |
| ⚠️ **A RECONTAR** | La diferencia queda fuera de la tolerancia. Candidato a la pasada siguiente. |

Filtrando por **A RECONTAR** se obtiene directamente el conjunto de SKUs que van a la próxima pasada — el panel permite marcarlos todos de una vez desde ese filtro.

La tolerancia es solo un cálculo, no altera datos. Al ajustarla, el tablero recalcula al instante cuántos artículos consolidan y cuántos quedan a recontar — sirve para negociar el criterio con el cliente viendo el impacto real antes de acordarlo.

### Conteo a ciegas

El `stock_sistema` **nunca sale del servidor**. La descarga del maestro al celular incluye `id_orden`, `tipo`, `material`, `sku`, `descripcion`, `grupo`, `ubicacion`, `unidad` y los códigos de barras. No incluye `stock_sistema`, `dif` ni `estado`. El dato no está en la base del celular, con lo cual no es accesible aunque se inspeccione el dispositivo.

El operario **ve solo sus propias cargas** de la sesión, para poder anular un error. No ve el total del SKU ni lo contado por otros.

### Unidades de medida

Lista configurable desde el panel. Arranca con: `UN`, `KG`, `GR`, `LT`, `ML`, `MT`, `CJ`, `PACK`.

- La unidad se mapea como columna al importar. Si el ERP no la trae, se elige una por defecto para toda la importación y se corrigen las excepciones desde el panel.
- En el alta rápida, el operario la elige de una lista.
- Cada SKU acumula siempre en su propia unidad; no hay conversiones entre unidades.
- El teclado numérico incluye coma en todos los casos. Si la unidad es entera (`UN`, `CJ`, `PACK`) y se carga un decimal, la app pide confirmación pero no bloquea.

### Ubicación

Dos conceptos distintos que conviven:

- **`ubicacion`** (del maestro): dónde el ERP dice que el artículo *debería* estar.
- **`ubicacion_real`** (del conteo): dónde el operario lo encontró efectivamente, solo si difiere.

Al escanear, la app muestra la ubicación del sistema. Si no coincide, el operario la corrige eligiendo de una **lista con buscador** — poblada con las ubicaciones del maestro — y deja una **observación** en texto libre. La ubicación del sistema no se pisa.

La lista incluye un botón **"Otra…"** para ubicaciones físicas que el ERP no tiene cargadas. Lo que se escriba ahí queda marcado como *ubicación nueva*, separado de las correcciones comunes en el panel.

El campo **observaciones** está disponible en cualquier conteo, con o sin corrección de ubicación (producto roto, vencido, sin etiqueta). Siempre opcional, nunca bloquea.

### Códigos desconocidos (alta rápida)

Si el código escaneado no está en el maestro, la app avisa con un sonido distintivo y ofrece el alta rápida: descripción, unidad, ubicación y cantidad. El artículo se crea en la sesión con `origen = alta_rapida` y el código escaneado asociado. En el panel y en la exportación salen identificados aparte, para resolverlos en el ERP.

## 6. App Android

### Puesta en marcha

1. Escanear el **QR de instalación** del panel → se abre la página del servidor → descarga del APK.
2. Habilitar "instalar apps de esta fuente" (una vez).
3. Escanear el **QR personal del operario** → la app queda vinculada al servidor con su identidad.
4. Descarga del maestro completo → listo para trabajar offline.

Requiere Android 8 o superior.

### Pantalla principal

```
┌─────────────────────────────┐
│ Conteo 2         Juan   ⚡3 │  ← pasada · operario · pendientes de sync
├─────────────────────────────┤
│                             │
│      [ CÁMARA EN VIVO ]     │  ← escaneo continuo, sin apretar nada
│   ┌───────────────────┐     │
│   └───────────────────┘     │  ← marco guía
│                             │
├─────────────────────────────┤
│  🔦 Linterna    🔍 Buscar   │
│         📋 Mis conteos       │
└─────────────────────────────┘
```

La cámara está siempre activa: el operario apunta y lee, no aprieta botones. Linterna accesible por la mala iluminación habitual en depósitos y estanterías bajas.

### Ficha del artículo

```
┌─────────────────────────────┐
│  TORNILLO HEX 3/8 x 2"      │  ← descripción, prominente
│  SKU 10453 · #127           │
│  Bulonería · Acero inox     │  ← grupo · material, secundario
│                             │
│  📍 Ubicación: A-03-2   ✏️  │  ← el lápiz abre la corrección
├─────────────────────────────┤
│        [  24  ]  UN         │  ← cantidad + unidad, bien visible
│   [1] [2] [3]               │
│   [4] [5] [6]   [ ✓ ]       │  ← teclado propio, teclas grandes
│   [7] [8] [9]   CONFIRMAR   │
│   [C] [0] [,]               │
└─────────────────────────────┘
```

Al leer un código: vibración, sonido, y la ficha sube desde abajo. **Mientras la ficha está abierta el escaneo se pausa**, evitando lecturas duplicadas accidentales. Al confirmar: vibración corta y vuelta a la cámara.

### Otras pantallas

- **Buscar** — para productos sin etiqueta o con código ilegible: búsqueda por descripción, SKU o ubicación contra el maestro local, offline. Sin esto, cada etiqueta rota frena el conteo.
- **Mis conteos** — lista de las cargas propias, de la más reciente a la más vieja, con SKU, cantidad, ubicación y hora. Deslizar una línea la anula. Solo lo propio.
- **Lista a recontar** — durante una pasada parcial, los SKUs asignados con su ubicación, para ir tachando.
- **Indicador de sincronización** — cuántos conteos faltan subir. Verde = todo al día. Nunca bloquea el trabajo.

## 7. Variante web (PWA)

Alternativa para iPhone y para celulares Android donde no se puede instalar el APK. Ofrece las **mismas funciones** que la app nativa: escaneo por cámara, trabajo sin señal, alta rápida, corrección de ubicación y anulaciones.

### Cómo se resuelve el acceso a la cámara y el offline

Los navegadores habilitan cámara y almacenamiento offline solo sobre HTTPS. Para lograrlo en una red local sin internet:

1. **El servidor genera una autoridad certificante propia** (CA) la primera vez que arranca, y la guarda junto a la base. Es única y permanente.
2. **Esa CA se instala una vez por celular.** El panel muestra un QR que descarga el certificado, junto con las instrucciones paso a paso para Android y para iPhone.
3. **En cada arranque, el servidor emite su propio certificado firmado por esa CA**, para la IP que tenga en ese momento.

El punto 3 es el que hace esto sostenible: al cambiar de cliente o de red, la IP cambia y el certificado se regenera solo. **Los celulares no necesitan volver a configurarse** — ya confían en la CA, que es la misma siempre. El trámite es una sola vez por equipo, no una vez por conteo.

El servidor escucha en HTTP (panel, API de la app nativa) y en HTTPS (PWA) al mismo tiempo.

### Funcionamiento

- **Escaneo:** en Android usa el lector de códigos nativo del navegador. En iPhone, que no lo tiene, se usa un decodificador incluido en la propia página. No hay descargas externas: todo se sirve desde el servidor local.
- **Offline:** un Service Worker guarda la aplicación y el maestro completo. Los conteos se acumulan en la base del navegador y se envían con la misma lógica de `uuid` e idempotencia que la app nativa.
- **Instalación:** desde el navegador, "Agregar a la pantalla de inicio". Queda con ícono propio y pantalla completa. En iPhone este paso además es lo que protege los datos guardados de ser borrados por el sistema, así que la PWA guía al operario para que lo haga antes de empezar a contar.
- **Vinculación:** el mismo QR personal del operario que usa la app nativa.

### Límites conocidos

Se documentan porque condicionan cuándo conviene usarla:

- El escaneo por cámara web es **más lento y menos tolerante** que ML Kit, sobre todo con códigos gastados o poca luz. En iPhone la diferencia es mayor.
- iOS puede liberar el almacenamiento del navegador si el equipo queda con poco espacio. Por eso la PWA avisa cuando hay conteos sin sincronizar y recomienda no acumular trabajo offline prolongado en iPhone.
- Si la pantalla se bloquea, la cámara se corta y hay que volver a apuntar. La PWA mantiene la pantalla encendida mientras está en modo escaneo.

**Criterio de uso:** la app nativa para los operarios que hacen el grueso del conteo; la PWA para los equipos que no la admiten.

## 8. Experiencia de uso y diseño

El sistema lo usan dos perfiles muy distintos, en condiciones muy distintas. El diseño responde a eso.

### App y PWA — el operario

Está de pie, moviéndose, con una mano ocupada, en un depósito con mala luz y ruido, repitiendo la misma operación cientos de veces. Todo lo demás se subordina a eso.

- **Una sola acción principal por pantalla.** Escanear, o cargar la cantidad. Nunca las dos cosas compitiendo.
- **Sin scroll en la pantalla de carga.** Todo lo necesario para confirmar entra sin desplazar.
- **Controles en la mitad inferior**, al alcance del pulgar con una mano.
- **Objetivos táctiles grandes:** mínimo 48 dp, y las teclas del numérico bastante más, porque se usan con apuro y a veces con guantes.
- **Jerarquía visual clara:** la descripción del artículo domina la pantalla; SKU, grupo y material quedan en segundo plano. El operario tiene que confirmar de un vistazo que tiene el producto correcto en la mano.
- **Feedback por tres vías a la vez** — sonido, vibración y color — con timbres distintos para *leído*, *código desconocido* y *error*. En un depósito ruidoso no se escucha; con el celular en movimiento no se ve. Al menos una de las tres siempre llega.
- **Alto contraste y texto grande**, legible con poca luz y a distancia de brazo.
- **Los errores se explican en castellano llano y dicen qué hacer**: "Este artículo no está en el conteo actual" y no un código de error.
- **El estado de sincronización nunca interrumpe.** Es un indicador discreto; si hay pendientes se ven, pero jamás bloquea el escaneo ni abre diálogos.
- **Nada que se pueda tocar sin querer borra trabajo.** Anular un conteo requiere un gesto deliberado y muestra qué se está anulando.

### Panel — el responsable

Está sentado frente a una PC, con sesiones largas, mirando muchas filas y tomando decisiones sobre ellas.

- **Las métricas que importan, arriba y grandes:** avance, consolidados, a recontar. Se leen sin buscar.
- **Tabla densa pero legible**, con encabezado fijo al desplazar y las columnas numéricas alineadas a la derecha para poder compararlas de un vistazo.
- **El estado se comunica con color, ícono y texto a la vez**, nunca solo con color: una diferencia no puede pasar desapercibida por daltonismo o por un monitor mal calibrado.
- **El refresco automático no mueve el piso.** Al actualizarse, se mantienen la posición de scroll, los filtros y la fila seleccionada. Un tablero que salta mientras lo leés es inservible.
- **Los filtros activos están siempre a la vista** y se quitan de a uno. Nunca se exporta o se decide sobre una vista filtrada sin que se vea que lo está.
- **Las acciones de peso piden confirmación y explican la consecuencia:** cerrar una pasada avisa cuántos SKUs quedan sin contar antes de seguir.
- **Todo lo que se ve se puede exportar**, con los filtros aplicados.

### Transversal

- Contraste suficiente para lectura cómoda (referencia WCAG AA) en las tres interfaces.
- Un mismo criterio visual para los estados en app, PWA y panel: el mismo color y el mismo ícono significan lo mismo en todos lados.
- Todos los textos en castellano rioplatense, sin jerga técnica.
- Nada de dependencias externas: tipografías, íconos y estilos se sirven desde el servidor local, porque durante el conteo puede no haber internet.

## 9. Sincronización

- Cada conteo nace en el celular con un `uuid` propio y se guarda primero en la base local.
- Un proceso en segundo plano empuja los pendientes apenas hay red. Si no hay, se acumulan sin interrumpir.
- El servidor descarta los `uuid` ya recibidos: reenviar es inofensivo.
- Como los conteos suman dentro de la pasada y nunca se editan, no existen conflictos de escritura concurrente.
- Las anulaciones viajan como eventos más, con la misma garantía.
- El celular puede permanecer sin señal indefinidamente sin perder trabajo.

## 10. Importación y exportación CSV

### Importación

Se arrastra el CSV del ERP al panel y aparece una tabla de mapeo: columnas del archivo a la izquierda, campos del sistema a la derecha (`id_orden`, `tipo`, `material`, `sku`, `descripcion`, `grupo`, `ubicacion`, `unidad`, `stock_sistema`). Vista previa de las primeras filas antes de confirmar.

**El orden y los nombres de columna del archivo son indistintos**: todo se resuelve en el mapeo.

Si el CSV no trae `id_orden`, se genera secuencialmente (1, 2, 3…) según el orden de las filas.

Los mapeos se guardan con nombre ("Formato Tango", "Formato Cliente X"): la siguiente importación de ese cliente es un clic.

### Exportación

**Resumen por SKU:**
```
id_orden | tipo | material | sku | descripcion | grupo | ubicacion | ubicacion_real |
unidad | stock_sistema | ultimo_conteo | dif | estado | fecha | observaciones
```

- `ultimo_conteo`, `dif` y `estado` son calculados sobre el valor vigente. `estado` toma los valores `SIN CONTAR`, `CONSOLIDADO` o `A RECONTAR`.
- `fecha` es la del **último conteo registrado** para ese artículo. Vacía si no se contó.
- `ubicacion_real` queda vacía si nadie la corrigió. Si hubo varias correcciones, se muestra la última y las observaciones se concatenan.
- Cuando hubo más de una pasada se agregan columnas `conteo_1`, `conteo_2`, `conteo_3`… con la cantidad registrada en cada una. Quedan vacías para los SKUs que no participaron de esa pasada.

**Detalle línea por línea:** cada escaneo con operario, hora, pasada (`Conteo 1`, `Conteo 2`…), ubicación real y observaciones.

Ambos se pueden exportar **con los filtros del tablero aplicados** (por ejemplo, solo las diferencias).

## 11. Panel web

**Sesiones** — crear, abrir, cerrar. Solo una sesión abierta a la vez, para que ningún celular se confunda de inventario. Configuración de tolerancia por sesión.

**Importar maestro** — mapeo de columnas con vista previa y formatos guardados (ver sección 10).

**Tablero en vivo** — tabla completa, refresco automático cada pocos segundos:

```
id_orden | tipo | material | sku | descripcion | grupo | ubicacion | ubicacion_real |
unidad | stock_sistema | ultimo_conteo | dif | estado | fecha | observaciones
```

- Métricas superiores: % contado, SKUs contados / totales, unidades contadas, SKUs consolidados, SKUs a recontar, altas rápidas pendientes, correcciones de ubicación.
- Filtros combinables por `tipo`, `material`, `grupo`, `ubicacion`, estado (`SIN CONTAR` / `CONSOLIDADO` / `A RECONTAR`), marcas (ubicación corregida / ubicación nueva / alta rápida) y operario.
- Avance por grupo y por ubicación, para saber dónde falta gente.
- Detección de artículos contados en una ubicación distinta a la esperada.
- Ordenamiento por cualquier columna.

**Conteos** — cerrar la pasada actual, revisar diferencias, marcar SKUs a recontar (manual o todos los que quedaron en `A RECONTAR`), abrir la siguiente. Vista comparativa de todas las pasadas (`Conteo 1`, `Conteo 2`, `Conteo 3`…), con la cantidad de SKUs incluidos en cada una.

**Operarios** — alta con nombre y PIN opcional, QR personal por operario, QR de instalación del APK, estado de conexión, cuánto lleva contado cada uno y si alguno tiene conteos sin sincronizar.

## 12. Instalación y operación

**En la PC:** carpeta autocontenida con el servidor y su propio Python. Doble clic en `Iniciar servidor.bat` y se abre el panel en el navegador. Sin instalación previa ni configuración de rutas. La primera ejecución requiere aceptar el permiso de firewall de Windows para redes privadas; sin eso los celulares no alcanzan el servidor.

**Backup:** toda la base es el archivo `inventario.db`. Copiarlo respalda maestro, conteos, pasadas y observaciones. El servidor genera una copia automática al cerrar cada pasada.

**En los celulares (app nativa):** QR de instalación → APK → QR personal. Android 8+.

**En los celulares (PWA):** QR del certificado → instalarlo siguiendo las instrucciones que muestra el panel → abrir la dirección segura del servidor → "Agregar a la pantalla de inicio" → QR personal. El certificado se instala una sola vez por equipo y sigue sirviendo aunque cambie la red o el cliente.

## 13. Testing

**Automatizado (backend)** — cubre lo que puede fallar en silencio y costar caro:
- Importación con CSVs mal formados: columnas faltantes, encabezados duplicados, filas incompletas, codificaciones distintas, separadores `,` y `;`, decimales con coma y con punto.
- Cálculo del valor vigente por pasada, incluyendo SKUs no incluidos en pasadas posteriores.
- Tolerancia en los bordes: diferencia exactamente igual al límite, stock cero, stock negativo.
- Idempotencia de la sincronización: reenvío del mismo `uuid`, reenvíos parciales, orden alterado.
- Anulaciones: anular un conteo ya anulado, anular un conteo de una pasada cerrada.
- Restricción de SKUs durante una pasada parcial.
- Que `stock_sistema` no aparezca en ninguna respuesta de la API destinada a la app ni a la PWA.
- Que el certificado del servidor se regenere al cambiar la IP y siga validando contra la CA original.

**Manual (app y PWA)** — con una tanda de códigos reales, en ambas interfaces:
- Escaneo con códigos gastados, con reflejo y con poca luz.
- Corte de WiFi a mitad del conteo: verificar que no se pierda ningún escaneo y que sincronice al volver.
- Alta rápida y corrección de ubicación completas.
- PWA: instalación del certificado desde cero en un Android y en un iPhone, siguiendo solo las instrucciones del panel.
- PWA en iPhone: cerrar la app, bloquear el equipo y volver, con conteos pendientes sin sincronizar.
- Conteo mixto: dos operarios con app nativa y uno con PWA sobre la misma pasada.

**Datos de prueba:** se genera un CSV de ejemplo con artículos y códigos reales para recorrer el circuito completo antes de usarlo en un cliente.

## 14. Fuera de alcance

Deliberadamente excluido:

- **Conversión entre unidades** (contar cajas de un artículo medido en kg). Requeriría factores de conversión por artículo; se descartó por decisión explícita.
- **App nativa de iOS.** Los iPhone se cubren con la PWA. Una app de iOS obligaría a cuenta de desarrollador de Apple y a distribución por App Store, desproporcionado para el caso.
- **Soporte para lectores de código Bluetooth.** Queda anotado como refuerzo posible si la velocidad de escaneo resultara insuficiente en algún cliente.
- **Acceso desde fuera de la red local.** El servidor opera en la LAN del cliente durante el conteo.
- **Integración automática con el ERP.** El intercambio es por CSV en ambos sentidos.
- **Multi-cliente simultáneo en el servidor.** Una sesión abierta a la vez.
- **Botón "+1"** para carga rápida de unidades. Descartado: las cantidades se ingresan siempre por teclado numérico.
