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
- **Exportar**: resumen por SKU y detalle escaneo por escaneo, los dos con
  los filtros que estén puestos en el tablero. El detalle trae una columna
  `fuera_asignacion` (`SI` o vacío) que dice, escaneo por escaneo, cuáles
  se hicieron fuera del sector asignado.

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
