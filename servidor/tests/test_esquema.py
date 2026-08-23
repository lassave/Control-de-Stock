def test_el_esquema_crea_las_tablas_de_cuentas_de_panel(con):
    tablas = {
        fila["name"]
        for fila in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert "cuenta_panel" in tablas
    assert "sesion_panel" in tablas


def test_cuenta_panel_tiene_rol_y_otp_opcional(con):
    columnas = {
        fila["name"]: fila for fila in con.execute("PRAGMA table_info(cuenta_panel)")
    }
    assert columnas["rol"]["notnull"] == 1
    assert columnas["rol"]["dflt_value"] == "'menor'"
    assert columnas["otp_secreto"]["notnull"] == 0


def test_sesion_panel_tiene_recordar(con):
    columnas = {
        fila["name"]: fila for fila in con.execute("PRAGMA table_info(sesion_panel)")
    }
    assert columnas["recordar"]["notnull"] == 1
    assert columnas["recordar"]["dflt_value"] == "0"


def test_el_esquema_crea_codigo_recuperacion(con):
    tablas = {
        fila["name"]
        for fila in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert "codigo_recuperacion" in tablas


def test_no_se_puede_crear_una_cuenta_con_rol_invalido(con):
    import pytest
    with pytest.raises(Exception):
        con.execute(
            "INSERT INTO cuenta_panel (usuario, clave_hash, rol) "
            "VALUES ('x', 'y', 'lo-que-sea')"
        )
