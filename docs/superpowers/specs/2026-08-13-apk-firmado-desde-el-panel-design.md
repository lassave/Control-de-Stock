# El APK firmado que se baja desde el panel — diseño

Fecha: 2026-08-13

## El problema

El panel ya tiene todo lo necesario para repartir la app: la pestaña de
Operarios trae un bloque con un QR de instalación y un enlace de descarga,
y el servidor entrega el archivo en `/app.apk`. Está escondido porque el
panel lo muestra solo cuando encuentra el archivo **en `servidor/app.apk`**
—esa carpeta y no la raíz del proyecto: la ruta la arma `panel.py` desde su
propia ubicación— y ese archivo no existe.

No existe porque **el proyecto no tiene configuración de firma**. Hoy
`assembleRelease` produce un APK sin firmar, que Android no instala. El único
instalable es el de debug, firmado con una clave de prueba que **cada máquina
genera por su cuenta**: sirve para probar por USB, no para entregar.

Mientras eso siga así, cada celular que se suma al inventario pasa por un
cable.

## Lo que manda sobre el diseño

**Android solo actualiza una app si la firma es la misma que la instalada.**
Con una firma distinta el instalador falla, y la única salida es desinstalar
—que borra la base local del celular, incluidos los conteos que todavía no
subieron—.

**La clave no puede vivir en la carpeta del proyecto.** Esa carpeta es la que
se copia a la PC del cliente para correr el servidor: una clave adentro
viajaría con ella. La firma es lo único que impide que un tercero publique
una actualización que los celulares acepten como nuestra.

**El APK se compila acá, no en la PC del cliente.** Allá solo corre el
servidor: no hay Android SDK ni Gradle.

## La clave

Se crea **una vez** un almacén de claves fuera del proyecto —`C:\clientes\claves\`—
junto a un archivo con sus contraseñas. El build lo lee de ahí.

**Si ese archivo no está, la compilación de release falla con un mensaje que
dice qué falta y cómo crearlo.** El modo de fallar importa: sin eso, Gradle
produce en silencio un APK sin firmar, que se copia, se publica, y falla
recién en el celular del operario con un error de Android que no explica
nada.

El respaldo de esa carpeta es parte del trabajo. Perderla significa que
ningún celular con la app instalada puede volver a actualizarse sin
desinstalar.

## El número de versión

Android también exige que cada versión publicada tenga un número **mayor** que
la instalada. Hoy está fijo en 1 y nadie lo mueve, así que la segunda
actualización no se instalaría.

El número sale de **cuántos commits lleva el repositorio** (`git rev-list
--count HEAD`): sube solo, no hay forma de olvidarse y no hay forma de
publicar dos veces el mismo. Aparte va un nombre legible con la fecha
—`2026-08-13`— para poder decir «el celular tiene la del martes».

**Si el comando de git no está disponible, la compilación de release falla**,
igual que sin la clave. Un número inventado —un cero, o el 1 de siempre—
produce un APK que no se puede instalar encima del anterior, y el síntoma
aparece recién en el celular del operario.

## Cómo se publica

Un archivo **`Publicar app.bat`** en la raíz, al lado del `Iniciar
servidor.bat` que ya existe y con la misma idea: se toca dos veces y hace
todo. Compila el release firmado, lo deja como `app.apk` donde el panel lo
busca, y al terminar dice qué versión publicó.

Cuando ese archivo existe, el bloque de instalación aparece solo en la pestaña
de Operarios, con su QR.

**El QR de vinculación de cada operario no se toca.** Son dos cosas distintas
y conviven: el de instalación es uno solo, arriba de la pestaña, y sirve para
bajar la app; el de vinculación está en la fila de cada persona y sirve para
conectar ese celular al servidor con su nombre.

## El panel muestra qué versión está ofreciendo

Junto al QR, el panel dice qué versión es el APK que está entregando.

Resuelve un problema real y ya conocido: al entregar una actualización hay que
poder mirar el panel del cliente y saber si tiene la vieja o la nueva. Sin
eso, la única forma de averiguarlo es desinstalar la app de un celular y
reinstalarla para comparar.

**De dónde sale ese dato.** La versión vive adentro del APK, en un formato
binario que hay que interpretar con herramientas del SDK de Android — que en
la PC del cliente no están. Así que se resuelve con dos datos que se sostienen
entre sí:

- **La fecha de publicación** sale del archivo `app.apk` mismo, de cuándo fue
  escrito. No la escribe nadie y no puede desactualizarse.
- **La versión** la escribe `Publicar app.bat` en un archivo chico al lado del
  APK, en el mismo movimiento en que lo copia. Los dos se mueven juntos porque
  los produce el mismo comando.

Si ese archivo no está —alguien copió un APK a mano— el panel muestra solo la
fecha, que es el dato que igual responde la pregunta. Preferimos eso a
inventar una versión que podría ser falsa.

## Cómo se prueba

- **El servidor**, con sus tests: que `/api/instalacion` informe la versión
  del APK que hay, y que sin archivo siga contestando que no hay nada para
  instalar en vez de romperse.
- **El panel**, con los tests de escapado y estructura que ya existen: que la
  versión salga escapada como todo lo que viene del servidor.
- **La compilación sin la clave**: que falle con el mensaje que explica qué
  falta, y no con un APK sin firmar.
- **En el celular, y es la que vale**: instalar desde el QR del panel —sin
  cable—, contar algo sin subirlo, publicar una versión nueva, instalarla
  **encima desde el QR**, y verificar que la app abre y que el conteo
  pendiente sigue ahí. Es la prueba de que la firma y el número de versión
  están bien: con la firma mal, Android rechaza la instalación; con el número
  mal, la rechaza igual pero por otro motivo.

## Lo que queda afuera, a propósito

- **Actualización automática.** Que la app avise que hay una versión nueva y
  se actualice sola es otro trabajo, con su propio diseño.
- **Publicar en Google Play.** El sistema se instala en la red del cliente,
  fuera de la tienda, y así se queda.
- **Firmar también la variante de debug.** La de debug sigue como está: se
  instala por cable durante el desarrollo y no se reparte.
