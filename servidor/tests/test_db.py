import sqlite3
import threading

import pytest

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


def crear_sesion(con):
    con.execute(
        "INSERT INTO sesion (id, nombre, fecha_creacion) VALUES (1, 'X', '2026-08-10T00:00:00Z')"
    )
    return 1


def crear_articulo(con, sesion_id, sku="A", unidad="UN", stock=0):
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, ?, 'Descripción', ?, ?, '2026-08-10T00:00:00Z')",
        (sesion_id, sku, unidad, stock),
    )


def test_rechaza_sku_repetido_en_la_misma_sesion(con):
    sesion_id = crear_sesion(con)
    crear_articulo(con, sesion_id, sku="A")

    with pytest.raises(sqlite3.IntegrityError):
        crear_articulo(con, sesion_id, sku="A")


def test_rechaza_pasada_de_una_sesion_inexistente(con):
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO pasada (sesion_id, numero, fecha_apertura) "
            "VALUES (999, 1, '2026-08-10T00:00:00Z')"
        )


def test_rechaza_unidad_que_no_existe(con):
    """Un CSV que trae «CAJA» en vez de «CJ» no puede entrar sin que nadie lo note."""
    sesion_id = crear_sesion(con)

    with pytest.raises(sqlite3.IntegrityError):
        crear_articulo(con, sesion_id, unidad="CAJA")


def test_rechaza_stock_decimal(con):
    """Las milésimas solo son exactas si la columna guarda enteros de verdad."""
    sesion_id = crear_sesion(con)

    with pytest.raises(sqlite3.IntegrityError):
        crear_articulo(con, sesion_id, stock=3.5)


def test_cada_hilo_recibe_su_propia_conexion(tmp_path):
    """Sin esto, el segundo operario que sincroniza en simultáneo recibe un error."""
    conexion = db.conectar(tmp_path / "hilos.db")
    db.crear_esquema(conexion)

    errores = []

    def consultar():
        try:
            conexion.execute("SELECT COUNT(*) FROM unidad").fetchone()
        except Exception as error:  # noqa: BLE001 — el test reporta cualquiera
            errores.append(error)

    hilos = [threading.Thread(target=consultar) for _ in range(4)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
