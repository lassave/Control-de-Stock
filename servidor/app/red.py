"""Dirección de esta máquina en la red local.

Vive en `app` y no en `iniciar` porque la usan los dos: el arranque, para
mostrar la dirección en pantalla, y la API, para armar el QR de vinculación.
Duplicarla haría que un día muestren direcciones distintas.
"""

import socket


def ip_local():
    """La IP de esta máquina en la red local.

    Abrir un socket UDP hacia una dirección externa no envía nada, pero
    obliga al sistema a elegir la interfaz de salida. Es la forma
    confiable de saber con qué IP nos ven los celulares cuando hay varias
    placas de red (WiFi, Ethernet, VPN).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()
