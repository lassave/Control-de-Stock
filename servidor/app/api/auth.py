"""Login del panel: cuentas, sesión, roles, y la recuperación de contraseña.

Sin autenticación en el propio router —es el único lugar donde no puede
haberla, por definición—. `panel.router` importa `verificar_sesion` y
`requerir_superusuario` de acá para protegerse a sí mismo.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.repos import cuentas_panel
from app.servicios import autenticacion, correo

router = APIRouter(prefix="/api/auth")

COOKIE_SESION = "sesion_panel"
SEGUNDOS_DE_SESION = 60 * 60 * 24 * 30
# "Recordarme": no vuelve a pedir login salvo un logout explícito. La
# cookie necesita un vencimiento largo para eso —`sesion_valida()` ya no
# chequea el vencimiento del lado del servidor para estas sesiones, pero
# el navegador igual descarta una cookie sin `max_age`—, así que se usa
# un número grande en vez de "para siempre" (no existe esa opción en HTTP).
SEGUNDOS_RECORDAR = 60 * 60 * 24 * 365 * 10


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


def requerir_superusuario(cuenta: dict = Depends(verificar_sesion)) -> dict:
    """Como `verificar_sesion`, pero además exige el rol superusuario."""
    if cuenta["rol"] != "superusuario":
        raise HTTPException(
            status_code=403, detail="Esta acción es solo para el superusuario"
        )
    return cuenta


@router.get("/estado")
def estado(request: Request):
    con = _con(request)
    token = request.cookies.get(COOKIE_SESION)
    cuenta = cuentas_panel.sesion_valida(con, token) if token else None

    return {
        "logueado": cuenta is not None,
        "usuario": cuenta["usuario"] if cuenta else None,
        "rol": cuenta["rol"] if cuenta else None,
    }


@router.post("/login")
async def login(request: Request, response: Response):
    cuerpo = await request.json()
    con = _con(request)

    usuario = (cuerpo.get("usuario") or "").strip()
    clave = cuerpo.get("clave") or ""
    recordarme = bool(cuerpo.get("recordarme"))

    credenciales_invalidas = HTTPException(
        status_code=401, detail="Usuario o contraseña incorrecto"
    )

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is None:
        raise credenciales_invalidas
    if not autenticacion.verificar_clave(clave, cuenta["clave_hash"]):
        raise credenciales_invalidas

    token = cuentas_panel.crear_sesion(con, cuenta["id"], recordar=recordarme)
    response.set_cookie(
        COOKIE_SESION, token,
        httponly=True, samesite="lax",
        max_age=SEGUNDOS_RECORDAR if recordarme else SEGUNDOS_DE_SESION,
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
async def crear_cuenta(request: Request, _: dict = Depends(requerir_superusuario)):
    raise NotImplementedError("completado en la Task 7 de este plan")


@router.post("/recuperar/solicitar")
async def recuperar_solicitar(request: Request):
    raise NotImplementedError("completado en la Task 8 de este plan")


@router.post("/recuperar/confirmar")
async def recuperar_confirmar(request: Request):
    raise NotImplementedError("completado en la Task 8 de este plan")
