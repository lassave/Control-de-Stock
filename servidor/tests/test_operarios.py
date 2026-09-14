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


def test_dar_de_alta_a_alguien_desactivado_lo_reactiva(con):
    """Sin esto, un clic equivocado dejaba el nombre bloqueado para siempre."""
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    revivido = operarios.crear(con, "Juan")

    assert revivido["id"] == juan["id"]
    assert revivido["activo"] == 1
    assert operarios.por_token(con, revivido["token_dispositivo"]) is not None


def test_reactivar_cambia_el_token(con):
    """El celular que quedó desvinculado no tiene que volver a funcionar solo."""
    juan = operarios.crear(con, "Juan")
    token_viejo = juan["token_dispositivo"]
    operarios.desactivar(con, juan["id"])

    operarios.crear(con, "Juan")

    assert operarios.por_token(con, token_viejo) is None


def test_el_nombre_se_normaliza(con):
    """«Juan» y «Juan » partirían el conteo de una misma persona en dos."""
    operarios.crear(con, "Juan")

    with pytest.raises(ValueError, match="Ya existe"):
        operarios.crear(con, "  Juan  ")


@pytest.mark.parametrize("nombre", ["", "   ", None, 123])
def test_rechaza_nombres_invalidos(con, nombre):
    with pytest.raises(ValueError, match="necesita un nombre"):
        operarios.crear(con, nombre)


def test_no_expone_el_pin(con):
    """El PIN no tiene por qué viajar en cada respuesta del panel."""
    juan = operarios.crear(con, "Juan", pin="1234")

    assert "pin" not in juan
    assert "pin" not in operarios.listar(con)[0]
    assert "pin" not in operarios.por_token(con, juan["token_dispositivo"])


def test_desactivar_a_alguien_que_no_existe_falla(con):
    with pytest.raises(ValueError, match="No existe el operario"):
        operarios.desactivar(con, 9999)


def test_listar_para_identificar_dice_si_tiene_pin(con):
    operarios.crear(con, "Juan")
    operarios.crear(con, "Ana", pin="1234")

    listado = {o["nombre"]: o["tiene_pin"] for o in operarios.listar_para_identificar(con)}

    assert listado == {"Juan": False, "Ana": True}


def test_listar_para_identificar_no_expone_ni_el_pin_ni_el_token(con):
    operarios.crear(con, "Ana", pin="1234")

    campos = set(operarios.listar_para_identificar(con)[0])

    assert campos == {"id", "nombre", "tiene_pin"}


def test_listar_para_identificar_ordena_por_nombre(con):
    operarios.crear(con, "Zulema")
    operarios.crear(con, "Ana")

    nombres = [o["nombre"] for o in operarios.listar_para_identificar(con)]

    assert nombres == ["Ana", "Zulema"]


def test_listar_para_identificar_ignora_desactivados(con):
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    assert operarios.listar_para_identificar(con) == []


def test_para_identificar_encuentra_por_nombre_y_trae_el_pin(con):
    juan = operarios.crear(con, "Juan", pin="1234")

    encontrado = operarios.para_identificar(con, "Juan")

    assert encontrado["id"] == juan["id"]
    assert encontrado["pin"] == "1234"
    assert encontrado["token_dispositivo"] == juan["token_dispositivo"]


def test_para_identificar_devuelve_none_si_no_existe(con):
    assert operarios.para_identificar(con, "Nadie") is None


def test_para_identificar_ignora_desactivados(con):
    juan = operarios.crear(con, "Juan")
    operarios.desactivar(con, juan["id"])

    assert operarios.para_identificar(con, "Juan") is None
