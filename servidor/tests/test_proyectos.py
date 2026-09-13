import re

import pytest

from app import reloj
from app.repos import proyectos


def test_crear_devuelve_id_y_abre_conteo_1(con):
    proyecto_id = proyectos.crear(con, "Cliente X — 10/08/2026")

    proyecto = proyectos.obtener(con, proyecto_id)
    assert proyecto["nombre"] == "Cliente X — 10/08/2026"
    assert proyecto["estado"] == "abierta"

    pasada = proyectos.pasada_abierta(con, proyecto_id)
    assert pasada["numero"] == 1
    assert pasada["etiqueta"] == "Conteo 1"


def test_tolerancia_por_defecto(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    proyecto = proyectos.obtener(con, proyecto_id)

    assert proyecto["tolerancia_pct"] == 2.0
    assert proyecto["tolerancia_min_abs"] == 1000  # 1 unidad en milésimas


@pytest.mark.parametrize("numero, esperado", [
    (1, "Conteo 1"),
    (2, "Conteo 2"),
    (17, "Conteo 17"),
])
def test_etiqueta_pasada(numero, esperado):
    assert proyectos.etiqueta_pasada(numero) == esperado


def test_no_permite_dos_proyectos_abiertos(con):
    proyectos.crear(con, "Primera")

    with pytest.raises(ValueError, match="Ya hay un proyecto abierto"):
        proyectos.crear(con, "Segunda")


def test_se_puede_crear_otra_tras_cerrar(con):
    primera = proyectos.crear(con, "Primera")
    proyectos.cerrar(con, primera)

    segunda = proyectos.crear(con, "Segunda")
    assert segunda != primera
    assert proyectos.proyecto_abierto(con)["id"] == segunda


def test_cerrar_cierra_tambien_la_pasada(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    proyectos.cerrar(con, proyecto_id)

    fila = con.execute(
        "SELECT estado, fecha_cierre FROM pasada WHERE proyecto_id = ?",
        (proyecto_id,),
    ).fetchone()
    assert fila["estado"] == "cerrada"
    assert fila["fecha_cierre"] is not None


def test_proyecto_abierto_devuelve_none_si_no_hay(con):
    assert proyectos.proyecto_abierto(con) is None


def test_listar_devuelve_las_mas_nuevas_primero(con):
    primera = proyectos.crear(con, "Primera")
    proyectos.cerrar(con, primera)
    segunda = proyectos.crear(con, "Segunda")

    listado = proyectos.listar(con)
    assert [p["id"] for p in listado] == [segunda, primera]


def test_fijar_tolerancia(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    proyectos.fijar_tolerancia(con, proyecto_id, 5.0, 2000)

    proyecto = proyectos.obtener(con, proyecto_id)
    assert proyecto["tolerancia_pct"] == 5.0
    assert proyecto["tolerancia_min_abs"] == 2000


def test_fijar_tolerancia_rechaza_milesimas_con_decimales(con):
    """La base lo rechazaría igual, pero con un mensaje que no dice nada."""
    proyecto_id = proyectos.crear(con, "Cliente X")

    with pytest.raises(ValueError, match="milésimas"):
        proyectos.fijar_tolerancia(con, proyecto_id, 5.0, 1500.5)


@pytest.mark.parametrize("operacion", [
    lambda con: proyectos.cerrar(con, 999),
    lambda con: proyectos.fijar_tolerancia(con, 999, 2.0, 1000),
])
def test_operar_sobre_un_proyecto_inexistente_falla(con, operacion):
    with pytest.raises(ValueError, match="No existe el proyecto"):
        operacion(con)


def test_ahora_usa_el_formato_del_proyecto():
    """reloj es la única fuente del formato de fecha de todo el sistema."""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", reloj.ahora())


def test_ultima_pasada_devuelve_la_de_mayor_numero(con):
    """El reparto se mira sobre todo cuando el proyecto ya cerró."""
    proyecto_id = proyectos.crear(con, "Cliente Z")
    con.execute(
        "INSERT INTO pasada (proyecto_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (proyecto_id, "2026-08-16T10:00:00Z"),
    )

    assert proyectos.ultima_pasada(con, proyecto_id)["numero"] == 2


def test_ultima_pasada_no_le_importa_que_este_cerrada(con):
    """`pasada_abierta` tira ValueError acá; esta tiene que contestar igual."""
    proyecto_id = proyectos.crear(con, "Cliente Z")
    proyectos.cerrar(con, proyecto_id)

    pasada = proyectos.ultima_pasada(con, proyecto_id)

    assert pasada["numero"] == 1
    assert pasada["estado"] == "cerrada"
    assert pasada["etiqueta"] == "Conteo 1"


def test_ultima_pasada_sin_ninguna_devuelve_nada(con):
    con.execute(
        "INSERT INTO proyecto (nombre, fecha_creacion) VALUES ('Suelta', ?)",
        ("2026-08-16T10:00:00Z",),
    )
    proyecto_id = con.execute("SELECT id FROM proyecto").fetchone()["id"]

    assert proyectos.ultima_pasada(con, proyecto_id) is None


# --- Pasada activa de un operario, con recuentos concurrentes ---------------

def _abrir_pasada(con, proyecto_id, numero):
    """Inserta una pasada nueva a mano: proyectos.abrir_pasada todavía no existe."""
    cursor = con.execute(
        "INSERT INTO pasada (proyecto_id, numero, fecha_apertura) VALUES (?, ?, ?)",
        (proyecto_id, numero, "2026-08-17T10:00:00Z"),
    )
    return cursor.lastrowid


def test_pasadas_abiertas_devuelve_todas_ordenadas(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    _abrir_pasada(con, proyecto_id, 2)
    _abrir_pasada(con, proyecto_id, 3)

    numeros = [p["numero"] for p in proyectos.pasadas_abiertas(con, proyecto_id)]

    assert numeros == [1, 2, 3]


def test_pasadas_abiertas_no_trae_las_cerradas(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    pasada_2 = _abrir_pasada(con, proyecto_id, 2)
    con.execute("UPDATE pasada SET estado = 'cerrada' WHERE id = ?", (pasada_2,))

    numeros = [p["numero"] for p in proyectos.pasadas_abiertas(con, proyecto_id)]

    assert numeros == [1]


def test_pasada_general_abierta_es_la_de_menor_numero_sin_pasada_item(con):
    from app.repos import pasada_item as pasada_item_repo

    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    pasada_2 = _abrir_pasada(con, proyecto_id, 2)
    pasada_item_repo.agregar(con, pasada_2, [articulo_id])

    general = proyectos.pasada_general_abierta(con, proyecto_id)

    assert general["numero"] == 1


def test_pasada_general_abierta_none_si_todas_son_recuento(con):
    from app.repos import pasada_item as pasada_item_repo

    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    pasada_1 = proyectos.pasada_abierta(con, proyecto_id)
    pasada_item_repo.agregar(con, pasada_1["id"], [articulo_id])

    assert proyectos.pasada_general_abierta(con, proyecto_id) is None


def test_pasada_activa_de_operario_sin_asignacion_cae_en_la_general(con):
    from app.repos import operarios

    proyecto_id = proyectos.crear(con, "Cliente X")
    juan = operarios.crear(con, "Juan")

    activa = proyectos.pasada_activa_de_operario(con, proyecto_id, juan["id"])

    assert activa["numero"] == 1


def test_pasada_activa_de_operario_con_asignacion_en_recuento(con):
    from app.repos import asignaciones, operarios
    from app.repos import pasada_item as pasada_item_repo

    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "ubicacion, creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', 'P-1', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    juan = operarios.crear(con, "Juan")
    pasada_2 = _abrir_pasada(con, proyecto_id, 2)
    pasada_item_repo.agregar(con, pasada_2, [articulo_id])
    asignaciones.reemplazar(con, pasada_2, juan["id"], ["P-1"])

    activa = proyectos.pasada_activa_de_operario(con, proyecto_id, juan["id"])

    assert activa["numero"] == 2


def test_pasada_activa_de_operario_sin_ninguna_candidata_es_error(con):
    from app.repos import operarios

    proyecto_id = proyectos.crear(con, "Cliente X")
    juan = operarios.crear(con, "Juan")
    proyectos.cerrar(con, proyecto_id)

    with pytest.raises(ValueError):
        proyectos.pasada_activa_de_operario(con, proyecto_id, juan["id"])


# --- listar_pasadas y abrir_pasada ------------------------------------------

def test_listar_pasadas_marca_general_y_recuento(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]

    from app.repos import pasada_item
    cursor = con.execute(
        "INSERT INTO pasada (proyecto_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    pasada_item.agregar(con, cursor.lastrowid, [articulo_id])

    pasadas = proyectos.listar_pasadas(con, proyecto_id)

    assert pasadas[0]["numero"] == 1
    assert pasadas[0]["es_parcial"] is False
    assert pasadas[1]["numero"] == 2
    assert pasadas[1]["es_parcial"] is True


def test_abrir_pasada_crea_la_siguiente_con_sus_sku(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]

    pasada = proyectos.abrir_pasada(con, proyecto_id, [articulo_id])

    assert pasada["numero"] == 2
    assert pasada["etiqueta"] == "Conteo 2"

    from app.repos import pasada_item
    assert pasada_item.de_pasada(con, pasada["id"]) == [articulo_id]


def test_abrir_pasada_con_lista_vacia_rechaza(con):
    proyecto_id = proyectos.crear(con, "Cliente X")

    with pytest.raises(ValueError):
        proyectos.abrir_pasada(con, proyecto_id, [])


def test_abrir_pasada_con_proyecto_cerrado_rechaza(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    proyectos.cerrar(con, proyecto_id)

    with pytest.raises(ValueError):
        proyectos.abrir_pasada(con, proyecto_id, [articulo_id])


def test_abrir_pasada_permite_varias_seguidas(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]

    proyectos.abrir_pasada(con, proyecto_id, [articulo_id])
    tercera = proyectos.abrir_pasada(con, proyecto_id, [articulo_id])

    assert tercera["numero"] == 3


def test_listar_pasadas_informa_cuantos_sku_tiene_el_recuento(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    proyectos.abrir_pasada(con, proyecto_id, [articulo_id])

    pasadas = proyectos.listar_pasadas(con, proyecto_id)

    assert pasadas[0]["cantidad_sku"] == 0
    assert pasadas[1]["cantidad_sku"] == 1


# --- borrar_pasada -----------------------------------------------------------

def test_borrar_pasada_sin_conteos_la_elimina(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    recuento = proyectos.abrir_pasada(con, proyecto_id, [articulo_id])

    proyectos.borrar_pasada(con, proyecto_id, recuento["id"])

    assert proyectos.obtener_pasada(con, proyecto_id, recuento["id"]) is None


def test_borrar_pasada_borra_tambien_sus_asignaciones_y_sku(con):
    from app.repos import asignaciones, operarios, pasada_item

    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, ubicacion, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', 'P-1', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    recuento = proyectos.abrir_pasada(con, proyecto_id, [articulo_id])
    operario = operarios.crear(con, "Juan")
    asignaciones.reemplazar(con, recuento["id"], operario["id"], ["P-1"])

    proyectos.borrar_pasada(con, proyecto_id, recuento["id"])

    assert pasada_item.de_pasada(con, recuento["id"]) == []
    assert asignaciones.de_operario(con, recuento["id"], operario["id"]) == []


def test_borrar_pasada_con_conteos_rechaza(con):
    from app.repos import asignaciones, conteos, operarios

    proyecto_id = proyectos.crear(con, "Cliente X")
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, ubicacion, "
        "creado_en) VALUES (?, 1, 'A', 'Tornillo', 'UN', 'P-1', ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    articulo_id = con.execute("SELECT id FROM articulo WHERE proyecto_id = ?", (proyecto_id,)).fetchone()["id"]
    con.execute(
        "INSERT INTO codigo_barras (articulo_id, codigo) VALUES (?, 'A')", (articulo_id,)
    )
    recuento = proyectos.abrir_pasada(con, proyecto_id, [articulo_id])
    operario = operarios.crear(con, "Juan")
    asignaciones.reemplazar(con, recuento["id"], operario["id"], ["P-1"])
    conteos.registrar(con, proyecto_id, operario["id"], {
        "uuid": "u1", "codigo": "A", "cantidad": 1000,
        "timestamp_dispositivo": "2026-08-17T10:00:00Z",
    })

    with pytest.raises(ValueError):
        proyectos.borrar_pasada(con, proyecto_id, recuento["id"])

    assert proyectos.obtener_pasada(con, proyecto_id, recuento["id"]) is not None


def test_borrar_pasada_general_rechaza(con):
    proyecto_id = proyectos.crear(con, "Cliente X")

    with pytest.raises(ValueError):
        proyectos.borrar_pasada(con, proyecto_id, 1)


def test_borrar_pasada_inexistente_rechaza(con):
    proyecto_id = proyectos.crear(con, "Cliente X")

    with pytest.raises(ValueError):
        proyectos.borrar_pasada(con, proyecto_id, 999)
