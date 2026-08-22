def test_el_esquema_crea_las_tablas_de_cuentas_de_panel(con):
    tablas = {
        fila["name"]
        for fila in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert "cuenta_panel" in tablas
    assert "sesion_panel" in tablas
