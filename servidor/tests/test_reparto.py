"""La pestaña que contesta quién tiene qué y cómo viene.

Se prueba sin levantar el servidor: la lógica vive en el servicio.
"""

import pytest

from app.repos import asignaciones, conteos, operarios, proyectos
from app.servicios import importacion, reparto, tablero


@pytest.fixture
def escenario(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,ubic,stock\n"
        "A,Tornillo,Deposito A,100\n"
        "B,Tuerca,Deposito B,50\n"
        "C,Arandela,,10\n"
    ).encode("utf-8")
    importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "ubicacion": "ubic",
        "stock_sistema": "stock",
    })
    pasada = proyectos.pasada_abierta(con, proyecto_id)
    return {
        "proyecto_id": proyecto_id,
        "pasada_id": pasada["id"],
        "juan": operarios.crear(con, "Juan"),
        "maria": operarios.crear(con, "Maria"),
    }


def fila_de(filas, sku):
    return next(f for f in filas if f["sku"] == sku)


def contar(con, escenario, operario, sku, cantidad, uuid, anula=None):
    return conteos.registrar(con, escenario["proyecto_id"], operario["id"], {
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

    filas = reparto.filas(con, escenario["proyecto_id"])

    assert fila_de(filas, "A")["asignado_a"] == ["Juan"]


def test_una_ubicacion_repartida_entre_dos_los_muestra_a_los_dos(con, escenario):
    """El panel permite asignarle la misma ubicación a más de una persona."""
    for quien in ("maria", "juan"):
        asignaciones.reemplazar(
            con, escenario["pasada_id"], escenario[quien]["id"], ["Deposito A"]
        )

    assert fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")["asignado_a"] == [
        "Juan", "Maria",
    ]


def test_una_ubicacion_que_nadie_tiene_sale_sin_dueno(con, escenario):
    """Es la fila que más sirve: avisa del pasillo que nadie va a contar."""
    filas = reparto.filas(con, escenario["proyecto_id"])

    assert fila_de(filas, "A")["asignado_a"] == []


def test_un_articulo_sin_ubicacion_no_le_toca_a_nadie(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    assert fila_de(reparto.filas(con, escenario["proyecto_id"]), "C")["asignado_a"] == []


def test_muestra_quien_conto(con, escenario):
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")

    assert fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")["contado_por"] == [
        "Juan",
    ]


def test_el_que_conto_tres_veces_aparece_una_sola(con, escenario):
    for numero in range(3):
        contar(con, escenario, escenario["juan"], "A", 10000, f"u{numero}")

    assert fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")["contado_por"] == [
        "Juan",
    ]


def test_dos_que_contaron_el_mismo_articulo_salen_los_dos(con, escenario):
    contar(con, escenario, escenario["maria"], "A", 10000, "u1")
    contar(con, escenario, escenario["juan"], "A", 20000, "u2")

    assert fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")["contado_por"] == [
        "Juan", "Maria",
    ]


def test_un_conteo_anulado_no_cuenta_ni_suma(con, escenario):
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")
    contar(con, escenario, escenario["juan"], "A", 0, "u2", anula="u1")

    fila = fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")

    assert fila["contado_por"] == []
    assert fila["contado"] is None


def test_el_total_y_el_estado_son_los_mismos_que_los_del_tablero(con, escenario):
    """Si derivan, las dos pestañas dicen cosas distintas del mismo SKU."""
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")
    contar(con, escenario, escenario["maria"], "A", 15000, "u2")

    del_reparto = fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")
    del_tablero = fila_de(tablero.filas(con, escenario["proyecto_id"]), "A")

    assert del_reparto["contado"] == del_tablero["ultimo_conteo"] == 55000
    assert del_reparto["estado"] == del_tablero["estado"]


def test_no_expone_el_stock_ni_el_costo(con, escenario):
    """Esta pestaña se exporta, y el CSV de «quién hizo qué» circula."""
    fila = fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")

    assert "stock_sistema" not in fila
    assert "costo_unitario" not in fila


def test_arrastra_los_filtros_del_tablero(con, escenario):
    filas = reparto.filas(con, escenario["proyecto_id"], {"ubicacion": "Deposito B"})

    assert [f["sku"] for f in filas] == ["B"]


def test_las_asignaciones_salen_de_la_ultima_pasada_aunque_este_cerrada(con, escenario):
    """Quién hizo qué se mira sobre todo cuando el inventario ya cerró."""
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    proyectos.cerrar(con, escenario["proyecto_id"])

    assert fila_de(reparto.filas(con, escenario["proyecto_id"]), "A")["asignado_a"] == [
        "Juan",
    ]


# --- El resumen por operario --------------------------------------------------

def operario_de(resultado, nombre):
    return next(o for o in resultado if o["operario"] == nombre)


