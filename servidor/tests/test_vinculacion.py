import ipaddress
import json

import pytest

from app import red
from app.servicios import vinculacion


def test_ip_local_es_ipv4_y_no_loopback():
    """Si devolviera 127.0.0.1, el QR mandaría al celular a sí mismo."""
    direccion = ipaddress.ip_address(red.ip_local())

    assert direccion.version == 4
    assert not direccion.is_loopback


def test_armar_url():
    assert vinculacion.armar_url("172.16.11.12", 8000) == "http://172.16.11.12:8000"


def test_el_contenido_lleva_direccion_y_token():
    texto = vinculacion.contenido("http://172.16.11.12:8000", "abc123")

    datos = json.loads(texto)
    assert datos == {"u": "http://172.16.11.12:8000", "t": "abc123"}


def test_el_contenido_es_compacto():
    """Cada carácter agranda el QR, y uno más denso se lee peor con poca luz."""
    texto = vinculacion.contenido("http://172.16.11.12:8000", "abc123")

    assert ", " not in texto
    assert '": ' not in texto


def test_el_svg_es_texto_y_no_bytes():
    """segno escribe bytes; devolver bytes rompería la respuesta HTTP."""
    salida = vinculacion.svg("hola")

    assert isinstance(salida, str)
    assert "<svg" in salida


def test_el_svg_no_referencia_nada_externo():
    """Durante el conteo puede no haber internet."""
    salida = vinculacion.svg("hola")

    assert "http://www.w3.org/2000/svg" in salida  # el namespace no es una descarga
    assert "<image" not in salida
    assert "xlink:href" not in salida


def test_un_token_largo_sigue_entrando_en_el_qr():
    """Los tokens reales son de 43 caracteres, no los de tres letras del test."""
    token = "dsvDgRqPY-gh9gMh90kuyjGinb1GAxqddsoDG4y4AXk"

    salida = vinculacion.svg(
        vinculacion.contenido("http://172.16.11.12:8000", token)
    )

    assert "<svg" in salida


@pytest.mark.parametrize("valor", ["", None])
def test_rechaza_un_token_vacio(valor):
    """Un QR sin token se lee bien y vincula a nadie: falla silencioso."""
    with pytest.raises(ValueError, match="token"):
        vinculacion.contenido("http://172.16.11.12:8000", valor)
