from app import db


def test_crear_esquema_crea_todas_las_tablas(con):
    filas = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    tablas = {fila["name"] for fila in filas}

    esperadas = {
        "sesion", "pasada", "unidad", "articulo", "codigo_barras",
        "operario", "conteo", "pasada_item", "asignacion",
        "mapeo_columnas", "codigo_aprendido", "evento_auditoria",
    }
    assert esperadas <= tablas


def test_unidades_precargadas(con):
    filas = con.execute("SELECT codigo, admite_decimales FROM unidad").fetchall()
    unidades = {fila["codigo"]: fila["admite_decimales"] for fila in filas}

    assert unidades["UN"] == 0
    assert unidades["KG"] == 1
    assert len(unidades) == 8


def test_crear_esquema_es_idempotente(con):
    db.crear_esquema(con)
    db.crear_esquema(con)

    total = con.execute("SELECT COUNT(*) AS n FROM unidad").fetchone()["n"]
    assert total == 8


def test_claves_foraneas_activas(con):
    activo = con.execute("PRAGMA foreign_keys").fetchone()[0]
    assert activo == 1
