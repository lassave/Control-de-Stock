"""Login del panel: cuentas, sesión, y el segundo factor por TOTP.

Sin autenticación —es el único lugar donde no puede haberla, por
definición—. `panel.router` importa `verificar_sesion` de acá para
protegerse a sí mismo.
"""

from fastapi import APIRouter, HTTPException, Request, Response

from app.repos import cuentas_panel
from app.servicios import autenticacion, vinculacion

router = APIRouter(prefix="/api/auth")

COOKIE_SESION = "sesion_panel"
SEGUNDOS_DE_SESION = 60 * 60 * 24 * 30


def _con(request):
    return request.app.state.con


def verificar_sesion(request: Request) -> dict:
    """La dependencia que protege `panel.router`: quién está logueado, o 401."""
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        raise HTTPException(status_code=401, detail="No hay sesión iniciada")

    cuenta = cuentas_panel.sesion_valida(_con(request), token)
    if cuenta is None:
        raise HTTPException(status_code=401, detail="La sesión no es válida o venció")

    return cuenta


@router.get("/estado")
def estado(request: Request):
    con = _con(request)
    token = request.cookies.get(COOKIE_SESION)
    cuenta = cuentas_panel.sesion_valida(con, token) if token else None

    return {
        "logueado": cuenta is not None,
        "usuario": cuenta["usuario"] if cuenta else None,
        "hay_cuentas": cuentas_panel.existe_alguna(con),
    }


@router.post("/login")
async def login(request: Request, response: Response):
    cuerpo = await request.json()
    con = _con(request)

    usuario = (cuerpo.get("usuario") or "").strip()
    clave = cuerpo.get("clave") or ""
    codigo_otp = cuerpo.get("codigo_otp") or ""

    # Un solo mensaje para las tres formas de fallar: no le confirma a
    # quien prueba a ciegas cuál de los tres datos acertó.
    credenciales_invalidas = HTTPException(
        status_code=401, detail="Usuario, contraseña o código incorrecto"
    )

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is None:
        raise credenciales_invalidas
    if not autenticacion.verificar_clave(clave, cuenta["clave_hash"]):
        raise credenciales_invalidas
    if not autenticacion.verificar_totp(cuenta["otp_secreto"], codigo_otp):
        raise credenciales_invalidas

    token = cuentas_panel.crear_sesion(con, cuenta["id"])
    response.set_cookie(
        COOKIE_SESION, token,
        httponly=True, samesite="lax", max_age=SEGUNDOS_DE_SESION,
    )
    return {"usuario": cuenta["usuario"]}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_SESION)
    if token:
        cuentas_panel.borrar_sesion(_con(request), token)
    response.delete_cookie(COOKIE_SESION)
    return {"ok": True}


@router.post("/cuentas")
async def crear_cuenta(request: Request):
    """Sin cuentas todavía, se permite sin sesión: es el arranque. Con al
    menos una ya creada, exige sesión válida como cualquier otro endpoint
    del panel — acá adentro, con un `if`, porque expresarlo como una
    dependencia de FastAPI sería más confuso que la condición misma."""
    con = _con(request)
    if cuentas_panel.existe_alguna(con):
        verificar_sesion(request)

    cuerpo = await request.json()
    try:
        creada = cuentas_panel.crear(con, cuerpo.get("usuario"), cuerpo.get("clave"))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    otpauth = autenticacion.otpauth_url(creada["otp_secreto"], creada["usuario"])
    return {
        "id": creada["id"],
        "usuario": creada["usuario"],
        "otpauth_url": otpauth,
        "qr_svg": vinculacion.svg(otpauth),
    }
