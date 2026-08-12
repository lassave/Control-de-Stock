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