def test_avance_por_operario_cuenta_lo_propio(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A", "Deposito B"]
    )
    contar(con, escenario, escenario["juan"], "A", 40000, "u1")

    juan = operario_de(reparto.avance_por_operario(con, escenario["proyecto_id"]), "Juan")

    assert juan["total"] == 2
    assert juan["contados"] == 1
    assert juan["sin_contar"] == 1
    assert juan["avance_pct"] == 50.0
    assert juan["ubicaciones"] == ["Deposito A", "Deposito B"]


def test_avance_por_operario_no_cuenta_lo_que_conto_otro(con, escenario):
    """«Contado» es lo que hizo el propio operario, no cualquiera."""
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    contar(con, escenario, escenario["maria"], "A", 40000, "u1")

    juan = operario_de(reparto.avance_por_operario(con, escenario["proyecto_id"]), "Juan")

    assert juan["contados"] == 0
    assert juan["avance_pct"] == 0.0


def test_avance_por_operario_omite_a_quien_no_tiene_nada_asignado(con, escenario):
    resultado = reparto.avance_por_operario(con, escenario["proyecto_id"])

    assert [o["operario"] for o in resultado] == []


def test_avance_por_operario_trae_el_detalle_ordenado(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    juan = operario_de(reparto.avance_por_operario(con, escenario["proyecto_id"]), "Juan")

    assert [d["sku"] for d in juan["detalle"]] == ["A"]
    assert juan["detalle"][0]["contado"] is False


def test_avance_por_operario_respeta_los_filtros(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A", "Deposito B"]
    )

    juan = operario_de(
        reparto.avance_por_operario(con, escenario["proyecto_id"], {"ubicacion": "Deposito A"}),
        "Juan",
    )

    assert juan["total"] == 1
    assert [d["sku"] for d in juan["detalle"]] == ["A"]


# --- El avance de un recuento puntual ------------------------------------------

def test_avance_de_pasada_cuenta_lo_marcado_para_ese_recuento(con, escenario):
    articulo_a = fila_de(tablero.filas(con, escenario["proyecto_id"]), "A")["id"]
    recuento = proyectos.abrir_pasada(con, escenario["proyecto_id"], [articulo_a])
    asignaciones.reemplazar(
        con, recuento["id"], escenario["juan"]["id"], ["Deposito A"]
    )

    resultado = reparto.avance_de_pasada(con, escenario["proyecto_id"], recuento["id"])

    juan = operario_de(resultado, "Juan")
    assert juan["total"] == 1
    assert juan["contados"] == 0
    assert juan["sin_contar"] == 1
    assert juan["avance_pct"] == 0.0
    assert juan["ubicaciones"] == ["Deposito A"]


def test_avance_de_pasada_refleja_lo_contado_en_ese_recuento(con, escenario):
    articulo_a = fila_de(tablero.filas(con, escenario["proyecto_id"]), "A")["id"]
    recuento = proyectos.abrir_pasada(con, escenario["proyecto_id"], [articulo_a])
    asignaciones.reemplazar(
        con, recuento["id"], escenario["juan"]["id"], ["Deposito A"]
    )
    contar(con, escenario, escenario["juan"], "A", 45000, "u1")

    juan = operario_de(
        reparto.avance_de_pasada(con, escenario["proyecto_id"], recuento["id"]), "Juan"
    )

    assert juan["contados"] == 1
    assert juan["avance_pct"] == 100.0


def test_avance_de_pasada_no_mezcla_lo_contado_en_otra_pasada(con, escenario):
    """Contar en el Conteo 1 no hace avanzar el recuento: son etapas distintas."""
    articulo_a = fila_de(tablero.filas(con, escenario["proyecto_id"]), "A")["id"]
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    contar(con, escenario, escenario["juan"], "A", 45000, "u1")

    recuento = proyectos.abrir_pasada(con, escenario["proyecto_id"], [articulo_a])
    asignaciones.reemplazar(
        con, recuento["id"], escenario["maria"]["id"], ["Deposito A"]
    )

    maria = operario_de(
        reparto.avance_de_pasada(con, escenario["proyecto_id"], recuento["id"]), "Maria"
    )

    assert maria["contados"] == 0


def test_avance_de_pasada_omite_a_quien_no_esta_asignado_ahi(con, escenario):
    articulo_a = fila_de(tablero.filas(con, escenario["proyecto_id"]), "A")["id"]
    recuento = proyectos.abrir_pasada(con, escenario["proyecto_id"], [articulo_a])

    resultado = reparto.avance_de_pasada(con, escenario["proyecto_id"], recuento["id"])

    assert resultado == []


def test_avance_de_pasada_con_pasada_inexistente_da_error(con, escenario):
    with pytest.raises(ValueError):
        reparto.avance_de_pasada(con, escenario["proyecto_id"], 999)
