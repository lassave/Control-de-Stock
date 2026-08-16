import csv
import io

import pytest

from app.repos import asignaciones, conteos, operarios, sesiones
from app.servicios import exportacion, importacion


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,grupo,ubic,um,stock,costo\n"
        "A,Tornillo,Buloneria,P-1,UN,100,25\n"
        "B,Cañería de bronce,Electricidad,P-2,MT,50,\n"
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
        "id_orden", "tipo", "material", "sku", "codigos_de_barra", "descripcion",
        "grupo", "ubicacion", "ubicacion_real", "unidad", "stock_sistema",
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


def test_detalle_tiene_las_columnas_del_spec(con, escenario):
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert list(filas[0].keys()) == [
        "fecha", "fecha_sincronizacion", "pasada", "operario", "sku",
        "descripcion", "unidad", "cantidad", "ubicacion", "ubicacion_real",
        "observaciones", "anulado", "fuera_asignacion",
    ]


def test_la_fecha_del_detalle_es_la_del_conteo_no_la_de_la_sincronizacion(
    con, escenario
):
    """Los celulares sincronizan en lote: una mañana entera compartiría instante."""
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert filas[0]["fecha"] == "2026-08-10T10:00:00Z"
    assert filas[0]["fecha_sincronizacion"] != filas[0]["fecha"]


def test_el_detalle_marca_las_dos_filas_de_una_anulacion(con, escenario):
    """La que anula y la anulada: si falta una, el total no cierra al leerlo."""
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "B", "cantidad": 50000,
        "timestamp_dispositivo": "2026-08-10T10:10:00Z",
    })
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-3", "codigo": "B", "cantidad": 0,
        "timestamp_dispositivo": "2026-08-10T10:20:00Z", "anula_uuid": "u-2",
    })

    marcas = {
        f["observaciones"] or f["cantidad"]: f["anulado"]
        for f in leer_csv(exportacion.detalle(con, escenario["sesion_id"]))
    }

    assert marcas["50"] == "SI"   # la anulada
    assert marcas["0"] == "SI"    # la que anula
    assert marcas["Estaba en otro estante"] == ""  # un escaneo vivo


def test_el_detalle_respeta_los_mismos_filtros_que_el_resumen(con, escenario):
    """Dos archivos que describen poblaciones distintas se leen mal juntos."""
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "B", "cantidad": 50000,
        "timestamp_dispositivo": "2026-08-10T10:10:00Z",
    })

    filas = leer_csv(
        exportacion.detalle(con, escenario["sesion_id"], {"grupo": "Electricidad"})
    )

    assert [f["sku"] for f in filas] == ["B"]


def test_el_resumen_filtrado_devuelve_lo_que_corresponde(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(
        con, escenario["sesion_id"], {"grupo": "Buloneria"}
    ))

    assert [f["sku"] for f in filas] == ["A"]


def test_los_acentos_sobreviven(con, escenario):
    """El BOM lo pone quien sirve el archivo, pero el texto tiene que llegar."""
    texto = exportacion.resumen_por_sku(con, escenario["sesion_id"])

    assert "Cañería" in texto


def test_detalle_sin_asignacion_no_marca(con, escenario):
    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))

    assert filas[0]["fuera_asignacion"] == ""


def test_detalle_marca_fuera_de_asignacion(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(con, pasada["id"], escenario["juan"]["id"], ["Otro deposito"])
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "B", "cantidad": 50000,
        "timestamp_dispositivo": "2026-08-10T10:10:00Z",
    })

    filas = leer_csv(exportacion.detalle(con, escenario["sesion_id"]))
    fila_b = next(f for f in filas if f["sku"] == "B")

    assert fila_b["fuera_asignacion"] == "SI"


def test_resumen_trae_los_codigos_de_barra(con, escenario):
    filas = leer_csv(exportacion.resumen_por_sku(con, escenario["sesion_id"]))
    fila_a = next(f for f in filas if f["sku"] == "A")

    assert fila_a["codigos_de_barra"] == "A"
