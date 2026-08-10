"""Conversión entre texto y enteros escalados.

Las cantidades viajan y se guardan en milésimas, y los importes en
centavos. Sumar float acumula error, y un inventario suma miles de veces.
"""

import re
from decimal import Decimal, InvalidOperation

MILESIMAS = 1000
CENTAVOS = 100

# Parte entera válida: o bien dígitos corridos, o bien grupos de miles de
# tres dígitos. Sirve para descartar entradas como "1,2,3", que si no se
# validan se interpretan como 12,3 sin que nadie lo note.
SIN_MILES = re.compile(r"^-?\d+$")


def _entero_valido(entero, separador_miles):
    if SIN_MILES.match(entero):
        return True
    patron = re.compile(r"^-?\d{1,3}(" + re.escape(separador_miles) + r"\d{3})+$")
    return bool(patron.match(entero))


def _normalizar(texto):
    """Deja un número con punto decimal, resolviendo el formato del origen.

    Los ERP exportan indistintamente 1.234,56 y 1,234.56. El separador
    decimal es el último que aparece; el otro es de miles.
    """
    if not isinstance(texto, str):
        raise ValueError(f"Se esperaba texto y llegó {type(texto).__name__}")

    limpio = texto.strip().replace(" ", "")
    if not limpio:
        raise ValueError("Cantidad vacía")

    ultima_coma = limpio.rfind(",")
    ultimo_punto = limpio.rfind(".")

    if ultima_coma == -1 and ultimo_punto == -1:
        return limpio

    if ultima_coma > ultimo_punto:
        entero, _, decimal = limpio.rpartition(",")
        separador_miles = "."
    else:
        entero, _, decimal = limpio.rpartition(".")
        separador_miles = ","

    if entero and not _entero_valido(entero, separador_miles):
        raise ValueError(f"Cantidad inválida: {texto!r}")

    entero = entero.replace(separador_miles, "")
    return f"{entero or '0'}.{decimal}"


def _a_escalado(texto, escala):
    normalizado = _normalizar(texto)
    try:
        valor = Decimal(normalizado)
    except InvalidOperation as error:
        raise ValueError(f"Cantidad inválida: {texto!r}") from error
    return int(valor * escala)


def a_milesimas(texto):
    """Convierte texto a milésimas. '3,5' -> 3500."""
    return _a_escalado(texto, MILESIMAS)


def a_centavos(texto):
    """Convierte texto a centavos. '1.234,56' -> 123456."""
    return _a_escalado(texto, CENTAVOS)


def a_texto(milesimas):
    """Convierte milésimas a texto con coma decimal. 3500 -> '3,5'."""
    signo = "-" if milesimas < 0 else ""
    absoluto = abs(milesimas)
    entero, resto = divmod(absoluto, MILESIMAS)

    if resto == 0:
        return f"{signo}{entero}"

    decimales = f"{resto:03d}".rstrip("0")
    return f"{signo}{entero},{decimales}"
