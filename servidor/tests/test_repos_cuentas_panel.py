import pytest

from app.repos import cuentas_panel


def test_crear_devuelve_el_secreto_totp_en_texto_plano(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert creada["usuario"] == "pablo"
    assert creada["otp_secreto"]
    assert "id" in creada


def test_no_se_puede_repetir_usuario(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    with pytest.raises(ValueError, match="pablo"):
        cuentas_panel.crear(con, "pablo", "otra-clave")


def test_sin_usuario_no_se_puede_crear(con):
    with pytest.raises(ValueError):
        cuentas_panel.crear(con, "", "clave-larga-123")


def test_sin_clave_no_se_puede_crear(con):
    with pytest.raises(ValueError):
        cuentas_panel.crear(con, "pablo", "")


def test_existe_alguna_es_falso_sin_cuentas(con):
    assert cuentas_panel.existe_alguna(con) is False


def test_existe_alguna_es_verdadero_con_una_cuenta(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert cuentas_panel.existe_alguna(con) is True


def test_por_usuario_trae_el_hash_y_el_secreto(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuenta = cuentas_panel.por_usuario(con, "pablo")

    assert cuenta["usuario"] == "pablo"
    assert cuenta["clave_hash"]
    assert cuenta["otp_secreto"]


def test_por_usuario_inexistente_devuelve_none(con):
    assert cuentas_panel.por_usuario(con, "nadie") is None


def test_listar_no_trae_el_hash_ni_el_secreto(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    listado = cuentas_panel.listar(con)

    assert listado == [{"id": listado[0]["id"], "usuario": "pablo", "activo": 1}]


def test_desactivar_saca_la_cuenta_del_listado(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuentas_panel.desactivar(con, creada["id"])

    assert cuentas_panel.listar(con) == []


def test_desactivar_una_cuenta_inexistente_avisa(con):
    with pytest.raises(ValueError):
        cuentas_panel.desactivar(con, 999)


def test_una_cuenta_desactivada_no_aparece_por_usuario(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cuentas_panel.desactivar(con, creada["id"])

    assert cuentas_panel.por_usuario(con, "pablo") is None


def test_crear_sesion_y_validarla(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    token = cuentas_panel.crear_sesion(con, creada["id"])
    validada = cuentas_panel.sesion_valida(con, token)

    assert validada == {"id": creada["id"], "usuario": "pablo"}


def test_un_token_que_no_existe_no_es_valido(con):
    assert cuentas_panel.sesion_valida(con, "token-inventado") is None


def test_borrar_sesion_la_invalida(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])

    cuentas_panel.borrar_sesion(con, token)

    assert cuentas_panel.sesion_valida(con, token) is None


def test_una_sesion_vencida_no_es_valida(con, monkeypatch):
    from datetime import datetime, timedelta, timezone

    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])

    vencida = (datetime.now(timezone.utc) - timedelta(days=31)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    con.execute(
        "UPDATE sesion_panel SET creado_en = ? WHERE token = ?", (vencida, token)
    )
    con.commit()

    assert cuentas_panel.sesion_valida(con, token) is None
