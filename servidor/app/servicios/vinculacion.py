"""El QR con el que un celular se vincula al servidor.

Lleva adentro la dirección del servidor y el token del operario, así el
operario no tipea nada: ni la IP, que cambia en cada lugar, ni el token,
que son 43 caracteres al azar.
"""

import io
import json

import segno

# Corrección de errores media: tolera un QR manchado o mal impreso sin
# agrandarlo tanto como para que cueste enfocarlo de cerca.
CORRECCION = "m"


def armar_url(ip, puerto):
    return f"http://{ip}:{puerto}"


def contenido(url, token):
    """El texto que va adentro del QR.

    Compacto a propósito: cada carácter agrega módulos al QR, y uno más
    denso se lee peor justo donde se usa, con poca luz y a pulso.
    """
    if not token:
        raise ValueError("El QR necesita el token del operario")
    return json.dumps({"u": url, "t": token}, separators=(",", ":"))


def svg(texto):
    """Devuelve el QR como SVG.

    `segno` escribe bytes aunque el formato sea texto, así que hay que
    decodificar: devolver bytes haría que la respuesta HTTP saliera como
    una descarga en vez de dibujarse.
    """
    qr = segno.make(texto, error=CORRECCION)
    salida = io.BytesIO()
    qr.save(salida, kind="svg", scale=4, border=2,
            dark="#1c2126", light="#ffffff")
    return salida.getvalue().decode("utf-8")
