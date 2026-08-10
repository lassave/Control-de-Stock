# Control de Stock — Diseño

**Fecha:** 2026-08-10
**Estado:** Aprobado para planificación

---

## 1. Objetivo

Sistema de toma de inventario físico con escaneo de códigos de barras. Varios operarios cuentan en simultáneo con celulares Android, contra un servidor que corre en la PC del responsable, en la misma red WiFi del cliente. El resultado se exporta a CSV para volcarlo al ERP.

El conteo puede extenderse varios días y admite múltiples rondas de recuento hasta acordar las diferencias con el cliente.

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
| **Servidor** | Python + FastAPI + SQLite | Única fuente de verdad. Expone API HTTP y sirve el panel. |
| **Panel web** | HTML + JS | Tablero de control, importación, exportación, administración. |
| **App Android** | Kotlin + CameraX + ML Kit + Room | Escaneo y carga de cantidades, offline-first. |

```
ERP → CSV → [Panel web] → Servidor (SQLite)
                              ↕ WiFi (HTTP, red local)
                        [Celulares Android] → escaneo → cola local → sync
                              ↓
                     Panel: tablero en vivo
                              ↓
                        CSV final → ERP
```

**Vinculación de celulares:** el panel genera códigos QR que contienen la dirección del servidor. No se configuran IPs a mano. Si la IP cambia, se regenera el QR.

**Elección de Android nativo sobre PWA:** la velocidad y tolerancia del escaneo (códigos gastados, poca luz, reflejos) determina si la herramienta se usa o se abandona en un conteo de miles de ítems. ML Kit es netamente superior a las alternativas web, y la app nativa evita la restricción de contexto seguro que bloquea la cámara en HTTP sobre red local.

## 4. Modelo de datos

### Principio: todo es un evento, nada se pisa

Cada escaneo genera una fila nueva. El total contado de un SKU es la suma de sus filas dentro de la ronda vigente. Nada se sobreescribe ni se borra. Esto hace que la sincronización sea idempotente y que el conteo sea auditable de punta a punta.

### Tablas del servidor

**`sesion`** — cada inventario (cliente + fecha)
```
id, nombre, fecha_creacion, estado (abierta | cerrada),
tolerancia_pct, tolerancia_min_abs
```

**`ronda`** — cada pasada de conteo dentro de una sesión
```
id, sesion_id, numero, estado (abierta | cerrada), fecha_apertura, fecha_cierre
```

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
uuid, sesion_id, ronda_id, articulo_id, cantidad, operario_id,
ubicacion_real (nullable), observaciones (nullable),
timestamp_dispositivo, timestamp_servidor,
anula_uuid (nullable)
```

**`recuento_item`** — qué SKUs entran en una ronda de recuento
```
ronda_id, articulo_id
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

Dentro de una misma ronda, escanear repetidamente el mismo SKU **suma**. Cubre el caso de un producto presente en varias ubicaciones o contado por dos personas. Dos operarios contando el mismo SKU en simultáneo no generan conflicto: cada uno aporta su parte.

### Rondas de recuento

- La **ronda 1** es el conteo inicial y abarca todo el maestro.
- Al cerrarla, el panel lista las diferencias. Se marcan los SKUs a recontar (manualmente o con "todos los que están fuera de tolerancia") y se abre la **ronda 2**.
- En una ronda de recuento, la app **solo acepta los SKUs marcados**. Si el operario escanea otro, la app avisa *"este artículo no está en el recuento"* y no lo carga.
- **Cada ronda cuenta desde cero y reemplaza a la anterior** para esos SKUs. Si en R1 contaron 48 y en R2 cuentan 50, el valor vigente es 50. Sumar daría 98, que no significa nada.
- Un SKU no incluido en una ronda conserva como vigente el valor de la última ronda en que fue contado.
- **El recuento también es a ciegas:** el operario no ve lo que se contó en la ronda anterior, ni propio ni ajeno. De lo contrario el recuento tendería a confirmar el primer conteo en lugar de verificarlo.
- Se pueden abrir tantas rondas como haga falta, en días distintos. Todas quedan visibles en paralelo en el tablero.
- La sesión permanece abierta hasta que las diferencias se acuerdan con el cliente. Al cerrarla se congela todo.

