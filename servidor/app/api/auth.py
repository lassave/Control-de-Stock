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
    """El rol nunca sale del cliente: esta ruta solo crea cuentas de rol
    menor. Hay exactamente un superusuario, y se crea a mano contra la
    base, nunca por acá."""
    con = _con(request)
    cuerpo = await request.json()
    try:
        creada = cuentas_panel.crear(con, cuerpo.get("usuario"), cuerpo.get("clave"), rol="menor")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"id": creada["id"], "usuario": creada["usuario"]}


MENSAJE_RECUPERAR_SOLICITADO = "Si la cuenta existe, ya podés poner el código."


@router.post("/recuperar/solicitar")
async def recuperar_solicitar(request: Request):
    """Mismo mensaje siempre, exista o no la cuenta, sea cual sea su rol:
    no hay que confirmarle a quien prueba a ciegas ninguno de los dos datos.

    Al superusuario no le manda nada —su código ya vive en la app
    autenticadora, no hay nada que generar—. A una cuenta de rol menor le
    genera un código y se lo manda por mail; si el envío falla, se avisa
    por consola en vez de romper la respuesta genérica —una respuesta
    distinta ahí confirmaría que la cuenta existe y es de rol menor—.
    """
    cuerpo = await request.json()
    con = _con(request)
    usuario = (cuerpo.get("usuario") or "").strip()

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is not None and cuenta["rol"] == "menor":
        codigo = cuentas_panel.generar_codigo_recuperacion(con, cuenta["id"])
        try:
            correo.mandar_codigo_recuperacion(cuenta["usuario"], codigo)
        except correo.ErrorDeCorreo as error:
            print(f"No se pudo mandar el mail de recuperación a {cuenta['usuario']}: {error}")

    return {"mensaje": MENSAJE_RECUPERAR_SOLICITADO}


@router.post("/recuperar/confirmar")
async def recuperar_confirmar(request: Request):
    cuerpo = await request.json()
    con = _con(request)

    usuario = (cuerpo.get("usuario") or "").strip()
    codigo = cuerpo.get("codigo") or ""
    clave_nueva = cuerpo.get("clave_nueva") or ""

    codigo_invalido = HTTPException(status_code=401, detail="Código o datos incorrectos")

    cuenta = cuentas_panel.por_usuario(con, usuario)
    if cuenta is None:
        raise codigo_invalido

    if cuenta["rol"] == "superusuario":
        valido = autenticacion.verificar_totp(cuenta["otp_secreto"], codigo)
    else:
        valido = cuentas_panel.verificar_codigo_recuperacion(con, cuenta["id"], codigo)

    if not valido:
        raise codigo_invalido

    try:
        cuentas_panel.cambiar_clave(con, cuenta["id"], clave_nueva)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"ok": True}
