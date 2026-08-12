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
        for sesion in c.get("/api/sesiones").json():
            if sesion["estado"] == "abierta":
                c.post(f"/api/sesiones/{sesion['id']}/cerrar")

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

        guardar("conteos-respuesta", c.post(
            "/api/dispositivo/conteos", headers=cab,
            json={"conteos": [
                {"uuid": "contrato-1", "codigo": "7790001001234", "cantidad": 48000,
                 "timestamp_dispositivo": "2026-08-11T10:00:00Z"},
                {"uuid": "contrato-2", "codigo": "no-existe", "cantidad": 1000,
                 "timestamp_dispositivo": "2026-08-11T10:01:00Z"},
            ]},
        ).json())

        guardar("alta-rapida", c.post(
            "/api/dispositivo/articulos", headers=cab,
            json={"codigo": "7790009999999", "descripcion": "Sin etiqueta",
                  "unidad": "UN", "ubicacion": "P-9"},
        ).json())

        c.post(f"/api/sesiones/{sesion['id']}/cerrar")


if __name__ == "__main__":
    sys.exit(main())
