import pytest

from app.repos import cuentas_panel
from app.servicios import autenticacion


def test_crear_superusuario_devuelve_el_secreto_totp_en_texto_plano(con):
    creada = cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    assert creada["usuario"] == "Administrator"
    assert creada["otp_secreto"]
    assert creada["rol"] == "superusuario"
    assert "id" in creada


def test_crear_menor_no_genera_secreto_totp(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert creada["otp_secreto"] is None
    assert creada["rol"] == "menor"


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


def test_clave_de_menos_de_8_caracteres_no_se_puede_crear(con):
    with pytest.raises(ValueError, match="8 caracteres"):
        cuentas_panel.crear(con, "pablo", "1234567")


def test_clave_de_8_caracteres_se_acepta(con):
    creada = cuentas_panel.crear(con, "pablo", "12345678")

    assert creada["usuario"] == "pablo"


def test_por_usuario_trae_el_hash_y_el_rol(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuenta = cuentas_panel.por_usuario(con, "pablo")

    assert cuenta["usuario"] == "pablo"
    assert cuenta["clave_hash"]
    assert cuenta["rol"] == "menor"


def test_por_usuario_de_un_superusuario_trae_el_secreto(con):
    cuentas_panel.crear(con, "Administrator", "clave-larga-123", rol="superusuario")

    cuenta = cuentas_panel.por_usuario(con, "Administrator")

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


def test_se_puede_recrear_una_cuenta_con_el_usuario_de_una_dada_de_baja(con):
    vieja = cuentas_panel.crear(con, "temporal", "clave-larga-123")
    cuentas_panel.desactivar(con, vieja["id"])

    nueva = cuentas_panel.crear(con, "temporal", "otra-clave-larga")

    cuenta = cuentas_panel.por_usuario(con, "temporal")
    assert cuenta["id"] == nueva["id"]
    assert cuenta["id"] != vieja["id"]


def test_no_se_puede_repetir_usuario_entre_dos_cuentas_activas(con):
    cuentas_panel.crear(con, "pablo", "clave-larga-123")

    with pytest.raises(ValueError, match="pablo"):
        cuentas_panel.crear(con, "pablo", "otra-clave-larga")


def test_crear_sesion_y_validarla(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    token = cuentas_panel.crear_sesion(con, creada["id"])
    validada = cuentas_panel.sesion_valida(con, token)

    assert validada == {"id": creada["id"], "usuario": "pablo", "rol": "menor"}


def test_una_sesion_recordada_no_vence_aunque_pasen_mas_de_30_dias(con, monkeypatch):
    from datetime import datetime, timedelta, timezone

    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"], recordar=True)

    vencida = (datetime.now(timezone.utc) - timedelta(days=400)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    con.execute(
        "UPDATE sesion_panel SET creado_en = ? WHERE token = ?", (vencida, token)
    )
    con.commit()

    assert cuentas_panel.sesion_valida(con, token) is not None


def test_un_token_que_no_existe_no_es_valido(con):
    assert cuentas_panel.sesion_valida(con, "token-inventado") is None


def test_borrar_sesion_la_invalida(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])

    cuentas_panel.borrar_sesion(con, token)

    assert cuentas_panel.sesion_valida(con, token) is None


def test_dar_de_baja_la_cuenta_invalida_sus_sesiones_abiertas(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])
    assert cuentas_panel.sesion_valida(con, token) is not None

    cuentas_panel.desactivar(con, creada["id"])

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


def test_generar_codigo_de_recuperacion_es_de_6_digitos(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert len(codigo) == 6
    assert codigo.isdigit()


def test_el_codigo_de_recuperacion_generado_es_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], codigo) is True


def test_un_codigo_incorrecto_no_es_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], "000000") is False


def test_sin_ningun_codigo_pedido_no_hay_codigo_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], "123456") is False


def test_pedir_un_codigo_nuevo_invalida_el_anterior(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    viejo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])
    cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], viejo) is False


def test_un_codigo_vencido_no_es_valido(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    from datetime import datetime, timedelta, timezone
    vencido = (datetime.now(timezone.utc) - timedelta(minutes=16)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    con.execute(
        "UPDATE codigo_recuperacion SET creado_en = ? WHERE cuenta_id = ?",
        (vencido, creada["id"]),
    )
    con.commit()

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], codigo) is False


def test_cambiar_clave_actualiza_el_hash(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    cuentas_panel.cambiar_clave(con, creada["id"], "clave-nueva-456")

    cuenta = cuentas_panel.por_usuario(con, "pablo")
    assert autenticacion.verificar_clave("clave-nueva-456", cuenta["clave_hash"])
    assert not autenticacion.verificar_clave("clave-larga-123", cuenta["clave_hash"])


def test_cambiar_clave_con_una_debil_avisa(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")

    with pytest.raises(ValueError, match="8 caracteres"):
        cuentas_panel.cambiar_clave(con, creada["id"], "corta")


def test_cambiar_clave_borra_el_codigo_de_recuperacion_pendiente(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    codigo = cuentas_panel.generar_codigo_recuperacion(con, creada["id"])

    cuentas_panel.cambiar_clave(con, creada["id"], "clave-nueva-456")

    assert cuentas_panel.verificar_codigo_recuperacion(con, creada["id"], codigo) is False


def test_cambiar_clave_cierra_las_sesiones_abiertas(con):
    creada = cuentas_panel.crear(con, "pablo", "clave-larga-123")
    token = cuentas_panel.crear_sesion(con, creada["id"])
    assert cuentas_panel.sesion_valida(con, token) is not None

    cuentas_panel.cambiar_clave(con, creada["id"], "clave-nueva-456")

    assert cuentas_panel.sesion_valida(con, token) is None
