"""Endpoints que consume el panel web."""

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app import red
from app.repos import operarios, sesiones
from app.servicios import exportacion, importacion, tablero, vinculacion

router = APIRouter(prefix="/api")

# Marca de orden de bytes. Sin ella, el Excel de un Windows en español lee
# el CSV como cp1252 y las descripciones con acentos llegan ilegibles.
BOM = "﻿"

# El APK se deja junto al servidor cuando hay una versión compilada. No está
# en git: es un binario que se regenera, y el repositorio no es su lugar.
RUTA_APK = Path(__file__).parent.parent.parent / "app.apk"

MEDIA_APK = "application/vnd.android.package-archive"


def _con(request):
    return request.app.state.con


def _no_encontrada(error):
    """Traduce el «no existe la sesión» de los repos a un 404.

    Sin esto, pedir una sesión borrada devuelve un 500 y el panel muestra
    «error del servidor» cuando lo único que pasó es que no está.
    """
    return HTTPException(status_code=404, detail=str(error))


@router.get("/sesiones")
def listar_sesiones(request: Request):
    return sesiones.listar(_con(request))


@router.post("/sesiones")
async def crear_sesion(request: Request):
    cuerpo = await request.json()
    con = _con(request)
    try:
        sesion_id = sesiones.crear(con, cuerpo["nombre"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    sesion = sesiones.obtener(con, sesion_id)
    sesion["pasada"] = sesiones.pasada_abierta(con, sesion_id)
    return sesion


@router.get("/sesiones/{sesion_id}")
def ver_sesion(sesion_id: int, request: Request):
    con = _con(request)
    try:
        sesion = sesiones.obtener(con, sesion_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    if sesion["estado"] == "abierta":
        sesion["pasada"] = sesiones.pasada_abierta(con, sesion_id)
    return sesion


@router.post("/sesiones/{sesion_id}/cerrar")
def cerrar_sesion(sesion_id: int, request: Request):
    try:
        sesiones.cerrar(_con(request), sesion_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return {"estado": "cerrada"}


@router.put("/sesiones/{sesion_id}/tolerancia")
async def fijar_tolerancia(sesion_id: int, request: Request):
    cuerpo = await request.json()
    con = _con(request)
    try:
        sesiones.fijar_tolerancia(con, sesion_id, cuerpo["pct"], cuerpo["min_abs"])
    except ValueError as error:
        # «No existe la sesión» es un 404; una tolerancia mal escrita es un
        # 400: el panel muestra mensajes distintos para cada caso.
        if "No existe la sesión" in str(error):
            raise _no_encontrada(error) from error
        raise HTTPException(status_code=400, detail=str(error)) from error

    return sesiones.obtener(con, sesion_id)


@router.post("/maestro/previsualizar")
async def previsualizar_maestro(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    try:
        return importacion.previsualizar(contenido)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sesiones/{sesion_id}/maestro")
async def importar_maestro(
    sesion_id: int,
    request: Request,
    archivo: UploadFile = File(...),
    mapeo: str = Form(...),
    unidad_por_defecto: str = Form("UN"),
):
    contenido = await archivo.read()
    try:
        definicion = json.loads(mapeo)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail="El mapeo no es válido") from error

    try:
        return importacion.importar(
            _con(request), sesion_id, contenido, definicion, unidad_por_defecto
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _filtros(tipo, material, grupo, ubicacion, estado, texto, solo_errores_carga):
    return {
        "tipo": tipo, "material": material, "grupo": grupo,
        "ubicacion": ubicacion, "estado": estado, "texto": texto,
        "solo_errores_carga": solo_errores_carga,
    }


@router.get("/sesiones/{sesion_id}/tablero")
def ver_tablero(
    sesion_id: int,
    request: Request,
    tipo: str = "", material: str = "", grupo: str = "",
    ubicacion: str = "", estado: str = "", texto: str = "",
    solo_errores_carga: bool = False,
):
    con = _con(request)
    filtros = _filtros(
        tipo, material, grupo, ubicacion, estado, texto, solo_errores_carga
    )
    try:
        return {
            "filas": tablero.filas(con, sesion_id, filtros),
            "resumen": tablero.resumen(con, sesion_id),
        }
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.get("/sesiones/{sesion_id}/resumen")
def ver_resumen(sesion_id: int, request: Request):
    try:
        return tablero.resumen(_con(request), sesion_id)
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.get("/operarios")
def listar_operarios(request: Request):
    return operarios.listar(_con(request))


@router.post("/operarios")
async def crear_operario(request: Request):
    cuerpo = await request.json()
    try:
        return operarios.crear(_con(request), cuerpo["nombre"], cuerpo.get("pin"))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/operarios/{operario_id}/qr")
def qr_de_operario(operario_id: int, request: Request):
    """El QR con el que se vincula un celular: dirección del servidor y token.

    La dirección sale de la IP de la red local y no del pedido: el panel se
    abre en 127.0.0.1, y ese QR mandaría al celular a sí mismo.
    """
    operario = operarios.obtener(_con(request), operario_id)
    if operario is None:
        raise HTTPException(
            status_code=404, detail=f"No existe el operario {operario_id}"
        )

    url = vinculacion.armar_url(red.ip_local(), request.url.port or 8000)
    texto = vinculacion.contenido(url, operario["token_dispositivo"])

    return Response(content=vinculacion.svg(texto), media_type="image/svg+xml")


@router.get("/sesiones/{sesion_id}/exportar/{tipo_exportacion}")
def exportar(
    sesion_id: int,
    tipo_exportacion: str,
    request: Request,
    tipo: str = "", material: str = "", grupo: str = "",
    ubicacion: str = "", estado: str = "", texto: str = "",
    solo_errores_carga: bool = False,
):
    """Exporta lo que el panel está mostrando, con sus mismos filtros.

    Sin los filtros, quien exporta después de acotar el tablero recibe el
    depósito entero y lo lee como si fuera lo que tenía en pantalla.
    """
    con = _con(request)
    filtros = _filtros(
        tipo, material, grupo, ubicacion, estado, texto, solo_errores_carga
    )

    if tipo_exportacion == "resumen":
        generar = exportacion.resumen_por_sku
    elif tipo_exportacion == "detalle":
        generar = exportacion.detalle
    else:
        raise HTTPException(
            status_code=404, detail=f"No existe la exportación «{tipo_exportacion}»"
        )

    try:
        texto_csv = generar(con, sesion_id, filtros)
    except ValueError as error:
        raise _no_encontrada(error) from error

    return Response(
        content=BOM + texto_csv,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="{tipo_exportacion}-{sesion_id}.csv"'
        },
    )


def _url_de_instalacion(request):
    base = vinculacion.armar_url(red.ip_local(), request.url.port or 8000)
    return f"{base}/app.apk"


@router.get("/instalacion")
def estado_de_instalacion(request: Request):
    """Si hay APK para instalar y desde qué dirección se baja."""
    if not RUTA_APK.exists():
        return {"disponible": False, "url": ""}
    return {"disponible": True, "url": _url_de_instalacion(request)}


@router.get("/instalacion/qr")
def qr_de_instalacion(request: Request):
    if not RUTA_APK.exists():
        raise HTTPException(
            status_code=404, detail="Todavía no hay una app para instalar"
        )

    return Response(
        content=vinculacion.svg(_url_de_instalacion(request)),
        media_type="image/svg+xml",
    )
