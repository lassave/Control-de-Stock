"""Hash de contraseña y verificación TOTP, sin tocar la base ni el request.

Funciones puras a propósito: son las dos piezas de este sistema donde un
error sale más caro que en cualquier otro lado del proyecto, y probarlas
solas —sin la base, sin el servidor— es lo que las hace fáciles de
revisar.
"""

import hashlib
import secrets

import pyotp

ALGORITMO = "pbkdf2_sha256"
ITERACIONES = 260_000
EMISOR = "Control de Stock"


def hashear_clave(clave: str) -> str:
    """Un string autodescriptivo: algoritmo, iteraciones, sal y hash, juntos.

    Autodescriptivo para que el día que las iteraciones suban, los hashes
    viejos se sigan verificando igual: la función lee sus propios
    parámetros del string en vez de asumirlos fijos.
    """
    sal = secrets.token_hex(16)
    derivada = hashlib.pbkdf2_hmac(
        "sha256", clave.encode("utf-8"), sal.encode("utf-8"), ITERACIONES
    )
    return f"{ALGORITMO}${ITERACIONES}${sal}${derivada.hex()}"


def verificar_clave(clave: str, clave_hash: str) -> bool:
    """False ante cualquier hash con forma rara, en vez de tirar una excepción."""
    partes = clave_hash.split("$")
    if len(partes) != 4:
        return False
    algoritmo, iteraciones, sal, derivada_hex = partes
    if algoritmo != ALGORITMO:
        return False
    try:
        iteraciones = int(iteraciones)
        calculada = hashlib.pbkdf2_hmac(
            "sha256", clave.encode("utf-8"), sal.encode("utf-8"), iteraciones
        )
        return secrets.compare_digest(calculada.hex(), derivada_hex)
    except (ValueError, TypeError):
        return False


def generar_secreto_totp() -> str:
    return pyotp.random_base32()


def verificar_totp(secreto: str, codigo: str) -> bool:
    """Admite un paso de 30 segundos de diferencia de reloj para cada lado."""
    return pyotp.TOTP(secreto).verify(codigo, valid_window=1)


def otpauth_url(secreto: str, usuario: str) -> str:
    """La URL que codifica el QR de alta, para cualquier app autenticadora."""
    return pyotp.totp.TOTP(secreto).provisioning_uri(name=usuario, issuer_name=EMISOR)
