import pyotp

from app.servicios import autenticacion


def test_una_clave_hasheada_se_verifica_con_la_misma_clave():
    hash_ = autenticacion.hashear_clave("secreta123")

    assert autenticacion.verificar_clave("secreta123", hash_)


def test_una_clave_distinta_no_verifica():
    hash_ = autenticacion.hashear_clave("secreta123")

    assert not autenticacion.verificar_clave("otra-clave", hash_)


def test_dos_hashes_de_la_misma_clave_son_distintos():
    """La sal tiene que ser al azar en cada llamada, o dos cuentas con la
    misma contraseña quedarían con el mismo hash, delatándolo."""
    assert autenticacion.hashear_clave("secreta123") != autenticacion.hashear_clave("secreta123")


def test_un_hash_con_otro_formato_no_verifica_en_vez_de_explotar():
    assert not autenticacion.verificar_clave("cualquiera", "no-es-un-hash-valido")


def test_el_secreto_totp_generado_es_valido_para_pyotp():
    secreto = autenticacion.generar_secreto_totp()

    codigo = pyotp.TOTP(secreto).now()

    assert autenticacion.verificar_totp(secreto, codigo)


def test_un_codigo_incorrecto_no_verifica():
    secreto = autenticacion.generar_secreto_totp()

    assert not autenticacion.verificar_totp(secreto, "000000")


def test_la_url_otpauth_lleva_el_usuario_y_el_nombre_del_sistema():
    secreto = autenticacion.generar_secreto_totp()

    url = autenticacion.otpauth_url(secreto, "pablo")

    assert url.startswith("otpauth://totp/")
    assert "pablo" in url
    assert "Control%20de%20Stock" in url or "Control+de+Stock" in url


def test_un_hash_con_iteraciones_cero_no_verifica_en_vez_de_explotar():
    """La iteración de pbkdf2_hmac con valor <= 0 levanta ValueError.
    verificar_clave debe retornar False en vez de propagar la excepción."""
    assert not autenticacion.verificar_clave("cualquiera", "pbkdf2_sha256$0$deadbeef$aa")


def test_un_hash_con_caracteres_no_ascii_no_verifica_en_vez_de_explotar():
    """secrets.compare_digest levanta TypeError con strings que tienen
    caracteres no-ASCII. verificar_clave debe retornar False."""
    assert not autenticacion.verificar_clave("cualquiera", "pbkdf2_sha256$1000$deadbeef$héllo1")


def test_verificar_totp_sin_secreto_da_falso():
    assert autenticacion.verificar_totp(None, "123456") is False
