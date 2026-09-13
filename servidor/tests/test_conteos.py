import sqlite3

import pytest

from app.repos import asignaciones, conteos, operarios, proyectos
from app.servicios import importacion


@pytest.fixture
def escenario(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,ean\n"
        "10453,Tornillo hex,7791111111111\n"
        "10454,Tuerca,7792222222222\n"
    ).encode("utf-8")
    importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "codigo_barras": "ean",
    })
    juan = operarios.crear(con, "Juan")
    ana = operarios.crear(con, "Ana")
    return {"proyecto_id": proyecto_id, "juan": juan, "ana": ana}


def evento(uuid, codigo="7791111111111", cantidad=24000, **extra):
    base = {
        "uuid": uuid,
        "codigo": codigo,
        "cantidad": cantidad,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
    }
    base.update(extra)
    return base


def test_registrar_guarda_el_conteo(con, escenario):
    resultado = conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
    )

    assert resultado == "registrado"
    fila = con.execute("SELECT * FROM conteo WHERE uuid = 'u-1'").fetchone()
    assert fila["cantidad"] == 24000
    assert fila["timestamp_servidor"] is not None


def test_reenviar_el_mismo_uuid_no_duplica(con, escenario):
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))
    resultado = conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
    )

    assert resultado == "duplicado"
    total = con.execute("SELECT COUNT(*) AS n FROM conteo").fetchone()["n"]
    assert total == 1


def test_lote_reporta_registrados_y_duplicados(con, escenario):
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))

    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1"), evento("u-2"), evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert resultado["duplicados"] == 1
    assert resultado["rechazados"] == []


def test_codigo_desconocido_se_rechaza_sin_frenar_el_lote(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1"), evento("u-2", codigo="0000000000000"), evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert len(resultado["rechazados"]) == 1
    assert resultado["rechazados"][0]["uuid"] == "u-2"


def test_anulacion_referencia_al_conteo_original(con, escenario):
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))
    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-2", cantidad=0, anula_uuid="u-1"),
    )

    fila = con.execute("SELECT anula_uuid FROM conteo WHERE uuid = 'u-2'").fetchone()
    assert fila["anula_uuid"] == "u-1"


def test_anular_un_uuid_inexistente_se_rechaza(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-9", anula_uuid="no-existe")],
    )

    assert resultado["registrados"] == 0
    assert len(resultado["rechazados"]) == 1


@pytest.mark.parametrize("roto", [
    {"codigo": None},
    {"timestamp_dispositivo": None},
    {"timestamp_dispositivo": "   "},
    {"timestamp_dispositivo": 12345},
    {"uuid": None},
    {"cantidad": None},
    {"cantidad": -1000},
    # Los enteros de JSON no tienen tope; los de SQLite sí.
    {"cantidad": 2 ** 63},
    # Valores no escalares: explotarían recién al ligarlos a la consulta,
    # como sqlite3.ProgrammingError, que no es ValueError.
    {"uuid": ["u-2"]},
    {"codigo": {"ean": "779"}},
    {"anula_uuid": ["u-1"]},
    {"ubicacion_real": ["A-01"]},
    {"observaciones": {"nota": "rota"}},
])
def test_un_evento_mal_formado_no_frena_el_lote(con, escenario, roto):
    """Sin esto el celular reintenta el mismo payload y la cola queda trabada."""
    malo = evento("u-2")
    malo.update(roto)

    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1"), malo, evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert len(resultado["rechazados"]) == 1


def test_un_evento_que_ni_siquiera_es_un_diccionario_no_frena_el_lote(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1"), "esto no es un evento", evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert len(resultado["rechazados"]) == 1


def test_una_anulacion_que_llega_antes_es_reintentable(con, escenario):
    """Los celulares sincronizan en cualquier orden: el evento no se descarta."""
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-9", anula_uuid="todavia-no-llego")],
    )

    assert resultado["rechazados"][0]["reintentable"] is True


def test_un_error_transitorio_de_la_base_es_reintentable(con, escenario, monkeypatch):
    """«database is locked» pasa cuando dos operarios sincronizan a la vez.

    Marcarlo como definitivo haría que el celular descarte un conteo que el
    operario sí hizo: una unidad que desaparece sin que nadie se entere.
    """
    def falla(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(conteos, "registrar", falla)

    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"], [evento("u-1")]
    )

    assert resultado["rechazados"][0]["reintentable"] is True


def test_una_anulacion_vacia_se_trata_como_ausente(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1", anula_uuid="")],
    )

    assert resultado["registrados"] == 1
    assert resultado["rechazados"] == []


def test_una_anulacion_no_se_puede_anular(con, escenario):
    """Si no, el conteo original queda excluido por una fila que ya no vale y
    el artículo vuelve a figurar sin contar: desaparecen unidades reales."""
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))
    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-2", cantidad=0, anula_uuid="u-1"),
    )

    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-3", cantidad=0, anula_uuid="u-2")],
    )

    assert resultado["registrados"] == 0
    assert resultado["rechazados"][0]["reintentable"] is False


