"""Captura del servidor real las respuestas que la app va a parsear.

Se corre a mano cuando el contrato cambia a propósito. Los archivos que
genera son la referencia compartida: la app se prueba contra ellos y
`servidor/tests/test_contrato.py` verifica que el servidor los siga
cumpliendo.

Uso, con el servidor levantado en el puerto 8000:
    servidor\\.venv\\Scripts\\python.exe celular\\contrato\\capturar.py
"""

import json
import sys
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
DESTINO = Path(__file__).parent

CSV = (
    "sku,descripcion,unidad,ubicacion,stock\n"
    "7790001001234,Fideos guisero 500g,UN,P-1,50\n"
    "7790002005678,Aceite girasol 900ml,UN,P-2,30\n"
).encode("utf-8")


def guardar(nombre, datos):
    ruta = DESTINO / f"{nombre}.json"
    ruta.write_text(
        json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"escrito {ruta.name}")


def main():
    with httpx.Client(base_url=BASE, timeout=10) as c:
        # Este script crea sesiones y artículos de mentira. Correrlo contra el
        # servidor de un cliente le mete basura al inventario en curso, y la
        # dirección por defecto es justamente la que levanta «Iniciar
        # servidor.bat». Si hay algo cargado, no se toca nada.
        existentes = c.get("/api/sesiones").json()
        if existentes:
            print(
                "Este servidor ya tiene sesiones cargadas. Capturá el contrato "
                "contra un servidor vacío: el script crea datos de prueba y no "
                "es para la PC de un cliente.",
                file=sys.stderr,
            )
            return 1

        sesion = c.post("/api/sesiones", json={"nombre": "Contrato"}).json()
        c.post(
            f"/api/sesiones/{sesion['id']}/maestro",
            files={"archivo": ("m.csv", CSV, "text/csv")},
            data={"mapeo": json.dumps({
                "sku": "sku", "descripcion": "descripcion",
                "unidad": "unidad", "ubicacion": "ubicacion",
                "stock_sistema": "stock",
            })},
        )

        operario = c.post("/api/operarios", json={"nombre": "Contrato"}).json()
        cab = {"X-Token": operario["token_dispositivo"]}

        guardar("vinculacion", c.post("/api/dispositivo/vincular", headers=cab).json())
        guardar("maestro", c.get("/api/dispositivo/maestro", headers=cab).json())

        # El pedido es la otra mitad del contrato: son los nombres que la app
        # escribe. Vive en su propio archivo para que los dos lados lo fijen,
        # en vez de existir solo como literal acá adentro.
        pedido = json.loads(
            (DESTINO / "conteos-pedido.json").read_text(encoding="utf-8")
        )
        guardar("conteos-respuesta", c.post(
            "/api/dispositivo/conteos", headers=cab, json=pedido,
        ).json())

        guardar("alta-rapida", c.post(
            "/api/dispositivo/articulos", headers=cab,
            json={"codigo": "7790009999999", "descripcion": "Sin etiqueta",
                  "unidad": "UN", "ubicacion": "P-9"},
        ).json())

        c.post(f"/api/sesiones/{sesion['id']}/cerrar")


if __name__ == "__main__":
    sys.exit(main())
