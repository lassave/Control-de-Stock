"""Qué SKU entran en una pasada parcial (un recuento)."""

import pytest

from app.repos import pasada_item
from app.servicios import importacion
from app.repos import sesiones


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,stock\n"
        "A,Tornillo,100\n"
        "B,Tuerca,50\n"
        "C,Arandela,10\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "stock_sistema": "stock",
    })
    pasada = sesiones.pasada_abierta(con, sesion_id)

    def id_de(sku):
        return con.execute(
            "SELECT id FROM articulo WHERE sesion_id = ? AND sku = ?",
            (sesion_id, sku),
        ).fetchone()["id"]

    return {"sesion_id": sesion_id, "pasada_id": pasada["id"], "id_de": id_de}


def test_agregar_guarda_las_filas(con, escenario):
    a = escenario["id_de"]("A")
    b = escenario["id_de"]("B")

    pasada_item.agregar(con, escenario["pasada_id"], [a, b])

    assert set(pasada_item.de_pasada(con, escenario["pasada_id"])) == {a, b}


def test_agregar_no_duplica_si_se_reintenta(con, escenario):
    a = escenario["id_de"]("A")

    pasada_item.agregar(con, escenario["pasada_id"], [a])
    pasada_item.agregar(con, escenario["pasada_id"], [a])

    assert pasada_item.de_pasada(con, escenario["pasada_id"]) == [a]


def test_es_parcial_falso_sin_filas(con, escenario):
    assert pasada_item.es_parcial(con, escenario["pasada_id"]) is False


def test_es_parcial_verdadero_con_alguna_fila(con, escenario):
    a = escenario["id_de"]("A")
    pasada_item.agregar(con, escenario["pasada_id"], [a])

    assert pasada_item.es_parcial(con, escenario["pasada_id"]) is True


def test_contiene(con, escenario):
    a = escenario["id_de"]("A")
    b = escenario["id_de"]("B")
    pasada_item.agregar(con, escenario["pasada_id"], [a])

    assert pasada_item.contiene(con, escenario["pasada_id"], a) is True
    assert pasada_item.contiene(con, escenario["pasada_id"], b) is False


def test_de_pasada_vacio_sin_nada_marcado(con, escenario):
    assert pasada_item.de_pasada(con, escenario["pasada_id"]) == []
