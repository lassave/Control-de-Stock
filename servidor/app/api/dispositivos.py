"""Endpoints que consumen la app y la PWA.

Ninguna respuesta de este módulo puede incluir stock_sistema ni
costo_unitario: el conteo es a ciegas y el dato no debe existir en el
dispositivo, ni siquiera oculto en la pantalla.
"""

from fastapi import APIRouter, Header, HTTPException, Request

from app.repos import conteos, operarios, sesiones

router = APIRouter(prefix="/api/dispositivo")


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
    return {
        "operario": {"id": operario["id"], "nombre": operario["nombre"]},
        "sesion": {"id": sesion["id"], "nombre": sesion["nombre"]},
        "pasada": sesiones.pasada_abierta(con, sesion["id"]),
    }


@router.get("/maestro")
def descargar_maestro(request: Request, x_token: str = Header(default="")):
    con, _, sesion = _contexto(request, x_token)

    articulos = con.execute(
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
        "articulos": [dict(fila) for fila in articulos],
        "codigos": [dict(fila) for fila in codigos],
        "unidades": [dict(fila) for fila in unidades],
    }


@router.post("/conteos")
async def recibir_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    cuerpo = await request.json()

    return conteos.registrar_lote(
        con, sesion["id"], operario["id"], cuerpo.get("conteos", [])
    )


@router.get("/mis-conteos")
def mis_conteos(request: Request, x_token: str = Header(default="")):
    con, operario, sesion = _contexto(request, x_token)
    return conteos.de_operario(con, sesion["id"], operario["id"])
