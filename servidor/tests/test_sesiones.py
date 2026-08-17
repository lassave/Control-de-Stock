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


# --- Pasada activa de un operario, con recuentos concurrentes ---------------

def _abrir_pasada(con, sesion_id, numero):
    """Inserta una pasada nueva a mano: sesiones.abrir_pasada todavía no existe."""
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, ?, ?)",
        (sesion_id, numero, "2026-08-17T10:00:00Z"),
    )
    return cursor.lastrowid


def test_pasadas_abiertas_devuelve_todas_ordenadas(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    _abrir_pasada(con, sesion_id, 2)
    _abrir_pasada(con, sesion_id, 3)

    numeros = [p["numero"] for p in sesiones.pasadas_abiertas(con, sesion_id)]

    assert numeros == [1, 2, 3]


def test_pasadas_abiertas_no_trae_las_cerradas(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    pasada_2 = _abrir_pasada(con, sesion_id, 2)
    con.execute("UPDATE pasada SET estado = 'cerrada' WHERE id = ?", (pasada_2,))

    numeros = [p["numero"] for p in sesiones.pasadas_abiertas(con, sesion_id)]

    assert numeros == [1]


def test_pasada_general_abierta_es_la_de_menor_numero_sin_pasada_item(con):
    from app.repos import pasada_item as pasada_item_repo

    sesion_id = sesiones.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (sesion_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE sesion_id = ?", (sesion_id,)).fetchone()["id"]
    pasada_2 = _abrir_pasada(con, sesion_id, 2)
    pasada_item_repo.agregar(con, pasada_2, [articulo_id])

    general = sesiones.pasada_general_abierta(con, sesion_id)

    assert general["numero"] == 1


def test_pasada_general_abierta_none_si_todas_son_recuento(con):
    from app.repos import pasada_item as pasada_item_repo

    sesion_id = sesiones.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (sesion_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE sesion_id = ?", (sesion_id,)).fetchone()["id"]
    pasada_1 = sesiones.pasada_abierta(con, sesion_id)
    pasada_item_repo.agregar(con, pasada_1["id"], [articulo_id])

    assert sesiones.pasada_general_abierta(con, sesion_id) is None


def test_pasada_activa_de_operario_sin_asignacion_cae_en_la_general(con):
    from app.repos import operarios

    sesion_id = sesiones.crear(con, "Cliente X")
    juan = operarios.crear(con, "Juan")

    activa = sesiones.pasada_activa_de_operario(con, sesion_id, juan["id"])

    assert activa["numero"] == 1


def test_pasada_activa_de_operario_con_asignacion_en_recuento(con):
    from app.repos import asignaciones, operarios
    from app.repos import pasada_item as pasada_item_repo

    sesion_id = sesiones.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "ubicacion, creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', 'P-1', ?)",
        (sesion_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE sesion_id = ?", (sesion_id,)).fetchone()["id"]
    juan = operarios.crear(con, "Juan")
    pasada_2 = _abrir_pasada(con, sesion_id, 2)
    pasada_item_repo.agregar(con, pasada_2, [articulo_id])
    asignaciones.reemplazar(con, pasada_2, juan["id"], ["P-1"])

    activa = sesiones.pasada_activa_de_operario(con, sesion_id, juan["id"])

    assert activa["numero"] == 2


def test_pasada_activa_de_operario_sin_ninguna_candidata_es_error(con):
    from app.repos import operarios

    sesion_id = sesiones.crear(con, "Cliente X")
    juan = operarios.crear(con, "Juan")
    sesiones.cerrar(con, sesion_id)

    with pytest.raises(ValueError):
        sesiones.pasada_activa_de_operario(con, sesion_id, juan["id"])
