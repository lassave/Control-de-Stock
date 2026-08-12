"""Punto de entrada del servidor."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.api import dispositivos, panel

RUTA_PANEL = Path(__file__).parent.parent / "panel"
RUTA_DB_POR_DEFECTO = Path(__file__).parent.parent / "inventario.db"


class PanelQueSeRevalida(StaticFiles):
    """El panel, sirviéndose siempre con permiso del servidor.

    `StaticFiles` manda `ETag` y `Last-Modified` pero no `Cache-Control`, y
    con eso el navegador estima por su cuenta cuánto vale lo que ya bajó y
    lo reusa sin preguntar. Después de actualizar el sistema el panel viejo
    sigue corriendo, y no hay nada en pantalla que lo diga: acá quedó una
    pestaña con un `app.js` anterior al QR de vinculación, el celular no se
    podía vincular y el panel se veía perfecto.

    `no-cache` no prohíbe guardar: obliga a preguntar antes de reusar. Con
    el ETag, la respuesta habitual es un 304 sin cuerpo.
    """

    async def get_response(self, path, scope):
        respuesta = await super().get_response(path, scope)
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


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

    @app.get("/app.apk")
    def descargar_apk():
        """La app para instalar en el celular.

        Sin prefijo /api porque esta dirección la escanea una persona desde
        un QR: cuanto más corta, más chico y más legible el código.
        """
        if not panel.RUTA_APK.exists():
            raise HTTPException(
                status_code=404, detail="Todavía no hay una app para instalar"
            )
        return FileResponse(
            panel.RUTA_APK,
            media_type=panel.MEDIA_APK,
            filename="control-de-stock.apk",
        )

    # El panel se monta al final y en la raíz: cualquier ruta que no haya
    # tomado un router de la API cae acá como archivo estático.
    if RUTA_PANEL.exists():
        app.mount("/", PanelQueSeRevalida(directory=RUTA_PANEL, html=True), name="panel")

    return app


app = crear_app()
