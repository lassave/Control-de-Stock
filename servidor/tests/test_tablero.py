import pytest

from app.repos import conteos, operarios, sesiones
from app.servicios import importacion, tablero


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,grupo,ubic,stock\n"
        "A,Tornillo,Buloneria,P-1,100\n"
        "B,Tuerca,Buloneria,P-1,50\n"
        "C,Arandela,Bazar,P-2,10\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "grupo": "grupo",
        "ubicacion": "ubic", "stock_sistema": "stock",
    })
    juan = operarios.crear(con, "Juan")
    return {"sesion_id": sesion_id, "juan": juan}


def contar(con, escenario, codigo, cantidad, uuid):
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": uuid,
        "codigo": codigo,
        "cantidad": cantidad,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z",
    })


@pytest.mark.parametrize("dif, stock, esperado", [
    (0,      100000, tablero.CONSOLIDADO),   # exacto
    (2000,   100000, tablero.CONSOLIDADO),   # 2% de 100 = 2 unidades
    (-2000,  100000, tablero.CONSOLIDADO),   # tolera para ambos lados
    (2001,   100000, tablero.A_RECONTAR),    # apenas afuera
    (1000,   3000,   tablero.CONSOLIDADO),   # 2% de 3 es 0,06: manda el mínimo de 1
    (1001,   3000,   tablero.A_RECONTAR),
    (1000,   0,      tablero.CONSOLIDADO),   # stock cero, entra por el mínimo
    (2000,   -100000, tablero.CONSOLIDADO),  # stock negativo del ERP: cuenta el absoluto
])
def test_estado_de(dif, stock, esperado):
    assert tablero.estado_de(dif, stock, 2.0, 1000, hubo_conteo=True) == esperado


def test_sin_conteo_es_sin_contar():
    assert tablero.estado_de(0, 100000, 2.0, 1000, hubo_conteo=False) == tablero.SIN_CONTAR


@pytest.mark.parametrize("contado, stock, esperado", [
    (240000, 24000, "dígito de más"),      # 240 en vez de 24
    (2000,   24000, "dígito de más"),      # 2 en vez de 24
    (2400000, 24000, "dígito de más"),     # 2400 en vez de 24
    (42000,  24000, "dígitos permutados"), # 42 en vez de 24
    (55000,  5000,  "dígito repetido"),    # 55 en vez de 5
    (23000,  24000, None),                 # diferencia común, no tiene forma de tipeo
    (0,      24000, None),                 # faltante total: es un hallazgo, no un error
    (24000,  24000, None),                 # sin diferencia
    (0,      0,     None),                 # ambos en cero: nada que comparar
])
def test_parece_error_de_carga(contado, stock, esperado):
    assert tablero.parece_error_de_carga(contado, stock) == esperado


def test_marca_error_de_carga_solo_a_los_que_hay_que_recontar(con, escenario):
    contar(con, escenario, "C", 100000, "u-1")  # el sistema dice 10, se cargaron 100

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "C")

    assert fila["estado"] == tablero.A_RECONTAR
    assert fila["posible_error_carga"] == "dígito de más"


def test_los_consolidados_no_se_marcan(con, escenario):
    contar(con, escenario, "A", 100000, "u-1")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["posible_error_carga"] is None


def test_filas_traen_todos_los_articulos(con, escenario):
    filas = tablero.filas(con, escenario["sesion_id"])

    assert len(filas) == 3
    assert [f["sku"] for f in filas] == ["A", "B", "C"]


def test_articulo_sin_contar(con, escenario):
    fila = tablero.filas(con, escenario["sesion_id"])[0]

    assert fila["ultimo_conteo"] is None
    assert fila["dif"] is None
    assert fila["estado"] == tablero.SIN_CONTAR
    assert fila["fecha"] is None


def test_conteos_del_mismo_sku_se_suman(con, escenario):
    contar(con, escenario, "A", 60000, "u-1")
    contar(con, escenario, "A", 40000, "u-2")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 100000
    assert fila["dif"] == 0
    assert fila["estado"] == tablero.CONSOLIDADO


def test_conteo_anulado_no_suma(con, escenario):
    contar(con, escenario, "A", 60000, "u-1")
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "A", "cantidad": 0,
        "timestamp_dispositivo": "2026-08-10T10:05:00Z", "anula_uuid": "u-1",
    })
    contar(con, escenario, "A", 100000, "u-3")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 100000


def test_diferencia_fuera_de_tolerancia(con, escenario):
    contar(con, escenario, "C", 5000, "u-1")  # sistema dice 10

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "C")

    assert fila["dif"] == -5000
    assert fila["estado"] == tablero.A_RECONTAR


def test_filtro_por_grupo(con, escenario):
    filas = tablero.filas(con, escenario["sesion_id"], {"grupo": "Bazar"})

    assert [f["sku"] for f in filas] == ["C"]


def test_filtro_por_estado(con, escenario):
    contar(con, escenario, "A", 100000, "u-1")

    filas = tablero.filas(con, escenario["sesion_id"], {"estado": tablero.SIN_CONTAR})

    assert [f["sku"] for f in filas] == ["B", "C"]


def test_filtro_por_texto_busca_en_sku_y_descripcion(con, escenario):
    filas = tablero.filas(con, escenario["sesion_id"], {"texto": "arand"})

    assert [f["sku"] for f in filas] == ["C"]


def test_resumen_cuenta_avance(con, escenario):
    contar(con, escenario, "A", 100000, "u-1")
    contar(con, escenario, "C", 5000, "u-2")

    resumen = tablero.resumen(con, escenario["sesion_id"])

    assert resumen["articulos"] == 3
    assert resumen["contados"] == 2
    assert resumen["sin_contar"] == 1
    assert resumen["consolidados"] == 1
    assert resumen["a_recontar"] == 1
    assert resumen["avance_pct"] == pytest.approx(66.7, abs=0.1)


def test_resumen_de_sesion_vacia_no_divide_por_cero(con):
    sesion_id = sesiones.crear(con, "Sin maestro")

    resumen = tablero.resumen(con, sesion_id)

    assert resumen["articulos"] == 0
    assert resumen["avance_pct"] == 0
