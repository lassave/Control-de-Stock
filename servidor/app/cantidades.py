"""Conversión entre texto y enteros escalados.

Las cantidades viajan y se guardan en milésimas, y los importes en
centavos. Sumar float acumula error, y un inventario suma miles de veces.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MILESIMAS = 1000
CENTAVOS = 100

SOLO_DIGITOS = re.compile(r"^-?\d+$")


def _agrupacion_valida(entero, separador_miles):
    """Verifica que los grupos de miles tengan tres dígitos.

    Sin esto «1,2,3» se leería como 123 en vez de rechazarse, y un número
    inventado es peor que un error: pasa por una cantidad real.
    """
    if separador_miles not in entero:
        return bool(SOLO_DIGITOS.match(entero))
    patron = r"^-?\d{1,3}(" + re.escape(separador_miles) + r"\d{3})+$"
    return bool(re.match(patron, entero))


def _partir(limpio, texto):
    """Separa parte entera y decimal resolviendo el formato del origen.

    Los ERP exportan indistintamente 1.234,56 y 1,234.56. Cuando conviven
    los dos caracteres, el último es el decimal y el otro agrupa miles.
    Cuando hay uno solo repetido (1.234.567) solo puede agrupar miles.

    Queda una ambigüedad que ningún criterio resuelve: «1.234» puede ser mil
    doscientos treinta y cuatro o uno coma doscientos treinta y cuatro. Se
    interpreta como decimal, que es lo habitual en cantidades. La vista
    previa de la importación existe para detectar el caso contrario.
    """
    coma = limpio.rfind(",")
    punto = limpio.rfind(".")

    if coma == -1 and punto == -1:
        if not SOLO_DIGITOS.match(limpio):
            raise ValueError(f"Cantidad inválida: {texto!r}")
        return limpio, ""

    if coma >= 0 and punto >= 0:
        separador_decimal = "," if coma > punto else "."
    else:
        unico = "," if coma >= 0 else "."
        if limpio.count(unico) > 1:
            if not _agrupacion_valida(limpio, unico):
                raise ValueError(f"Cantidad inválida: {texto!r}")
            return limpio.replace(unico, ""), ""
        separador_decimal = unico

    separador_miles = "." if separador_decimal == "," else ","
    entero, _, decimal = limpio.rpartition(separador_decimal)

    # Un separador suelto («.» o «,») no es cero: es una celda rota. Devolver
    # cero sería lo peor posible, porque un cero pasa por un conteo real.
    if not decimal.isdigit():
        raise ValueError(f"Cantidad inválida: {texto!r}")

    if entero in ("", "-"):
        entero += "0"
    if not _agrupacion_valida(entero, separador_miles):
        raise ValueError(f"Cantidad inválida: {texto!r}")

    return entero.replace(separador_miles, ""), decimal


def _a_escalado(texto, escala):
    if not isinstance(texto, str):
        raise ValueError(f"Se esperaba texto y llegó {type(texto).__name__}")

    limpio = texto.strip()
    if not limpio:
        raise ValueError("Cantidad vacía")

    entero, decimal = _partir(limpio, texto)

    try:
        valor = Decimal(f"{entero}.{decimal or 0}")
        # Redondeo y no truncamiento: el ERP puede exportar más decimales de
        # los que se guardan, y truncar sesgaría todas las cantidades a la baja.
        return int((valor * escala).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ArithmeticError) as error:
        raise ValueError(f"Cantidad inválida: {texto!r}") from error


def a_milesimas(texto: str) -> int:
    """Convierte texto a milésimas. '3,5' -> 3500."""
    return _a_escalado(texto, MILESIMAS)


def a_centavos(texto: str) -> int:
    """Convierte texto a centavos. '1.234,56' -> 123456."""
    return _a_escalado(texto, CENTAVOS)


def a_texto_importe(centavos: int | None) -> str:
    """Convierte centavos a texto con dos decimales. 12345 -> '123,45'.

    Vive acá, junto a `a_centavos`, para que la conversión de importes tenga
    una sola implementación: la exportación y el panel muestran plata los dos.
    A diferencia de `a_texto`, nunca recorta los decimales: un importe de
    '10' a secas se lee como diez pesos y no como diez con cero centavos.
    """
    if centavos is None:
        return ""
    signo = "-" if centavos < 0 else ""
    entero, resto = divmod(abs(centavos), CENTAVOS)
    return f"{signo}{entero},{resto:02d}"


def a_texto(milesimas: int) -> str:
    """Convierte milésimas a texto con coma decimal. 3500 -> '3,5'."""
    signo = "-" if milesimas < 0 else ""
    absoluto = abs(milesimas)
    entero, resto = divmod(absoluto, MILESIMAS)

    if resto == 0:
        return f"{signo}{entero}"

    decimales = f"{resto:03d}".rstrip("0")
    return f"{signo}{entero},{decimales}"
