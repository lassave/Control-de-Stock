"""Arranque del servidor con la dirección visible para los celulares."""

import socket

import uvicorn

PUERTO = 8000

# 127.0.0.1 y no «localhost»: en Windows, localhost resuelve primero a ::1 y
# el servidor escucha en IPv4. La dirección numérica abre siempre, y esta
# línea es lo único que tiene quien levanta el servidor para llegar al panel.
LOCAL = "127.0.0.1"


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


def mostrar_encabezado():
    """Lo único que ve quien levanta el servidor: tiene que alcanzar solo."""
    ip = ip_local()
    print("=" * 56)
    print("  CONTROL DE STOCK")
    print("=" * 56)
    print(f"  Panel:      http://{LOCAL}:{PUERTO}")
    print(f"  Celulares:  http://{ip}:{PUERTO}")
    print()
    print("  Dejá esta ventana abierta mientras dure el conteo.")
    print("  Para terminar, cerrala o apretá Ctrl+C.")
    print("=" * 56, flush=True)
    # El flush no es adorno: si alguien arranca el servidor con la salida
    # redirigida a un archivo de registro, Python se guarda todo en el buffer
    # y uvicorn no termina nunca, así que la dirección no aparece jamás.


def main():
    mostrar_encabezado()
    uvicorn.run("app.main:app", host="0.0.0.0", port=PUERTO, log_level="warning")


if __name__ == "__main__":
    main()
