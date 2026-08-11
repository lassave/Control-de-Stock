import pytest

from app.repos import operarios


def test_crear_devuelve_token(con):
    juan = operarios.crear(con, "Juan Pérez")

    assert juan["nombre"] == "Juan Pérez"
    assert len(juan["token_dispositivo"]) >= 32
    assert juan["activo"] == 1


def test_tokens_distintos_por_operario(con):
    juan = operarios.crear(con, "Juan")
    ana = operarios.crear(con, "Ana")

    assert juan["token_dispositivo"] != ana["token_dispositivo"]


def test_por_token_encuentra_al_operario(con):
    juan = operarios.crear(con, "Juan")

    encontrado = operarios.por_token(con, juan["token_dispositivo"])

    assert encontrado["id"] == juan["id"]


def test_por_token_devuelve_none_si_no_existe(con):
    assert operarios.por_token(con, "token-inventado") is None


def test_por_token_ignora_desactivados(con):
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    assert operarios.por_token(con, juan["token_dispositivo"]) is None


def test_no_permite_nombres_repetidos(con):
    operarios.crear(con, "Juan")

    with pytest.raises(ValueError, match="Ya existe"):
        operarios.crear(con, "Juan")


def test_listar_ordena_por_nombre(con):
    operarios.crear(con, "Zulema")
    operarios.crear(con, "Ana")

    nombres = [o["nombre"] for o in operarios.listar(con)]

    assert nombres == ["Ana", "Zulema"]
