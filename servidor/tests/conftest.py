import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402


@pytest.fixture
def con():
    conexion = db.conectar(":memory:")
    db.crear_esquema(conexion)
    yield conexion
    conexion.close()


def loguear(cliente, rol="superusuario"):
    """Crea una cuenta de panel directo contra la base del `TestClient` ya
    arrancado, y le pisa la cookie de sesión.

    Superusuario por default: la mayoría de los ~500 tests que usan esto
    no tienen nada que ver con roles, y necesitan poder tocar cualquier
    endpoint —incluidos los de gestión de usuarios— sin pensar en esto.
    Los tests que sí prueban la restricción de rol pasan `rol="menor"`.
    """
    from app.repos import cuentas_panel

    con = cliente.app.state.con
    creada = cuentas_panel.crear(con, "prueba", "clave-de-prueba-123", rol=rol)
    token = cuentas_panel.crear_sesion(con, creada["id"])
    cliente.cookies.set("sesion_panel", token)