def test_un_conteo_no_puede_anularse_a_si_mismo(con, escenario):
    """La única fila que lo satisfaría es la que se está rechazando."""
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1", anula_uuid="u-1")],
    )

    assert resultado["registrados"] == 0
    # Si saliera reintentable, el celular lo reenviaría para siempre.
    assert resultado["rechazados"][0]["reintentable"] is False


def test_un_codigo_desconocido_no_es_reintentable(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1", codigo="0000000000000")],
    )

    assert resultado["rechazados"][0]["reintentable"] is False


def test_no_se_puede_anular_el_conteo_de_otro_articulo(con, escenario):
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))

    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-2", codigo="7792222222222", anula_uuid="u-1")],
    )

    assert resultado["registrados"] == 0
    assert len(resultado["rechazados"]) == 1


def test_el_mismo_uuid_dos_veces_en_un_lote_se_registra_una_sola(con, escenario):
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1"), evento("u-1")],
    )

    assert resultado["registrados"] == 1
    assert resultado["duplicados"] == 1


@pytest.mark.parametrize("cantidad", [24.5, "24000", True])
def test_una_cantidad_que_no_es_entera_no_frena_el_lote(con, escenario, cantidad):
    """El CHECK del esquema la rechazaría abortando todo el lote."""
    resultado = conteos.registrar_lote(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        [evento("u-1"), evento("u-2", cantidad=cantidad), evento("u-3")],
    )

    assert resultado["registrados"] == 2
    assert [r["uuid"] for r in resultado["rechazados"]] == ["u-2"]


def test_no_se_puede_anular_un_conteo_de_otro_proyecto(con, escenario):
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))
    proyectos.cerrar(con, escenario["proyecto_id"])

    otro = proyectos.crear(con, "Otro cliente")
    importacion.importar(
        con, otro, "sku,detalle,ean\n10453,Tornillo hex,7791111111111\n".encode("utf-8"),
        {"sku": "sku", "descripcion": "detalle", "codigo_barras": "ean"},
    )

    resultado = conteos.registrar_lote(
        con, otro, escenario["juan"]["id"],
        [evento("u-9", anula_uuid="u-1")],
    )

    assert resultado["registrados"] == 0
    assert len(resultado["rechazados"]) == 1
    # El uuid es único en toda la base: reintentarlo nunca va a funcionar.
    assert resultado["rechazados"][0]["reintentable"] is False


def test_guarda_ubicacion_real_y_observaciones(con, escenario):
    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="C-01", observaciones="Estaba mal ubicado"),
    )

    fila = con.execute("SELECT * FROM conteo WHERE uuid = 'u-1'").fetchone()
    assert fila["ubicacion_real"] == "C-01"
    assert fila["observaciones"] == "Estaba mal ubicado"


def test_buscar_por_codigo_devuelve_el_articulo(con, escenario):
    articulo = conteos.buscar_por_codigo(con, escenario["proyecto_id"], "7792222222222")

    assert articulo["sku"] == "10454"
    assert articulo["descripcion"] == "Tuerca"


def test_buscar_por_codigo_no_expone_stock_ni_costo(con, escenario):
    articulo = conteos.buscar_por_codigo(con, escenario["proyecto_id"], "7791111111111")

    assert "stock_sistema" not in articulo
    assert "costo_unitario" not in articulo


def test_de_operario_solo_devuelve_lo_propio(con, escenario):
    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))
    conteos.registrar(con, escenario["proyecto_id"], escenario["ana"]["id"], evento("u-2"))

    propios = conteos.de_operario(
        con, escenario["proyecto_id"], escenario["juan"]["id"]
    )

    assert [c["uuid"] for c in propios] == ["u-1"]


def test_de_operario_devuelve_lo_mas_reciente_primero(con, escenario):
    for numero in range(1, 4):
        conteos.registrar(
            con, escenario["proyecto_id"], escenario["juan"]["id"],
            evento(f"u-{numero}"),
        )

    propios = conteos.de_operario(con, escenario["proyecto_id"], escenario["juan"]["id"])

    assert [c["uuid"] for c in propios] == ["u-3", "u-2", "u-1"]


def test_sin_asignacion_no_se_marca(con, escenario):
    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="Deposito A"),
    )

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 0


