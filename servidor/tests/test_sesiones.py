import re

import pytest

from app import reloj
from app.repos import sesiones


def test_crear_devuelve_id_y_abre_conteo_1(con):
    sesion_id = sesiones.crear(con, "Cliente X — 10/08/2026")

    sesion = sesiones.obtener(con, sesion_id)
    assert sesion["nombre"] == "Cliente X — 10/08/2026"
    assert sesion["estado"] == "abierta"

    pasada = sesiones.pasada_abierta(con, sesion_id)
    assert pasada["numero"] == 1
    assert pasada["etiqueta"] == "Conteo 1"


def test_tolerancia_por_defecto(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    sesion = sesiones.obtener(con, sesion_id)

    assert sesion["tolerancia_pct"] == 2.0
    assert sesion["tolerancia_min_abs"] == 1000  # 1 unidad en milésimas


@pytest.mark.parametrize("numero, esperado", [
    (1, "Conteo 1"),
    (2, "Conteo 2"),
    (17, "Conteo 17"),
])
def test_etiqueta_pasada(numero, esperado):
    assert sesiones.etiqueta_pasada(numero) == esperado


def test_no_permite_dos_sesiones_abiertas(con):
    sesiones.crear(con, "Primera")

    with pytest.raises(ValueError, match="Ya hay una sesión abierta"):
        sesiones.crear(con, "Segunda")


def test_se_puede_crear_otra_tras_cerrar(con):
    primera = sesiones.crear(con, "Primera")
    sesiones.cerrar(con, primera)

    segunda = sesiones.crear(con, "Segunda")
    assert segunda != primera
    assert sesiones.sesion_abierta(con)["id"] == segunda


def test_cerrar_cierra_tambien_la_pasada(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    sesiones.cerrar(con, sesion_id)

    fila = con.execute(
        "SELECT estado, fecha_cierre FROM pasada WHERE sesion_id = ?",
        (sesion_id,),
    ).fetchone()
    assert fila["estado"] == "cerrada"
    assert fila["fecha_cierre"] is not None


def test_sesion_abierta_devuelve_none_si_no_hay(con):
    assert sesiones.sesion_abierta(con) is None


def test_listar_devuelve_las_mas_nuevas_primero(con):
    primera = sesiones.crear(con, "Primera")
    sesiones.cerrar(con, primera)
    segunda = sesiones.crear(con, "Segunda")

    listado = sesiones.listar(con)
    assert [s["id"] for s in listado] == [segunda, primera]


def test_fijar_tolerancia(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    sesiones.fijar_tolerancia(con, sesion_id, 5.0, 2000)

    sesion = sesiones.obtener(con, sesion_id)
    assert sesion["tolerancia_pct"] == 5.0
    assert sesion["tolerancia_min_abs"] == 2000


def test_fijar_tolerancia_rechaza_milesimas_con_decimales(con):
    """La base lo rechazaría igual, pero con un mensaje que no dice nada."""
    sesion_id = sesiones.crear(con, "Cliente X")

    with pytest.raises(ValueError, match="milésimas"):
        sesiones.fijar_tolerancia(con, sesion_id, 5.0, 1500.5)


@pytest.mark.parametrize("operacion", [
    lambda con: sesiones.cerrar(con, 999),
    lambda con: sesiones.fijar_tolerancia(con, 999, 2.0, 1000),
])
def test_operar_sobre_una_sesion_inexistente_falla(con, operacion):
    with pytest.raises(ValueError, match="No existe la sesión"):
        operacion(con)


def test_ahora_usa_el_formato_del_proyecto():
    """reloj es la única fuente del formato de fecha de todo el sistema."""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", reloj.ahora())


def test_ultima_pasada_devuelve_la_de_mayor_numero(con):
    """El reparto se mira sobre todo cuando la sesión ya cerró."""
    sesion_id = sesiones.crear(con, "Cliente Z")
    con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion_id, "2026-08-16T10:00:00Z"),
    )

    assert sesiones.ultima_pasada(con, sesion_id)["numero"] == 2


def test_ultima_pasada_no_le_importa_que_este_cerrada(con):
    """`pasada_abierta` tira ValueError acá; esta tiene que contestar igual."""
    sesion_id = sesiones.crear(con, "Cliente Z")
    sesiones.cerrar(con, sesion_id)

    pasada = sesiones.ultima_pasada(con, sesion_id)

    assert pasada["numero"] == 1
    assert pasada["estado"] == "cerrada"
    assert pasada["etiqueta"] == "Conteo 1"


def test_ultima_pasada_sin_ninguna_devuelve_nada(con):
    con.execute(
        "INSERT INTO sesion (nombre, fecha_creacion) VALUES ('Suelta', ?)",
        ("2026-08-16T10:00:00Z",),
    )
    sesion_id = con.execute("SELECT id FROM sesion").fetchone()["id"]

    assert sesiones.ultima_pasada(con, sesion_id) is None