**Valor vigente de un SKU:** suma de sus conteos no anulados en la ronda de número más alto en la que fue contado.

### Tolerancia

Un artículo está **dentro de tolerancia** si:

```
|contado - stock_sistema| <= max(|stock_sistema| * tolerancia_pct, tolerancia_min_abs)
```

El valor absoluto sobre `stock_sistema` cubre el caso de stock teórico negativo, que algunos ERP arrastran por errores de carga.

Valores por defecto: **2%** con mínimo de **1 unidad**. Configurables por sesión desde el panel.

La tolerancia es solo un cálculo, no altera datos. Puede cambiarse en cualquier momento y el tablero recalcula al instante — sirve para negociar el criterio con el cliente viendo el impacto real.

Estados resultantes: **sin contar** (⬜), **dentro de tolerancia** (✅), **fuera de tolerancia** (⚠️).

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
│ Ronda 2          Juan   ⚡3 │  ← ronda · operario · pendientes de sync
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
- **Lista de recuento** — en rondas de recuento, los SKUs asignados con su ubicación, para ir tachando.
- **Indicador de sincronización** — cuántos conteos faltan subir. Verde = todo al día. Nunca bloquea el trabajo.

## 7. Sincronización

- Cada conteo nace en el celular con un `uuid` propio y se guarda primero en la base local.
- Un proceso en segundo plano empuja los pendientes apenas hay red. Si no hay, se acumulan sin interrumpir.
- El servidor descarta los `uuid` ya recibidos: reenviar es inofensivo.
- Como los conteos suman dentro de la ronda y nunca se editan, no existen conflictos de escritura concurrente.
- Las anulaciones viajan como eventos más, con la misma garantía.
- El celular puede permanecer sin señal indefinidamente sin perder trabajo.

## 8. Importación y exportación CSV

### Importación

Se arrastra el CSV del ERP al panel y aparece una tabla de mapeo: columnas del archivo a la izquierda, campos del sistema a la derecha (`id_orden`, `tipo`, `material`, `sku`, `descripcion`, `grupo`, `ubicacion`, `unidad`, `stock_sistema`). Vista previa de las primeras filas antes de confirmar.

**El orden y los nombres de columna del archivo son indistintos**: todo se resuelve en el mapeo.

Si el CSV no trae `id_orden`, se genera secuencialmente (1, 2, 3…) según el orden de las filas.

Los mapeos se guardan con nombre ("Formato Tango", "Formato Cliente X"): la siguiente importación de ese cliente es un clic.

### Exportación

**Resumen por SKU:**
```
id_orden | tipo | material | sku | descripcion | grupo | ubicacion | ubicacion_real |
unidad | stock_sistema | contado | dif | estado | fecha | observaciones
```

- `contado`, `dif` y `estado` son calculados sobre el valor vigente.
- `fecha` es la del **último conteo registrado** para ese artículo. Vacía si no se contó.
- `ubicacion_real` queda vacía si nadie la corrigió. Si hubo varias correcciones, se muestra la última y las observaciones se concatenan.
- Con rondas activas se agregan columnas `R1`, `R2`, `R3`… con el contado de cada ronda.

**Detalle línea por línea:** cada escaneo con operario, hora, ronda, ubicación real y observaciones.

Ambos se pueden exportar **con los filtros del tablero aplicados** (por ejemplo, solo las diferencias).

## 9. Panel web

**Sesiones** — crear, abrir, cerrar. Solo una sesión abierta a la vez, para que ningún celular se confunda de inventario. Configuración de tolerancia por sesión.

