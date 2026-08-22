import pytest
from fastapi.testclient import TestClient

import pyotp

from app.main import crear_app


@pytest.fixture
def cliente_sin_loguear(tmp_path):
    """A diferencia del `cliente` de los demás archivos, este no se loguea:
    es el que hace falta para probar el login en sí y los 401."""
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


def test_estado_sin_cuentas(cliente_sin_loguear):
    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": False, "usuario": None, "hay_cuentas": False}


def _crear_primera_cuenta(cliente, usuario="pablo", clave="clave-larga-123"):
    respuesta = cliente.post(
        "/api/auth/cuentas", json={"usuario": usuario, "clave": clave}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def test_se_puede_crear_la_primera_cuenta_sin_sesion(cliente_sin_loguear):
    cuerpo = _crear_primera_cuenta(cliente_sin_loguear)

    assert cuerpo["usuario"] == "pablo"
    assert cuerpo["otpauth_url"].startswith("otpauth://")
    assert "<svg" in cuerpo["qr_svg"]


def test_una_segunda_cuenta_sin_sesion_se_rechaza(cliente_sin_loguear):
    _crear_primera_cuenta(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "otra", "clave": "clave-larga-456"}
    )

    assert respuesta.status_code == 401


def test_login_con_los_tres_datos_correctos(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    assert respuesta.status_code == 200
    assert "sesion_panel" in respuesta.cookies


def test_login_con_clave_incorrecta(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "otra-clave", "codigo_otp": codigo},
    )

    assert respuesta.status_code == 401


def test_login_con_codigo_otp_incorrecto(cliente_sin_loguear):
    _crear_primera_cuenta(cliente_sin_loguear)

    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": "000000"},
    )

    assert respuesta.status_code == 401


def test_login_con_usuario_inexistente(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "nadie", "clave": "loquesea", "codigo_otp": "000000"},
    )

    assert respuesta.status_code == 401


def test_estado_despues_de_loguearse(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()

    assert cuerpo == {"logueado": True, "usuario": "pablo", "hay_cuentas": True}


def test_logout_invalida_la_sesion(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    cliente_sin_loguear.post("/api/auth/logout")

    cuerpo = cliente_sin_loguear.get("/api/auth/estado").json()
    assert cuerpo["logueado"] is False


def test_una_cuenta_ya_logueada_puede_crear_otra(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    respuesta = cliente_sin_loguear.post(
        "/api/auth/cuentas", json={"usuario": "ana", "clave": "clave-larga-789"}
    )

    assert respuesta.status_code == 200


def test_endpoint_del_panel_sin_sesion_da_401(cliente_sin_loguear):
    assert cliente_sin_loguear.get("/api/sesiones").status_code == 401


def test_endpoint_del_panel_con_sesion_funciona(cliente_sin_loguear):
    cuenta = _crear_primera_cuenta(cliente_sin_loguear)
    codigo = pyotp.TOTP(pyotp.parse_uri(cuenta["otpauth_url"]).secret).now()
    cliente_sin_loguear.post(
        "/api/auth/login",
        json={"usuario": "pablo", "clave": "clave-larga-123", "codigo_otp": codigo},
    )

    assert cliente_sin_loguear.get("/api/sesiones").status_code == 200


def test_dispositivos_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    """La vinculación de celulares no tiene nada que ver con esto."""
    respuesta = cliente_sin_loguear.post(
        "/api/dispositivo/vincular", headers={"X-Token": "token-inventado"}
    )

    assert respuesta.status_code != 401


def test_app_apk_sigue_sin_pedir_sesion_de_panel(cliente_sin_loguear):
    respuesta = cliente_sin_loguear.get("/app.apk")

    assert respuesta.status_code != 401
