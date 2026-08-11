"""Arranque del servidor con la dirección visible para los celulares."""

import uvicorn

from app.red import ip_local

PUERTO = 8000

# 127.0.0.1 y no «localhost»: en Windows, localhost resuelve primero a ::1 y
# el servidor escucha en IPv4. La dirección numérica abre siempre, y esta
# línea es lo único que tiene quien levanta el servidor para llegar al panel.
LOCAL = "127.0.0.1"


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
