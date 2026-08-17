# Control de Stock

Toma de inventario con escaneo de códigos de barras. El servidor corre en
una PC y los celulares se conectan por la red WiFi del lugar.

## Cómo se usa

1. Doble clic en **Iniciar servidor.bat**. La primera vez tarda un poco
   más porque prepara el entorno.
2. Windows va a pedir permiso de firewall: hay que **aceptarlo para redes
   privadas**. Sin eso los celulares no llegan al servidor.
3. Se abre una ventana negra con dos direcciones. La de `127.0.0.1` es
   para esta PC; la otra es la que usan los celulares.
4. Abrir el panel en el navegador, crear una sesión e importar el maestro.

Dejá la ventana negra abierta mientras dure el conteo.

## El circuito

- **Sesiones**: se crea una sesión por inventario. Solo puede haber una
  abierta a la vez, porque los celulares se vinculan a «la» sesión abierta.
- **Importar maestro**: se elige el CSV que exporta el sistema de gestión y
  se indica en pantalla qué columna es cada campo. El separador y la
  codificación se detectan solos.
- **Operarios**: cada uno recibe un token, que es con lo que se vincula su
  dispositivo. Con una sesión abierta, el botón «Sectores» de cada persona
  abre un cuadro para elegir qué ubicaciones le tocan en el conteo en
  curso. No es obligatorio ni bloquea nada: es para repartir el trabajo y
  saber después si alguien contó algo que no le tocaba.
- **Tablero**: se refresca solo cada cuatro segundos, conservando los
  filtros y la posición de la pantalla. Un artículo con algún conteo hecho
  fuera del sector asignado a quien lo contó queda marcado con «⚑ fuera de
  sector».
- **Avance por ubicación**: una pestaña aparte con una fila por artículo —
  ubicación, a quién le toca, quién lo contó, cuánto y estado—, con sus
  propios filtros y su propia exportación. Las ubicaciones que nadie tiene
  asignadas quedan marcadas «⚑ sin asignar»: es la forma de darse cuenta,
  antes de cerrar el inventario, de que hay un sector que nadie va a contar.
- **Recuento**: al cerrar (o sin cerrar) el conteo, la pestaña lista los SKU
  «A recontar» — los que quedaron fuera de la tolerancia configurada acá
  mismo. Se marcan a mano los que van a recuento (arranca vacío, a
  propósito) y «Abrir recuento» crea un Conteo 2 con esos SKU. Se le asigna
  por ubicación a un operario, igual que en Operarios, y mientras ese
  recuento esté abierto su celular **solo acepta contar esos SKU** — el
  resto avisa sin bloquear la app. Pueden convivir varios recuentos abiertos
  a la vez, pero un mismo operario nunca puede estar asignado a dos a la
  vez. No hace falta volver a vincular el celular: en cuanto se refresca la
  lista, «Lo mío» muestra la etiqueta de la pasada nueva.
- **Exportar**: resumen por SKU, detalle escaneo por escaneo, y el reparto de
  la pestaña de avance — los tres con los filtros que estén puestos en su
  pantalla. El detalle trae una columna `fuera_asignacion` (`SI` o vacío) que
  dice, escaneo por escaneo, cuáles se hicieron fuera del sector asignado.

El conteo es a ciegas: ninguna respuesta al celular incluye el stock del
sistema ni el costo.

## Instalar la app en los celulares

Copiá el APK compilado a `servidor/app.apk`. Con el archivo ahí, la solapa
**Operarios** muestra un código QR para descargarlo: se escanea con la cámara
del celular y se instala. La primera vez, Android pide permiso para instalar
desde esta fuente.

Si el archivo no está, el panel no muestra nada — no hay nada que descargar.
No hace falta reiniciar el servidor al copiarlo: alcanza con recargar la
página.

Cada operario tiene además **su propio QR** en esa misma solapa, con el que se
vincula su celular. Lleva adentro la dirección del servidor y su token, así no
hay que tipear ninguno de los dos.

Al vincularse, el celular abre siempre en **«Lo mío»**: la lista de las
ubicaciones que le fueron asignadas, con sus artículos y un tilde en los que
ya contó. Sin asignación, la lista sale vacía con un aviso, pero el botón
«Contar» funciona igual — no se bloquea nada, y sigue pudiendo contar
cualquier cosa como antes de que esta pantalla existiera. Un botón
«Actualizar», y automáticamente al abrir la app o volver del fondo, piden al
servidor la asignación vigente; sin señal se sigue mostrando la última que
bajó.

Debajo del título, «Lo mío» muestra en qué pasada está contando el operario
—«Conteo 1», o «Conteo 2» si le tocó un recuento—. Durante un recuento el
celular solo acepta los SKU que le marcaron: escanear cualquier otro avisa
con un cartel («No corresponde a este conteo») sin bloquear la app y sin
ofrecer darlo de alta, porque el artículo ya existe.

## La base de datos

Todo vive en `servidor/inventario.db`. Copiar ese archivo respalda el
inventario completo. No está en git a propósito: git no es el backup de
los datos.

## Para desarrollar

```bash
cd servidor
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest tests/ -v
```

Las cantidades se guardan como enteros en milésimas y los importes en
centavos. Sumar decimales en punto flotante acumula error, y un inventario
suma miles de veces.
