import ipaddress
from pathlib import Path

import iniciar

RAIZ = Path(__file__).resolve().parent.parent.parent
ARRANQUE = RAIZ / "Iniciar servidor.bat"


def test_ip_local_es_una_ip_valida():
    ip = iniciar.ip_local()

    direccion = ipaddress.ip_address(ip)
    assert direccion.version == 4


def test_ip_local_no_es_loopback():
    """Si devolviera 127.0.0.1, los celulares no podrían llegar al servidor."""
    ip = iniciar.ip_local()

    assert not ipaddress.ip_address(ip).is_loopback


def test_el_encabezado_muestra_las_dos_direcciones(capsys):
    """La ventana negra es toda la interfaz que tiene quien levanta el servidor."""
    iniciar.mostrar_encabezado()

    salida = capsys.readouterr().out
    assert f"http://{iniciar.LOCAL}:{iniciar.PUERTO}" in salida
    assert f"http://{iniciar.ip_local()}:{iniciar.PUERTO}" in salida


def test_la_direccion_local_no_depende_de_resolver_un_nombre():
    """«localhost» resuelve primero a ::1 en Windows y el servidor es IPv4.

    Con el nombre, el panel puede no abrir en la misma PC que lo sirve, que
    es donde lo abre quien está corriendo el inventario.
    """
    assert not ipaddress.ip_address(iniciar.LOCAL).version == 6
    assert ipaddress.ip_address(iniciar.LOCAL).is_loopback


def test_el_bat_de_arranque_usa_saltos_de_linea_de_windows():
    """Con saltos LF, cmd se come el primer carácter de cada línea.

    El arranque falla con «"hcp" no se reconoce como un comando» y quien
    recibe el proyecto no tiene forma de saber qué pasó. Es el archivo que
    el cliente ejecuta con doble clic: no puede depender de cómo lo escribió
    el editor de turno.
    """
    crudo = ARRANQUE.read_bytes()

    assert b"\n" in crudo
    assert crudo.replace(b"\r\n", b"") .count(b"\n") == 0


def test_el_bat_de_arranque_no_lleva_bom():
    """cmd interpreta el BOM como parte del primer comando y lo rechaza."""
    assert not ARRANQUE.read_bytes().startswith(b"\xef\xbb\xbf")
