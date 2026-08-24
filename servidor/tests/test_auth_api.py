import pyotp
import pytest
from fastapi.testclient import TestClient

from app.main import crear_app
from app.repos import cuentas_panel


@pytest.fixture
def cliente_sin_loguear(tmp_path):
    """A diferencia del `cliente` de los demás archivos, este no se loguea:
    es el que hace falta para probar el login en sí y los 401/403."""
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


def _crear_superusuario_y_loguearse(cliente, usuario="Administrator", clave="clave-larga-123"):
    con = cliente.app.state.con
    creada = cuentas_panel.crear(con, usuario, clave, rol="superusuario")
    cliente.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
    return creada


def test_login_sin_otp_funciona(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "clave-larga-123"}
    )

    assert respuesta.status_code == 200
    assert "sesion_panel" in respuesta.cookies


def test_login_con_recordarme_pone_una_cookie_de_diez_anios(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "recordarme": True},
    )

    cookie = next(c for c in respuesta.cookies.jar if c.name == "sesion_panel")
    assert cookie.expires - cookie.expires % 100 > 315_000_000


def test_login_con_clave_incorrecta(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "otra-clave"}
    )

    assert respuesta.status_code == 401


def test_login_con_usuario_inexistente(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "nadie", "clave": "loquesea"}
    )

    assert respuesta.status_code == 401


def test_estado_sin_login_no_trae_rol(cliente_sin_loguear):
    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": False, "usuario": None, "rol": None}


def test_estado_despues_de_loguearse(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": True, "usuario": "Administrator", "rol": "superusuario"}


def test_logout_invalida_la_sesion(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cliente_sin_loguear.post("/api/auth/logout")

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()
    assert cuerpo["logueado"] is False


def test_crear_cuenta_sin_sesion_da_401(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 401


def test_requerir_superusuario_rechaza_una_cuenta_menor(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "pablo", "clave": "clave-larga-123"}
    )

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "otra@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 403


def test_superusuario_puede_crear_una_cuenta_menor(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana@x.com", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo == {"id": cuerpo["id"], "usuario": "ana@x.com"}


def test_crear_cuenta_ignora_el_rol_del_pedido(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    cliente_sin_loguear.post(
        "/api/auth/cuentas",
        json={"usuario": "ana@x.com", "clave": "clave-larga-456", "rol": "superusuario"},
    )

    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.por_usuario(con, "ana@x.com")
    assert creada["rol"] == "menor"


def test_solicitar_recuperacion_siempre_da_el_mismo_mensaje(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/solicitar", json={"usuario": "nadie@x.com"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["mensaje"]


def test_solicitar_recuperacion_de_una_cuenta_menor_manda_un_mail(
    cliente_sin_loguear, monkeypatch
):
    from app.servicios import correo

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")

    mandados = []
    monkeypatch.setattr(
        correo, "mandar_codigo_recuperacion",
        lambda destinatario, codigo: mandados.append((destinatario, codigo)),
    )

    cliente_sin_loguear.post("/api/auth/recuperar/solicitar", json={"usuario": "ana@x.com"})

    assert len(mandados) == 1
    assert mandados[0][0] == "ana@x.com"


def test_solicitar_recuperacion_del_superusuario_no_manda_mail(
    cliente_sin_loguear, monkeypatch
):
    from app.servicios import correo

    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    mandados = []
    monkeypatch.setattr(
        correo, "mandar_codigo_recuperacion",
        lambda destinatario, codigo: mandados.append((destinatario, codigo)),
    )

    cliente_sin_loguear.post(
        "/api/auth/recuperar/solicitar", json={"usuario": "Administrator"}
    )

    assert mandados == []


def test_confirmar_recuperacion_del_superusuario_con_totp(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")
    codigo = pyotp.TOTP(creada["otp_secreto"]).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "Administrator", "codigo": codigo, "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 200
    login = cliente_sin_loguear.post(
        "/api/auth/login", json={"usuario": "Administrator", "clave": "clave-nueva-456"}
    )
    assert login.status_code == 200


def test_confirmar_recuperacion_de_una_cuenta_menor_con_el_codigo(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": codigo, "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 200


def test_confirmar_recuperacion_con_codigo_incorrecto_da_401(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": "000000", "clave_nueva": "clave-nueva-456"},
    )

    assert respuesta.status_code == 401


def test_confirmar_recuperacion_con_clave_nueva_debil_da_400(cliente_sin_loguear):
    con = cliente_sin_loguear.app.state.con
    creada = cuentas_panel.crear(con, "ana@x.com", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    respuesta = cliente_sin_loguear.post(
        "/api/auth/recuperar/confirmar",
        json={"usuario": "ana@x.com", "codigo": codigo, "clave_nueva": "corta"},
    )

    assert respuesta.status_code == 400


def test_endpoint_del_panel_sin_sesion_da_401(cliente_sin_loguear):
    assert cliente_sin_loguear.get("/api/sesiones").status_code == 401


def test_endpoint_del_panel_con_sesion_funciona(cliente_sin_loguear):
    _crear_superusuario_y_loguearse(cliente_sin_loguear)

    assert cliente_sin_loguear.get("/api/sesiones").status_code == 200


def test_dispositivos_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    """La vinculación de celulares no tiene nada que ver con esto.

    Un token inventado ya da 401 por su cuenta —`_contexto` en
    `dispositivos.py` rechaza cualquier token de operario que no exista,
    sesión de panel aparte—, así que probarlo con eso no demostraría
    nada. Acá se crea un operario y una sesión de inventario de verdad
    estando logueado, se cierra la sesión de panel, y se comprueba que
    `/api/dispositivo/vincular` igual funciona con el token real.
    """
    _crear_superusuario_y_loguearse(cliente_sin_loguear)
    cliente_sin_loguear.post("/api/sesiones", json={"nombre": "Cliente X"})
    operario = cliente_sin_loguear.post(
        "/api/operarios", json={"nombre": "Juan"}
    ).json()

    cliente_sin_loguear.post("/api/auth/logout")

    respuesta = cliente_sin_loguear.post(
        "/api/dispositivo/vincular",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 200


def test_app_apk_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.get("/app.apk")

    assert respuesta.status_code != 401
