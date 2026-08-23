"""Envío del código de recuperación por mail.

Solo hace falta para recuperar la contraseña de una cuenta de rol
menor —el uso normal del panel nunca depende de esto—, así que su
ausencia o mala configuración no impide que el servidor arranque: este
módulo no se toca hasta que alguien pide recuperar una contraseña.
"""

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

RUTA_CONFIG = Path(
    os.environ.get(
        "CONTROL_DE_STOCK_MAIL", "C:/clientes/claves/control-de-stock-mail.properties"
    )
)

CAMPOS_REQUERIDOS = ["usuario", "clave"]


class ErrorDeCorreo(Exception):
    pass


def _leer_config():
    if not RUTA_CONFIG.exists():
        raise ErrorDeCorreo(
            f"Falta el archivo de configuración de mail: {RUTA_CONFIG}. "
            "Copiá servidor/correo-de-ejemplo.properties a esa ruta y completá "
            "usuario y clave, o poné otra ruta en la variable de entorno "
            "CONTROL_DE_STOCK_MAIL."
        )

    config = {}
    for linea in RUTA_CONFIG.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        config[clave.strip()] = valor.strip()

    faltantes = [campo for campo in CAMPOS_REQUERIDOS if not config.get(campo)]
    if faltantes:
        raise ErrorDeCorreo(
            f"Al archivo de configuración de mail ({RUTA_CONFIG}) le falta "
            f"completar: {', '.join(faltantes)}"
        )
    return config


def mandar_codigo_recuperacion(destinatario, codigo):
    config = _leer_config()

    mensaje = EmailMessage()
    mensaje["Subject"] = "Código para recuperar tu contraseña — Control de Stock"
    mensaje["From"] = config["usuario"]
    mensaje["To"] = destinatario
    mensaje.set_content(
        f"Tu código para recuperar la contraseña es: {codigo}\n\n"
        "Vence en 15 minutos. Si no lo pediste vos, ignorá este mail."
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(config["usuario"], config["clave"])
            servidor.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as error:
        raise ErrorDeCorreo(f"No se pudo mandar el mail: {error}") from error
