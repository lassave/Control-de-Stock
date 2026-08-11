import csv
import io

import pytest

from app.repos import conteos, operarios, sesiones
from app.servicios import exportacion, importacion


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,grupo,ubic,um,stock,costo\n"
        "A,Tornillo,Buloneria,P-1,UN,100,25\n"
        "B,Cable,Electricidad,P-2,MT,50,\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "grupo": "grupo",
        "ubicacion": "ubic", "unidad": "um", "stock_sistema": "stock",
        "costo_unitario": "costo",
    })
    juan = operarios.crear(con, "Juan")
    conteos.registrar(con, sesion_id, juan["id"], {
        "uuid": "u-1", "codigo": "A", "cantidad": 98000,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
        "ubicacion_real": "P-9", "observaciones": "Estaba en otro estante",
    })
    return {"sesion_id": sesion_id, "juan": juan}


def leer_csv(texto):
    return list(csv.DictReader(io.StringIO(texto), delimiter=";"))


def test_resumen_tiene_las_columnas_del_spec(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))

    assert list(filas[0].keys()) == [
        "id_orden", "tipo", "material", "sku", "descripcion", "grupo",
        "ubicacion", "ubicacion_real", "unidad", "stock_sistema",
        "ultimo_conteo", "dif", "costo_unitario", "dif_valorizada",
        "estado", "fecha", "observaciones",
    ]


def test_cantidades_salen_con_coma_decimal(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_a = next(f for f in filas if f["sku"] == "A")

    assert fila_a["stock_sistema"] == "100"
    assert fila_a["ultimo_conteo"] == "98"
    assert fila_a["dif"] == "-2"


def test_articulo_sin_contar_deja_columnas_vacias(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_b = next(f for f in filas if f["sku"] == "B")

    assert fila_b["ultimo_conteo"] == ""
    assert fila_b["dif"] == ""
    assert fila_b["estado"] == "SIN CONTAR"


def test_valorizacion_vacia_si_no_hay_costo(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_b = next(f for f in filas if f["sku"] == "B")

    assert fila_b["costo_unitario"] == ""
    assert fila_b["dif_valorizada"] == ""


def test_valorizacion_calculada(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_a = next(f for f in filas if f["sku"] == "A")

    assert fila_a["costo_unitario"] == "25,00"
    assert fila_a["dif_valorizada"] == "-50,00"


def test_resumen_respeta_filtros(con, escenario):
    texto = exportacion.resumen_por_sku(
        con, escenario["sesion_id"], {"grupo": "Bazar"}
    )
    filas = leer_csv(texto)

    assert filas == []


def test_detalle_tiene_una_fila_por_escaneo(con, escenario):
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert len(filas) == 1
    assert filas[0]["sku"] == "A"
    assert filas[0]["operario"] == "Juan"
    assert filas[0]["cantidad"] == "98"
    assert filas[0]["pasada"] == "Conteo 1"
    assert filas[0]["ubicacion_real"] == "P-9"
    assert filas[0]["observaciones"] == "Estaba en otro estante"