**Importar maestro** — mapeo de columnas con vista previa y formatos guardados (ver sección 8).

**Tablero en vivo** — tabla completa, refresco automático cada pocos segundos:

```
id_orden | tipo | material | sku | descripcion | grupo | ubicacion | ubicacion_real |
unidad | stock_sistema | contado | dif | estado | fecha | observaciones
```

- Métricas superiores: % contado, SKUs contados / totales, unidades contadas, diferencias detectadas, altas rápidas pendientes, correcciones de ubicación.
- Filtros combinables por `tipo`, `material`, `grupo`, `ubicacion`, estado (sin contar / dentro de tolerancia / fuera de tolerancia / ubicación corregida / ubicación nueva / alta rápida) y operario.
- Avance por grupo y por ubicación, para saber dónde falta gente.
- Detección de artículos contados en una ubicación distinta a la esperada.
- Ordenamiento por cualquier columna.

**Rondas** — cerrar la ronda actual, revisar diferencias, marcar SKUs a recontar (manual o "todos los fuera de tolerancia"), abrir la siguiente. Vista comparativa de todas las rondas.

**Operarios** — alta con nombre y PIN opcional, QR personal por operario, QR de instalación del APK, estado de conexión, cuánto lleva contado cada uno y si alguno tiene conteos sin sincronizar.

## 10. Instalación y operación

**En la PC:** carpeta autocontenida con el servidor y su propio Python. Doble clic en `Iniciar servidor.bat` y se abre el panel en el navegador. Sin instalación previa ni configuración de rutas. La primera ejecución requiere aceptar el permiso de firewall de Windows para redes privadas; sin eso los celulares no alcanzan el servidor.

**Backup:** toda la base es el archivo `inventario.db`. Copiarlo respalda maestro, conteos, rondas y observaciones. El servidor genera una copia automática al cerrar cada ronda.

**En los celulares:** QR de instalación → APK → QR personal. Android 8+.

## 11. Testing

**Automatizado (backend)** — cubre lo que puede fallar en silencio y costar caro:
- Importación con CSVs mal formados: columnas faltantes, encabezados duplicados, filas incompletas, codificaciones distintas, separadores `,` y `;`, decimales con coma y con punto.
- Cálculo del valor vigente por ronda, incluyendo SKUs no incluidos en rondas posteriores.
- Tolerancia en los bordes: diferencia exactamente igual al límite, stock cero, stock negativo.
- Idempotencia de la sincronización: reenvío del mismo `uuid`, reenvíos parciales, orden alterado.
- Anulaciones: anular un conteo ya anulado, anular un conteo de una ronda cerrada.
- Restricción de SKUs en rondas de recuento.
- Que `stock_sistema` no aparezca en ninguna respuesta de la API destinada a la app.

**Manual (app)** — con una tanda de códigos reales:
- Escaneo con códigos gastados, con reflejo y con poca luz.
- Corte de WiFi a mitad del conteo: verificar que no se pierda ningún escaneo y que sincronice al volver.
- Alta rápida y corrección de ubicación completas.

**Datos de prueba:** se genera un CSV de ejemplo con artículos y códigos reales para recorrer el circuito completo antes de usarlo en un cliente.

## 12. Fuera de alcance

Deliberadamente excluido:

- **Conversión entre unidades** (contar cajas de un artículo medido en kg). Requeriría factores de conversión por artículo; se descartó por decisión explícita.
- **iOS.** No hay necesidad; agregarlo obligaría a un stack multiplataforma sin beneficio.
- **Acceso desde fuera de la red local.** El servidor opera en la LAN del cliente durante el conteo.
- **Integración automática con el ERP.** El intercambio es por CSV en ambos sentidos.
- **Multi-cliente simultáneo en el servidor.** Una sesión abierta a la vez.
- **Botón "+1"** para carga rápida de unidades. Descartado: las cantidades se ingresan siempre por teclado numérico.
