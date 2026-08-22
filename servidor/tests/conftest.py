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


def loguear(cliente):
    """Crea una cuenta de panel directo contra la base del `TestClient` ya
    arrancado, y le pisa la cookie de sesión.

    Directo contra la base y no vía `/api/auth/*`: encadenar el login real
    en cada uno de los cientos de tests que ya existían antes de esta
    cuenta los volvería frágiles ante cualquier cambio futuro del propio
    flujo de login, que ya tiene sus propios tests en `test_auth_api.py`.
    """
    from app.repos import cuentas_panel

    con = cliente.app.state.con
    creada = cuentas_panel.crear(con, "prueba", "clave-de-prueba-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])
    cliente.cookies.set("sesion_panel", token)
