"""Endpoints que consume el panel web."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app import red, reloj
from app.api.auth import requerir_superusuario, verificar_sesion
from app.repos import asignaciones, cuentas_panel, operarios, pasada_item, proyectos
from app.servicios import exportacion, importacion, novedades, reparto, tablero, vinculacion

router = APIRouter(prefix="/api", dependencies=[Depends(verificar_sesion)])

# Marca de orden de bytes. Sin ella, el Excel de un Windows en español lee
# el CSV como cp1252 y las descripciones con acentos llegan ilegibles.
BOM = "﻿"

# El APK se deja junto al servidor cuando hay una versión compilada. No está
# en git: es un binario que se regenera, y el repositorio no es su lugar.
RUTA_APK = Path(__file__).parent.parent.parent / "app.apk"

# A diferencia del APK, este sí está en git: lo mantiene a mano quien
# publica, no lo genera ninguna compilación.
RUTA_NOVEDADES = Path(__file__).parent.parent.parent / "novedades.md"

MEDIA_APK = "application/vnd.android.package-archive"


def _con(request):
    return request.app.state.con


def _no_encontrada(error):
    """Traduce el «no existe el proyecto» de los repos a un 404.

    Sin esto, pedir un proyecto borrado devuelve un 500 y el panel muestra
    «error del servidor» cuando lo único que pasó es que no está.
    """
    return HTTPException(status_code=404, detail=str(error))


@router.get("/proyectos")
def listar_proyectos(request: Request):
    return proyectos.listar(_con(request))


@router.post("/proyectos")
async def crear_proyecto(request: Request):
    cuerpo = await request.json()
    con = _con(request)
    try:
        proyecto_id = proyectos.crear(con, cuerpo["nombre"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    proyecto = proyectos.obtener(con, proyecto_id)
    proyecto["pasada"] = proyectos.pasada_general_abierta(con, proyecto_id)
    return proyecto


@router.get("/proyectos/{proyecto_id}")
def ver_proyecto(proyecto_id: int, request: Request):
    con = _con(request)
    try:
        proyecto = proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    if proyecto["estado"] == "abierta":
        proyecto["pasada"] = proyectos.pasada_general_abierta(con, proyecto_id)
    return proyecto


@router.post("/proyectos/{proyecto_id}/cerrar")
def cerrar_proyecto(proyecto_id: int, request: Request):
    try:
        proyectos.cerrar(_con(request), proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return {"estado": "cerrada"}


@router.put("/proyectos/{proyecto_id}/tolerancia")
async def fijar_tolerancia(proyecto_id: int, request: Request):
    cuerpo = await request.json()
    con = _con(request)
    try:
        proyectos.fijar_tolerancia(con, proyecto_id, cuerpo["pct"], cuerpo["min_abs"])
    except ValueError as error:
        # «No existe el proyecto» es un 404; una tolerancia mal escrita es un
        # 400: el panel muestra mensajes distintos para cada caso.
        if "No existe el proyecto" in str(error):
            raise _no_encontrada(error) from error
        raise HTTPException(status_code=400, detail=str(error)) from error

    return proyectos.obtener(con, proyecto_id)


@router.get("/proyectos/{proyecto_id}/pasadas")
def listar_pasadas(proyecto_id: int, request: Request):
    con = _con(request)
    try:
        proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return proyectos.listar_pasadas(con, proyecto_id)


@router.post("/proyectos/{proyecto_id}/pasadas")
async def abrir_pasada(proyecto_id: int, request: Request):
    con = _con(request)
    cuerpo = await request.json()

    articulo_ids = cuerpo.get("articulo_ids")
    if not isinstance(articulo_ids, list):
        raise HTTPException(
            status_code=400, detail="«articulo_ids» tiene que ser una lista"
        )

    try:
        proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    try:
        return proyectos.abrir_pasada(con, proyecto_id, articulo_ids)
    except ValueError as error:
        if "está cerrado" in str(error):
            raise HTTPException(status_code=409, detail=str(error)) from error
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/proyectos/{proyecto_id}/pasadas/{pasada_id}")
def borrar_pasada(proyecto_id: int, pasada_id: int, request: Request):
    con = _con(request)
    try:
        proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    try:
        proyectos.borrar_pasada(con, proyecto_id, pasada_id)
    except ValueError as error:
        mensaje = str(error)
        if "No existe la pasada" in mensaje:
            raise _no_encontrada(error) from error
        if "Ya tiene conteos" in mensaje:
            raise HTTPException(status_code=409, detail=mensaje) from error
        raise HTTPException(status_code=400, detail=mensaje) from error

    return {"borrada": True}


@router.get("/proyectos/{proyecto_id}/pasadas/{pasada_id}/avance")
def ver_avance_de_pasada(proyecto_id: int, pasada_id: int, request: Request):
    con = _con(request)
    try:
        proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    try:
        return reparto.avance_de_pasada(con, proyecto_id, pasada_id)
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.post("/maestro/previsualizar")
async def previsualizar_maestro(archivo: UploadFile = File(...)):
    contenido = await archivo.read()
    try:
        return importacion.previsualizar(contenido)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/proyectos/{proyecto_id}/maestro")
async def importar_maestro(
    proyecto_id: int,
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
            _con(request), proyecto_id, contenido, definicion, unidad_por_defecto
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _filtros(tipo, material, grupo, ubicacion, estado, texto, solo_errores_carga):
    return {
        "tipo": tipo, "material": material, "grupo": grupo,
        "ubicacion": ubicacion, "estado": estado, "texto": texto,
        "solo_errores_carga": solo_errores_carga,
    }


@router.get("/proyectos/{proyecto_id}/tablero")
def ver_tablero(
    proyecto_id: int,
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
            "filas": tablero.filas(con, proyecto_id, filtros),
            "resumen": tablero.resumen(con, proyecto_id),
        }
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.get("/proyectos/{proyecto_id}/reparto")
def ver_reparto(
    proyecto_id: int,
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
        return {"filas": reparto.filas(con, proyecto_id, filtros)}
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.get("/proyectos/{proyecto_id}/reparto/operarios")
def ver_avance_por_operario(
    proyecto_id: int,
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
        return {"operarios": reparto.avance_por_operario(con, proyecto_id, filtros)}
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.get("/proyectos/{proyecto_id}/resumen")
def ver_resumen(proyecto_id: int, request: Request):
    try:
        return tablero.resumen(_con(request), proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error


@router.get("/proyectos/{proyecto_id}/ubicaciones")
def listar_ubicaciones(proyecto_id: int, request: Request):
    con = _con(request)
    try:
        proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return asignaciones.ubicaciones_distintas(con, proyecto_id)


@router.get("/operarios")
def listar_operarios(request: Request):
    return asignaciones.operarios_con_ubicaciones(_con(request))


@router.post("/operarios")
async def crear_operario(request: Request):
    cuerpo = await request.json()
    try:
        return operarios.crear(_con(request), cuerpo["nombre"], cuerpo.get("pin"))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/proyectos/{proyecto_id}/operarios/{operario_id}/asignacion")
async def asignar_ubicaciones(proyecto_id: int, operario_id: int, request: Request):
    con = _con(request)
    cuerpo = await request.json()

    ubicaciones_pedidas = cuerpo.get("ubicaciones")
    if not isinstance(ubicaciones_pedidas, list):
        raise HTTPException(
            status_code=400, detail="«ubicaciones» tiene que ser una lista"
        )

    # Con una sola pasada nunca hacía falta decirlo: se resolvía sola. Con
    # recuentos concurrentes, adivinarla ("la abierta de número más alto")
    # asignaría en silencio al recuento equivocado.
    pasada_id = cuerpo.get("pasada_id")
    if not isinstance(pasada_id, int) or isinstance(pasada_id, bool):
        raise HTTPException(
            status_code=400, detail="Falta indicar a qué pasada asignar"
        )

    try:
        proyecto = proyectos.obtener(con, proyecto_id)
    except ValueError as error:
        raise _no_encontrada(error) from error

    if proyecto["estado"] != "abierta":
        raise HTTPException(
            status_code=409,
            detail="No se puede asignar: el proyecto ya está cerrado",
        )

    if operarios.obtener(con, operario_id) is None:
        raise HTTPException(
            status_code=404, detail=f"No existe el operario {operario_id}"
        )

    pasada = proyectos.obtener_pasada(con, proyecto_id, pasada_id)
    if pasada is None:
        raise HTTPException(
            status_code=404, detail=f"No existe la pasada {pasada_id} en este proyecto"
        )
    if pasada["estado"] != "abierta":
        raise HTTPException(
            status_code=409, detail="No se puede asignar: esa pasada ya está cerrada"
        )

    # Un operario nunca puede estar en dos recuentos abiertos a la vez. No
    # se resuelve después comparando números: se impide acá, al asignar.
    if ubicaciones_pedidas and pasada_item.es_parcial(con, pasada_id):
        for otra in proyectos.pasadas_abiertas(con, proyecto_id):
            if otra["id"] == pasada_id or not pasada_item.es_parcial(con, otra["id"]):
                continue
            if asignaciones.de_operario(con, otra["id"], operario_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Ya está asignado en {otra['etiqueta']}. "
                        "Desasignalo ahí primero."
                    ),
                )

    guardadas = asignaciones.reemplazar(con, pasada_id, operario_id, ubicaciones_pedidas)
    return {"ubicaciones": guardadas}


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


@router.get("/usuarios")
def listar_usuarios(request: Request, _: dict = Depends(requerir_superusuario)):
    return cuentas_panel.listar(_con(request))


@router.post("/usuarios/{cuenta_id}/desactivar")
def desactivar_usuario(
    cuenta_id: int, request: Request, cuenta_actual: dict = Depends(requerir_superusuario)
):
    if cuenta_id == cuenta_actual["id"]:
        raise HTTPException(status_code=400, detail="No podés dar de baja tu propia cuenta")
    try:
        cuentas_panel.desactivar(_con(request), cuenta_id)
    except ValueError as error:
        raise _no_encontrada(error) from error
    return {"activo": False}


@router.get("/proyectos/{proyecto_id}/exportar/{tipo_exportacion}")
def exportar(
    proyecto_id: int,
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
    elif tipo_exportacion == "reparto":
        generar = exportacion.reparto
    else:
        raise HTTPException(
            status_code=404, detail=f"No existe la exportación «{tipo_exportacion}»"
        )

    try:
        texto_csv = generar(con, proyecto_id, filtros)
    except ValueError as error:
        raise _no_encontrada(error) from error

    return Response(
        content=BOM + texto_csv,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="{tipo_exportacion}-{proyecto_id}.csv"'
        },
    )


def _url_de_instalacion(request):
    base = vinculacion.armar_url(red.ip_local(), request.url.port or 8000)
    return f"{base}/app.apk"


def _version_publicada():
    """Qué versión dice ser el APK que hay, o vacío si nadie lo dijo.

    Lo escribe la publicación, en el mismo movimiento en que copia el APK: la
    versión vive adentro del APK, en un formato binario que solo saben leer
    las herramientas del SDK de Android, y en la PC del cliente no están.

    La ruta se arma acá adentro y no como constante del módulo: los tests
    reemplazan `RUTA_APK` para apuntarlo a un archivo temporal, y una
    constante calculada al importar seguiría mirando la carpeta de verdad.
    """
    archivo = RUTA_APK.parent / "app.apk.txt"
    if not archivo.exists():
        return ""

    try:
        # Si el archivo no es UTF-8 (PowerShell puede escribir UTF-16, cmd cp1252),
        # o es un directorio, o está bloqueado, no se puede leer sin romper
        # /api/instalacion. La regla es: si no se puede leer, se informa vacía.
        # OSError es el padre de IsADirectoryError, PermissionError, FileNotFoundError.
        contenido = archivo.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        # El archivo desapareció, es una carpeta, está sin permisos, no es UTF-8,
        # o cualquier otra razón del sistema operativo lo hace ilegible: se informa
        # como ausente.
        return ""

    # Eliminar BOM UTF-8 (U+FEFF) si está presente. PowerShell Set-Content
    # -Encoding UTF8 lo antepone.
    if contenido.startswith('﻿'):
        contenido = contenido[1:]

    # Tomar solo la primera línea, limpiar espacios en blanco, y truncar a un
    # largo sensato. El archivo puede tener varias líneas o ser muy largo. El panel
    # comparte el renglón con el QR: una versión que no cabe lo rompe.
    primera_linea = contenido.split('\n')[0].strip()[:200]

    return primera_linea


@router.get("/instalacion")
def estado_de_instalacion(request: Request):
    """Si hay APK para instalar, desde qué dirección se baja y cuál es.

    La fecha sale del archivo y no de un dato aparte: no la escribe nadie,
    así que no puede quedar desactualizada. La versión sí la escribe la
    publicación, y si falta se informa vacía en vez de inventarla.
    """
    if not RUTA_APK.exists():
        return {"disponible": False, "url": "", "version": "", "publicado": ""}

    return {
        "disponible": True,
        "url": _url_de_instalacion(request),
        "version": _version_publicada(),
        "publicado": reloj.desde_epoch(RUTA_APK.stat().st_mtime),
    }


@router.get("/novedades")
def ver_novedades():
    """Qué cambió en cada versión publicada, para quien mira el panel.

    Lista vacía y no un 404 si falta el archivo: sin novedades que mostrar
    la pestaña queda en blanco, que es preferible a un error.
    """
    if not RUTA_NOVEDADES.exists():
        return []

    return novedades.leer(RUTA_NOVEDADES.read_text(encoding="utf-8"))


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
