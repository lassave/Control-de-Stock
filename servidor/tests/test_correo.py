import smtplib

import pytest

from app.servicios import correo


class SMTPFalso:
    """Reemplaza smtplib.SMTP_SSL en los tests: nunca abre una conexión real."""

    instancias = []

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.logueado_con = None
        self.mensajes_mandados = []
        SMTPFalso.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def login(self, usuario, clave):
        self.logueado_con = (usuario, clave)

    def send_message(self, mensaje):
        self.mensajes_mandados.append(mensaje)


class SMTPQueFalla(SMTPFalso):
    def send_message(self, mensaje):
        raise smtplib.SMTPException("el servidor de Gmail rechazó el mensaje")


@pytest.fixture
def config_de_correo(tmp_path, monkeypatch):
    archivo = tmp_path / "correo.properties"
    archivo.write_text("usuario=deposito@gmail.com\nclave=una-clave-de-aplicacion\n")
    monkeypatch.setattr(correo, "RUTA_CONFIG", archivo)
    return archivo


def test_sin_archivo_de_configuracion_avisa(tmp_path, monkeypatch):
    monkeypatch.setattr(correo, "RUTA_CONFIG", tmp_path / "no-existe.properties")

    with pytest.raises(correo.ErrorDeCorreo, match="configuración"):
        correo.mandar_codigo_recuperacion("alguien@x.com", "123456")


def test_con_campos_incompletos_avisa(tmp_path, monkeypatch):
    archivo = tmp_path / "correo.properties"
    archivo.write_text("usuario=deposito@gmail.com\n")
    monkeypatch.setattr(correo, "RUTA_CONFIG", archivo)

    with pytest.raises(correo.ErrorDeCorreo, match="clave"):
        correo.mandar_codigo_recuperacion("alguien@x.com", "123456")


def test_manda_el_codigo_por_smtp(config_de_correo, monkeypatch):
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", SMTPFalso)
    SMTPFalso.instancias.clear()

    correo.mandar_codigo_recuperacion("alguien@x.com", "123456")

    servidor = SMTPFalso.instancias[0]
    assert servidor.logueado_con == ("deposito@gmail.com", "una-clave-de-aplicacion")
    mensaje = servidor.mensajes_mandados[0]
    assert mensaje["To"] == "alguien@x.com"
    assert "123456" in mensaje.get_content()


def test_una_falla_de_smtp_se_traduce_a_errordecorreo(config_de_correo, monkeypatch):
    monkeypatch.setattr(correo.smtplib, "SMTP_SSL", SMTPQueFalla)

    with pytest.raises(correo.ErrorDeCorreo):
        correo.mandar_codigo_recuperacion("alguien@x.com", "123456")
