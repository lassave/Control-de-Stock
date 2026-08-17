import pytest

from app.repos import asignaciones, operarios, sesiones
from app.servicios import importacion


@pytest.fixture
def escenario(con):
    sesion_id = sesiones.crear(con, "Cliente X")
    contenido = (
        "sku,detalle,ubic\n"
        "A,Tornillo,Deposito A\n"
        "B,Tuerca,Deposito B\n"
    ).encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "ubicacion": "ubic",
    })
    juan = operarios.crear(con, "Juan")
    pasada = sesiones.pasada_abierta(con, sesion_id)
    return {"sesion_id": sesion_id, "juan": juan, "pasada_id": pasada["id"]}


def test_reemplazar_guarda_las_ubicaciones(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"],
        ["Deposito A", "Deposito B"],
    )

    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == ["Deposito A", "Deposito B"]


def test_reemplazar_borra_lo_anterior(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito B"]
    )

    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == ["Deposito B"]


def test_sin_asignar_devuelve_vacio(con, escenario):
    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == []


def test_reemplazar_por_vacio_deja_sin_asignacion(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )
    asignaciones.reemplazar(con, escenario["pasada_id"], escenario["juan"]["id"], [])

    assert asignaciones.de_operario(
        con, escenario["pasada_id"], escenario["juan"]["id"]
    ) == []


def test_una_pasada_nueva_arranca_sin_asignaciones(con, escenario):
    """Un reconteo es justamente para que otra persona revise un sector."""
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-16T10:00:00Z"),
    )
    pasada_2_id = cursor.lastrowid

    assert asignaciones.de_operario(con, pasada_2_id, escenario["juan"]["id"]) == []


def test_ubicaciones_distintas_del_maestro(con, escenario):
    assert asignaciones.ubicaciones_distintas(con, escenario["sesion_id"]) == [
        "Deposito A", "Deposito B",
    ]


def test_ubicaciones_distintas_ignora_articulos_sin_ubicacion(con):
    sesion_id = sesiones.crear(con, "Cliente Y")
    contenido = "sku,detalle\nA,Tornillo\n".encode("utf-8")
    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert asignaciones.ubicaciones_distintas(con, sesion_id) == []


def test_operarios_con_ubicaciones_sin_sesion_abierta(con):
    """Sin sesión abierta no hay pasada a la cual asignar nada."""
    operarios.crear(con, "Juan")

    lista = asignaciones.operarios_con_ubicaciones(con)

    assert lista[0]["ubicaciones_asignadas"] == []


def test_operarios_con_ubicaciones_de_la_pasada_abierta(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    lista = asignaciones.operarios_con_ubicaciones(con)
    juan = next(o for o in lista if o["id"] == escenario["juan"]["id"])

    assert juan["ubicaciones_asignadas"] == ["Deposito A"]


def test_operarios_con_ubicaciones_sin_pasada_abierta_no_rompe(con, escenario):
    """Una sesión abierta cuyo conteo se cerró: hoy esto sale como 500.

    Es inalcanzable desde el panel —crear y cerrar mueven sesión y pasada
    juntas—, pero el reconteo lo va a abrir, y el radio de la falla es un
    endpoint global. Sin asignaciones que mostrar, lista vacía.
    """
    con.execute(
        "UPDATE pasada SET estado = 'cerrada' WHERE sesion_id = ?",
        (escenario["sesion_id"],),
    )

    lista = asignaciones.operarios_con_ubicaciones(con)

    assert lista[0]["ubicaciones_asignadas"] == []
