"""Punto de entrada del servidor."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.api import dispositivos, panel

RUTA_PANEL = Path(__file__).parent.parent / "panel"
RUTA_DB_POR_DEFECTO = Path(__file__).parent.parent / "inventario.db"


def crear_app(ruta_db=None):
    ruta = str(ruta_db or RUTA_DB_POR_DEFECTO)

    @asynccontextmanager
    async def ciclo_de_vida(app):
        app.state.con = db.conectar(ruta)
        db.crear_esquema(app.state.con)
        yield
        app.state.con.close()

    app = FastAPI(title="Control de Stock", lifespan=ciclo_de_vida)
    app.include_router(panel.router)
    app.include_router(dispositivos.router)

    # El panel se monta al final y en la raíz: cualquier ruta que no haya
    # tomado un router de la API cae acá como archivo estático.
    if RUTA_PANEL.exists():
        app.mount("/", StaticFiles(directory=RUTA_PANEL, html=True), name="panel")

    return app


app = crear_app()
