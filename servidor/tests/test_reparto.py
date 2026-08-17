"""La pestaña que contesta quién tiene qué y cómo viene.

Se prueba sin levantar el servidor: la lógica vive en el servicio.
"""

import pytest

from app.repos import asignaciones, conteos, operarios, sesiones
from app.servicios import importacion, reparto, tablero


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,ubic,stock\n"
        "A,Tornillo,Deposito A,100\n"
        "B,Tuerca,Deposito B,50\n"
        "C,Arandela,,10\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "ubicacion": "ubic",
        "stock_sistema": "stock",
    })
    pasada = sesiones.pasada_abierta(con, sesion_id)
    return {
        "sesion_id": sesion_id,
        "pasada_id": pasada["id"],
        "juan": operarios.crear(con, "Juan"),
        "maria": operarios.crear(con, "Maria"),
    }


def fila_de(filas, sku):
    return next(f for f in filas if f["sku"] == sku)


def contar(con, escenario, operario, sku, cantidad, uuid, anula=None):
    return conteos.registrar(con, escenario["sesion_id"], operario["id"], {
        "uuid": uuid,
        "codigo": sku,
        "cantidad": cantidad,
        "timestamp_dispositivo": "2026-08-16T10:00:00Z",
        "anula_uuid": anula,
    })


def test_muestra_a_quien_le_toca_cada_ubicacion(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    filas = reparto.filas(con, escenario["sesion_id"])

    assert fila_de(filas, "A")["asignado_a"] == ["Juan"]


def test_una_ubicacion_repartida_entre_dos_los_muestra_a_los_dos(con, escenario):
    """El panel permite asignarle la misma ubicación a más de una persona."""
    for quien in ("maria", "juan"):
        asignaciones.reemplazar(
            con, escenario["pasada_id"], escenario[quien]["id"], ["Deposito A"]
        )

    assert fila_de(reparto.filas(con, escenario["sesion_id"]), "A")["asignado_a"] == [
        "Juan", "Maria",
    ]


def test_una_ubicacion_que_nadie_tiene_sale_sin_dueno(con, escenario):
    """Es la fila que más sirve: avisa del pasillo que nadie va a contar."""
    filas = reparto.filas(con, escenario["sesion_id"])

    assert fila_de(filas, "A")["asignado_a"] == []


def test_un_articulo_sin_ubicacion_no_le_toca_a_nadie(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    assert fila_de(reparto.filas(con, escenario["sesion_id"]), "C")["asignado_a"] == []


def test_muestra_quien_conto(con, escenario):
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")

    assert fila_de(reparto.filas(con, escenario["sesion_id"]), "A")["contado_por"] == [
        "Juan",
    ]


def test_el_que_conto_tres_veces_aparece_una_sola(con, escenario):
    for numero in range(3):
        contar(con, escenario, escenario["juan"], "A", 10000, f"u{numero}")

    assert fila_de(reparto.filas(con, escenario["sesion_id"]), "A")["contado_por"] == [
        "Juan",
    ]


def test_dos_que_contaron_el_mismo_articulo_salen_los_dos(con, escenario):
    contar(con, escenario, escenario["maria"], "A", 10000, "u1")
    contar(con, escenario, escenario["juan"], "A", 20000, "u2")

    assert fila_de(reparto.filas(con, escenario["sesion_id"]), "A")["contado_por"] == [
        "Juan", "Maria",
    ]


def test_un_conteo_anulado_no_cuenta_ni_suma(con, escenario):
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")
    contar(con, escenario, escenario["juan"], "A", 0, "u2", anula="u1")

    fila = fila_de(reparto.filas(con, escenario["sesion_id"]), "A")

    assert fila["contado_por"] == []
    assert fila["contado"] is None


def test_el_total_y_el_estado_son_los_mismos_que_los_del_tablero(con, escenario):
    """Si derivan, las dos pestañas dicen cosas distintas del mismo SKU."""
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")
    contar(con, escenario, escenario["maria"], "A", 15000, "u2")

    del_reparto = fila_de(reparto.filas(con, escenario["sesion_id"]), "A")
    del_tablero = fila_de(tablero.filas(con, escenario["sesion_id"]), "A")

    assert del_reparto["contado"] == del_tablero["ultimo_conteo"] == 55000
    assert del_reparto["estado"] == del_tablero["estado"]


def test_no_expone_el_stock_ni_el_costo(con, escenario):
    """Esta pestaña se exporta, y el CSV de «quién hizo qué» circula."""
    fila = fila_de(reparto.filas(con, escenario["sesion_id"]), "A")

    assert "stock_sistema" not in fila
    assert "costo_unitario" not in fila


def test_arrastra_los_filtros_del_tablero(con, escenario):
    filas = reparto.filas(con, escenario["sesion_id"], {"ubicacion": "Deposito B"})

    assert [f["sku"] for f in filas] == ["B"]


def test_las_asignaciones_salen_de_la_ultima_pasada_aunque_este_cerrada(con, escenario):
    """Quién hizo qué se mira sobre todo cuando el inventario ya cerró."""
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    sesiones.cerrar(con, escenario["sesion_id"])

    assert fila_de(reparto.filas(con, escenario["sesion_id"]), "A")["asignado_a"] == [
        "Juan",
    ]
