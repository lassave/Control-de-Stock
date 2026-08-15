import pytest

from app.repos import asignaciones, conteos, operarios, sesiones
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
    (2000,   24000, "dígito faltante"),    # 2 en vez de 24
    (2400000, 24000, "dígito de más"),     # 2400 en vez de 24
    (12000,  120000, "dígito faltante"),   # 12 en vez de 120
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
    # La fila que anula lleva cantidad propia a propósito: con cero, un error
    # que sumara la anulación en vez de descartarla pasaría inadvertido.
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "A", "cantidad": 7000,
        "timestamp_dispositivo": "2026-08-10T10:05:00Z", "anula_uuid": "u-1",
    })
    contar(con, escenario, "A", 100000, "u-3")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 100000


def abrir_conteo_2(con, sesion_id):
    """Cierra la pasada abierta y abre la siguiente.

    Los conteos sucesivos se implementan en un plan posterior, pero el cálculo
    del valor vigente ya tiene que estar bien: si no, el defecto aparece recién
    cuando alguien manda a recontar, y para entonces el número está mal en la
    reunión con el cliente.
    """
    con.execute(
        "UPDATE pasada SET estado = 'cerrada', fecha_cierre = ? "
        "WHERE sesion_id = ? AND estado = 'abierta'",
        ("2026-08-10T12:00:00Z", sesion_id),
    )
    con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion_id, "2026-08-10T12:00:00Z"),
    )
    con.commit()


def test_el_conteo_nuevo_reemplaza_al_anterior_no_se_suma(con, escenario):
    """48 en el Conteo 1 y 50 en el Conteo 2 dan 50, no 98."""
    contar(con, escenario, "A", 48000, "u-1")
    abrir_conteo_2(con, escenario["sesion_id"])
    contar(con, escenario, "A", 50000, "u-2")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 50000


def test_dentro_de_una_pasada_los_conteos_siguen_sumando(con, escenario):
    contar(con, escenario, "A", 30000, "u-1")
    abrir_conteo_2(con, escenario["sesion_id"])
    contar(con, escenario, "A", 20000, "u-2")
    contar(con, escenario, "A", 30000, "u-3")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 50000


def test_un_articulo_fuera_del_reconteo_conserva_su_valor(con, escenario):
    contar(con, escenario, "B", 45000, "u-1")
    abrir_conteo_2(con, escenario["sesion_id"])
    contar(con, escenario, "A", 100000, "u-2")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "B")

    assert fila["ultimo_conteo"] == 45000


def test_anular_el_reconteo_devuelve_el_valor_de_la_pasada_anterior(con, escenario):
    """No puede caer a SIN CONTAR: el conteo de la pasada 1 sigue siendo válido."""
    contar(con, escenario, "A", 48000, "u-1")
    abrir_conteo_2(con, escenario["sesion_id"])
    contar(con, escenario, "A", 50000, "u-2")
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-3", "codigo": "A", "cantidad": 0,
        "timestamp_dispositivo": "2026-08-10T13:00:00Z", "anula_uuid": "u-2",
    })

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ultimo_conteo"] == 48000
    assert fila["estado"] == tablero.A_RECONTAR


def test_la_ubicacion_real_es_la_ultima_correccion(con, escenario):
    """Concatenarlas todas dejaba la celda ilegible y mostraba las anuladas."""
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-1", "codigo": "A", "cantidad": 40000,
        "timestamp_dispositivo": "2026-08-10T10:00:00Z", "ubicacion_real": "P-9",
    })
    conteos.registrar(con, escenario["sesion_id"], escenario["juan"]["id"], {
        "uuid": "u-2", "codigo": "A", "cantidad": 60000,
        "timestamp_dispositivo": "2026-08-10T11:00:00Z", "ubicacion_real": "P-7",
    })

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")

    assert fila["ubicacion_real"] == "P-7"


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


@pytest.fixture
def escenario_con_costo(con):
    """Un maestro con costo, para lo que el escenario común no cubre."""
    sesion_id = sesiones.crear(con, "Cliente con costos")
    contenido = (
        "sku,detalle,stock,costo\n"
        "A,Tornillo,100,25\n"
        "B,Tuerca,50,10\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
        "stock_sistema": "stock", "costo_unitario": "costo",
    })
    juan = operarios.crear(con, "Juan")
    return {"sesion_id": sesion_id, "juan": juan}


def test_valoriza_la_diferencia(con, escenario_con_costo):
    """Milésimas por centavos: el resultado queda en centavos."""
    contar(con, escenario_con_costo, "A", 98000, "u-1")  # faltan 2 a $25

    fila = next(
        f for f in tablero.filas(con, escenario_con_costo["sesion_id"])
        if f["sku"] == "A"
    )

    assert fila["dif"] == -2000
    assert fila["dif_valorizada"] == -5000  # -$50,00 en centavos


def test_el_resumen_separa_desvio_neto_y_absoluto(con, escenario_con_costo):
    """El neto puede dar cerca de cero con el depósito hecho un desastre."""
    contar(con, escenario_con_costo, "A", 98000, "u-1")   # -2 x $25 = -$50
    contar(con, escenario_con_costo, "B", 55000, "u-2")   # +5 x $10 = +$50

    resumen = tablero.resumen(con, escenario_con_costo["sesion_id"])

    assert resumen["desvio_neto"] == 0
    assert resumen["desvio_absoluto"] == 10000  # $100,00


def test_sin_costo_no_hay_valorizacion(con, escenario):
    contar(con, escenario, "C", 5000, "u-1")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "C")

    assert fila["dif"] == -5000
    assert fila["dif_valorizada"] is None


def test_resumen_de_sesion_vacia_no_divide_por_cero(con):
    sesion_id = sesiones.crear(con, "Sin maestro")

    resumen = tablero.resumen(con, sesion_id)

    assert resumen["articulos"] == 0
    assert resumen["avance_pct"] == 0


def test_marca_fuera_de_asignacion(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(con, pasada["id"], escenario["juan"]["id"], ["P-2"])

    contar(con, escenario, "A", 24000, "u-1")  # A está en P-1, Juan tiene P-2

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")
    assert fila["fuera_asignacion"] is True


def test_sin_marca_cuando_coincide_la_asignacion(con, escenario):
    pasada = sesiones.pasada_abierta(con, escenario["sesion_id"])
    asignaciones.reemplazar(con, pasada["id"], escenario["juan"]["id"], ["P-1"])

    contar(con, escenario, "A", 24000, "u-1")

    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "A")
    assert fila["fuera_asignacion"] is False


def test_sin_contar_no_se_marca(con, escenario):
    fila = next(f for f in tablero.filas(con, escenario["sesion_id"]) if f["sku"] == "B")
    assert fila["fuera_asignacion"] is False
