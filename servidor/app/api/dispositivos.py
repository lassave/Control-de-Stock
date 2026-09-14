"""Endpoints que consumen la app y la PWA.

Ninguna respuesta de este módulo puede incluir stock_sistema ni
costo_unitario: el conteo es a ciegas y el dato no debe existir en el
dispositivo, ni siquiera oculto en la pantalla.
"""

import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.repos import articulos, asignaciones, conteos, operarios, proyectos

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

    proyecto = proyectos.proyecto_abierto(con)
    if proyecto is None:
        raise HTTPException(status_code=409, detail="No hay ningún proyecto abierto")

    return con, operario, proyecto


@router.post("/vincular")
def vincular(request: Request, x_token: str = Header(default="")):
    con, operario, proyecto = _contexto(request, x_token)
    try:
        pasada = proyectos.pasada_activa_de_operario(con, proyecto["id"], operario["id"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {
        "operario": {"id": operario["id"], "nombre": operario["nombre"]},
        "proyecto": {"id": proyecto["id"], "nombre": proyecto["nombre"]},
        "pasada": pasada,
    }


@router.get("/operarios")
def listar_operarios(request: Request, x_token: str = Header(default="")):
    con, _, _ = _contexto(request, x_token)
    return {"operarios": operarios.listar_para_identificar(con)}


@router.post("/identificar")
async def identificar(request: Request, x_token: str = Header(default="")):
    """Identificarse en un celular ya vinculado, sin volver a escanear el QR.

    El `X-Token` de acá adentro no es el de la persona que se está por
    identificar: es el de quien ya tenía el celular, y solo prueba que es un
    dispositivo que ya pasó por el QR alguna vez.
    """
    con, _, proyecto = _contexto(request, x_token)
    cuerpo = await _cuerpo_json(request)

    nombre = (cuerpo.get("nombre") or "").strip()
    elegido = operarios.para_identificar(con, nombre)
    if elegido is None:
        raise HTTPException(status_code=400, detail="Ese operario no existe")

    pin_guardado = elegido["pin"]
    if pin_guardado:
        pin_recibido = cuerpo.get("pin")
        if not pin_recibido:
            raise HTTPException(status_code=400, detail="Ese operario necesita un PIN")
        if pin_recibido != pin_guardado:
            raise HTTPException(status_code=400, detail="El PIN no coincide")

    try:
        pasada = proyectos.pasada_activa_de_operario(con, proyecto["id"], elegido["id"])
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {
        "operario": {"id": elegido["id"], "nombre": elegido["nombre"]},
        "proyecto": {"id": proyecto["id"], "nombre": proyecto["nombre"]},
        "pasada": pasada,
        "token": elegido["token_dispositivo"],
    }


@router.get("/maestro")
def descargar_maestro(request: Request, x_token: str = Header(default="")):
    con, _, proyecto = _contexto(request, x_token)

    filas_articulos = con.execute(
        """
        SELECT a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion,
               a.grupo, a.ubicacion, a.unidad
        FROM articulo a
        WHERE a.proyecto_id = ? AND a.fusionado_en IS NULL
        ORDER BY a.id_orden
        """,
        (proyecto["id"],),
    ).fetchall()

    codigos = con.execute(
        """
        SELECT cb.codigo, cb.articulo_id
        FROM codigo_barras cb
        JOIN articulo a ON a.id = cb.articulo_id
        WHERE a.proyecto_id = ?
        """,
        (proyecto["id"],),
    ).fetchall()

    unidades = con.execute("SELECT * FROM unidad").fetchall()

    return {
        "proyecto_id": proyecto["id"],
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
    con, operario, proyecto = _contexto(request, x_token)

    cuerpo = await _cuerpo_json(request)

    try:
        return articulos.crear_alta_rapida(
            con, proyecto["id"], operario["id"], cuerpo
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/conteos")
async def recibir_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, proyecto = _contexto(request, x_token)
    # Sin esto, un cuerpo cortado sube como error no controlado: el celular
    # ve un 500, que por suerte también reintenta, pero el servidor escupe un
    # traceback por cada corte de WiFi y el motivo real queda enterrado.
    cuerpo = await _cuerpo_json(request)

    return conteos.registrar_lote(
        con, proyecto["id"], operario["id"], cuerpo.get("conteos", [])
    )


@router.get("/mis-conteos")
def mis_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, proyecto = _contexto(request, x_token)
    return conteos.de_operario(con, proyecto["id"], operario["id"])


@router.get("/mis-ubicaciones")
def mis_ubicaciones(request: Request, x_token: str = Header(default="")):
    """Qué ubicaciones le tocan al operario en el conteo abierto.

    Es lo único que el celular no puede saber solo: el maestro con la
    ubicación de cada artículo y sus propios conteos ya los tiene guardados.

    Sin nada asignado la respuesta es una lista vacía, que es un dato. Sin
    conteo abierto, en cambio, es un 409: una lista vacía ahí sería mentira
    y el celular la escribiría encima del reparto que ya bajó.
    """
    con, operario, proyecto = _contexto(request, x_token)
    try:
        return asignaciones.de_operario_en_proyecto(con, proyecto["id"], operario["id"])
    except ValueError as error:
        raise HTTPException(
            status_code=409, detail="El conteo no está abierto en este momento."
        ) from error
