"""Endpoints que consumen la app y la PWA.

Ninguna respuesta de este módulo puede incluir stock_sistema ni
costo_unitario: el conteo es a ciegas y el dato no debe existir en el
dispositivo, ni siquiera oculto en la pantalla.
"""

import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.repos import articulos, asignaciones, conteos, operarios, sesiones

router = APIRouter(prefix="/api/dispositivo")


async def _cuerpo_json(request):
    """El cuerpo del pedido, o 422 si llegó cortado.

    Es 422 y no 400 a propósito. El 400 de estos endpoints significa «leí lo
    que mandaste y lo rechazo por lo que es», y el celular lo usa para cerrar
    un alta y sus conteos para siempre. Un cuerpo truncado —la conexión se
    cortó a mitad de envío, que en una WiFi de depósito pasa— es lo contrario:
    nadie llegó a leer nada y reintentarlo funciona. Con el mismo código, un
    corte de red le destruiría al operario conteos que se habrían subido
    solos.
    """
    try:
        return await request.json()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        # Son dos fallas distintas y hay que atrapar las dos. Si el corte cae
        # justo adentro de un carácter acentuado —«Cañ» partido al medio, o
        # sea media eñe— los bytes ni siquiera forman texto y falla la
        # decodificación, antes de que nadie mire si es JSON. Si cae en
        # cualquier otro lado, el texto se arma pero queda incompleto y falla
        # el parseo. En castellano la primera no es un borde raro.
        #
        # Para el operario las dos significan lo mismo: el pedido llegó
        # cortado y hay que mandarlo de nuevo.
        raise HTTPException(
            status_code=422, detail="El pedido llegó incompleto."
        ) from error


def _contexto(request, token):
    con = request.app.state.con
    operario = operarios.por_token(con, token or "")
    if operario is None:
        raise HTTPException(status_code=401, detail="Token de operario inválido")

    sesion = sesiones.sesion_abierta(con)
    if sesion is None:
        raise HTTPException(status_code=409, detail="No hay ninguna sesión abierta")

    return con, operario, sesion


@router.post("/vincular")
def vincular(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    try:
        pasada = sesiones.pasada_activa_de_operario(con, sesion["id"], operario["id"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {
        "operario": {"id": operario["id"], "nombre": operario["nombre"]},
        "sesion": {"id": sesion["id"], "nombre": sesion["nombre"]},
        "pasada": pasada,
    }


@router.get("/maestro")
def descargar_maestro(request: Request, x_token: str = Header(default="")):
    con, _, sesion = _contexto(request, x_token)

    filas_articulos = con.execute(
        """
        SELECT a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion,
               a.grupo, a.ubicacion, a.unidad
        FROM articulo a
        WHERE a.sesion_id = ? AND a.fusionado_en IS NULL
        ORDER BY a.id_orden
        """,
        (sesion["id"],),
    ).fetchall()

    codigos = con.execute(
        """
        SELECT cb.codigo, cb.articulo_id
        FROM codigo_barras cb
        JOIN articulo a ON a.id = cb.articulo_id
        WHERE a.sesion_id = ?
        """,
        (sesion["id"],),
    ).fetchall()

    unidades = con.execute("SELECT * FROM unidad").fetchall()

    return {
        "sesion_id": sesion["id"],
        "articulos": [dict(fila) for fila in filas_articulos],
        "codigos": [dict(fila) for fila in codigos],
        "unidades": [dict(fila) for fila in unidades],
    }


@router.post("/articulos")
async def dar_de_alta(request: Request, x_token: str = Header(default="")):
    """Alta rápida de un código que no está en el maestro.

    Necesita red, a diferencia del conteo: el identificador lo asigna el
    servidor. La app avisa cuando no hay señal en vez de guardar un alta a
    ciegas que después podría chocar con otra igual.
    """
    con, operario, sesion = _contexto(request, x_token)

    cuerpo = await _cuerpo_json(request)

    try:
        return articulos.crear_alta_rapida(
            con, sesion["id"], operario["id"], cuerpo
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/conteos")
async def recibir_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    # Sin esto, un cuerpo cortado sube como error no controlado: el celular
    # ve un 500, que por suerte también reintenta, pero el servidor escupe un
    # traceback por cada corte de WiFi y el motivo real queda enterrado.
    cuerpo = await _cuerpo_json(request)

    return conteos.registrar_lote(
        con, sesion["id"], operario["id"], cuerpo.get("conteos", [])
    )


@router.get("/mis-conteos")
def mis_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    return conteos.de_operario(con, sesion["id"], operario["id"])


@router.get("/mis-ubicaciones")
def mis_ubicaciones(request: Request, x_token: str = Header(default="")):
    """Qué ubicaciones le tocan al operario en el conteo abierto.

    Es lo único que el celular no puede saber solo: el maestro con la
    ubicación de cada artículo y sus propios conteos ya los tiene guardados.

    Sin nada asignado la respuesta es una lista vacía, que es un dato. Sin
    conteo abierto, en cambio, es un 409: una lista vacía ahí sería mentira
    y el celular la escribiría encima del reparto que ya bajó.
    """
    con, operario, sesion = _contexto(request, x_token)
    try:
        return asignaciones.de_operario_en_sesion(con, sesion["id"], operario["id"])
    except ValueError as error:
        raise HTTPException(
            status_code=409, detail="El conteo no está abierto en este momento."
        ) from error
