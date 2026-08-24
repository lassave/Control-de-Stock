"""Crea la cuenta superusuario del panel, directo contra la base.

Hay exactamente un superusuario para siempre: ningún endpoint puede
crearlo. Este script es la única forma —al instalar el sistema, o para
recrear la cuenta si se pierde el acceso (el QR de acá abajo es la
única vez que el secreto TOTP existe fuera de la base)—.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import db
from app.repos import cuentas_panel
from app.servicios import autenticacion, vinculacion


def main():
    ruta_db = Path(__file__).resolve().parent / "inventario.db"
    con = db.conectar(str(ruta_db))
    db.crear_esquema(con)

    usuario = input("Usuario del superusuario: ").strip()
    clave = getpass.getpass("Contraseña (mínimo 8 caracteres): ")

    try:
        creada = cuentas_panel.crear(con, usuario, clave, rol="superusuario")
    except ValueError as error:
        print(f"No se pudo crear la cuenta: {error}")
        sys.exit(1)

    otpauth = autenticacion.otpauth_url(creada["otp_secreto"], creada["usuario"])
    ruta_qr = Path(__file__).resolve().parent / "superusuario-qr.svg"
    ruta_qr.write_text(vinculacion.svg(otpauth), encoding="utf-8")

    print()
    print("=" * 56)
    print(f"  Cuenta creada: {creada['usuario']}")
    print("  Escaneá este código con tu app autenticadora:")
    print(f"  {ruta_qr}")
    print("  (abrilo con el navegador o cualquier visor de SVG)")
    print()
    print("  No se puede volver a mostrar. Lo vas a necesitar para")
    print("  recuperar la contraseña si alguna vez la olvidás.")
    print("=" * 56)
    print()
    print("Borrá el archivo del QR después de escanearlo.")

    con.close()


if __name__ == "__main__":
    main()