def test_contar_en_la_ubicacion_asignada_no_se_marca(con, escenario):
    pasada = proyectos.pasada_abierta(con, escenario["proyecto_id"])
    asignaciones.reemplazar(
        con, pasada["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="Deposito A"),
    )

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 0


def test_contar_fuera_de_lo_asignado_se_marca(con, escenario):
    pasada = proyectos.pasada_abierta(con, escenario["proyecto_id"])
    asignaciones.reemplazar(
        con, pasada["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-1", ubicacion_real="Deposito B"),
    )

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 1


def test_sin_ubicacion_conocida_no_se_marca(con, escenario):
    """El artículo del escenario no tiene ubicación en el maestro, y este
    evento tampoco trae una corrección: no hay con qué comparar."""
    pasada = proyectos.pasada_abierta(con, escenario["proyecto_id"])
    asignaciones.reemplazar(
        con, pasada["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    conteos.registrar(con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1"))

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 0


def test_usa_la_ubicacion_del_articulo_si_no_hay_correccion(con):
    proyecto_id = proyectos.crear(con, "Cliente Z")
    contenido = "sku,detalle,ubic\nA,Tornillo,Deposito A\n".encode("utf-8")
    importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "ubicacion": "ubic",
    })
    juan = operarios.crear(con, "Juan")
    pasada = proyectos.pasada_abierta(con, proyecto_id)
    asignaciones.reemplazar(con, pasada["id"], juan["id"], ["Deposito B"])

    conteos.registrar(con, proyecto_id, juan["id"], {
        "uuid": "u-1", "codigo": "A", "cantidad": 1000,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
    })

    fila = con.execute(
        "SELECT fuera_asignacion FROM conteo WHERE uuid = 'u-1'"
    ).fetchone()
    assert fila["fuera_asignacion"] == 1


# --- Pasada activa del operario y bloqueo de SKU fuera de recuento ---------

def _abrir_recuento(con, proyecto_id, articulo_ids):
    """Abre una pasada 2 con esos SKU marcados. proyectos.abrir_pasada
    todavía no existe (tarea aparte); se arma a mano."""
    from app.repos import pasada_item

    cursor = con.execute(
        "INSERT INTO pasada (proyecto_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (proyecto_id, "2026-08-17T10:00:00Z"),
    )
    pasada_id = cursor.lastrowid
    pasada_item.agregar(con, pasada_id, articulo_ids)
    return pasada_id


def _id_de(con, proyecto_id, sku):
    return con.execute(
        "SELECT id FROM articulo WHERE proyecto_id = ? AND sku = ?",
        (proyecto_id, sku),
    ).fetchone()["id"]


def test_un_conteo_en_la_pasada_general_sigue_aceptando_cualquier_sku(con, escenario):
    resultado = conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
    )

    assert resultado == "registrado"


def test_un_sku_marcado_para_el_recuento_se_acepta(con, escenario):
    a = _id_de(con, escenario["proyecto_id"], "10453")
    pasada_2 = _abrir_recuento(con, escenario["proyecto_id"], [a])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["P-1"])

    resultado = conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
    )

    assert resultado == "registrado"
    fila = con.execute("SELECT pasada_id FROM conteo WHERE uuid = 'u-1'").fetchone()
    assert fila["pasada_id"] == pasada_2


def test_un_sku_no_marcado_para_el_recuento_se_rechaza(con, escenario):
    b = _id_de(con, escenario["proyecto_id"], "10454")
    pasada_2 = _abrir_recuento(con, escenario["proyecto_id"], [b])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["P-1"])

    with pytest.raises(conteos.EventoInvalido) as excinfo:
        conteos.registrar(
            con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
        )

    assert "no está en el conteo actual" in str(excinfo.value)
    assert excinfo.value.reintentable is False


def test_una_anulacion_no_pasa_por_el_bloqueo_de_sku(con, escenario):
    b = _id_de(con, escenario["proyecto_id"], "10454")
    pasada_2 = _abrir_recuento(con, escenario["proyecto_id"], [b])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["P-1"])

    conteos.registrar(con, escenario["proyecto_id"], escenario["ana"]["id"], evento("u-original"))

    resultado = conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"],
        evento("u-anula", cantidad=0, anula_uuid="u-original"),
    )

    assert resultado == "registrado"


def test_operario_sin_pasada_activa_da_un_error_claro(con, escenario):
    proyectos.cerrar(con, escenario["proyecto_id"])

    with pytest.raises(ValueError):
        conteos.registrar(
            con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
        )


def test_operario_no_asignado_al_recuento_sigue_cayendo_en_la_general(con, escenario):
    """Con dos pasadas abiertas, un operario ajeno al recuento no puede
    quedar atrapado ahí solo porque tiene el numero mas alto."""
    a = _id_de(con, escenario["proyecto_id"], "10453")
    pasada_2 = _abrir_recuento(con, escenario["proyecto_id"], [a])
    asignaciones.reemplazar(con, pasada_2, escenario["ana"]["id"], ["P-1"])
    # Juan no está asignado al recuento: sigue en la pasada general (1).

    conteos.registrar(
        con, escenario["proyecto_id"], escenario["juan"]["id"], evento("u-1")
    )

    fila = con.execute("SELECT pasada_id FROM conteo WHERE uuid = 'u-1'").fetchone()
    pasada_1 = proyectos.obtener(con, escenario["proyecto_id"])
    assert fila["pasada_id"] != pasada_2
