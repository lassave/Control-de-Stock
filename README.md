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
  dispositivo.
- **Tablero**: se refresca solo cada cuatro segundos, conservando los
  filtros y la posición de la pantalla.
- **Exportar**: resumen por SKU y detalle escaneo por escaneo, los dos con
  los filtros que estén puestos en el tablero.

El conteo es a ciegas: ninguna respuesta al celular incluye el stock del
sistema ni el costo.

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
