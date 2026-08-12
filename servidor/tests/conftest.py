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


@pytest.fixture
def cliente_contrato(tmp_path):
    """Un cliente HTTP sobre una app real, para los tests de contrato."""
    from fastapi.testclient import TestClient

    from app.main import crear_app

    app = crear_app(str(tmp_path / "contrato.db"))
    with TestClient(app) as cliente:
        yield cliente
