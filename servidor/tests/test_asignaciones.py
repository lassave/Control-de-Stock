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


def test_asignados_por_articulo(con, escenario):
    """Es la funcion compartida que usan tanto el tablero como el reparto."""
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    articulo_a = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]

    resultado = asignaciones.asignados_por_articulo(con, escenario["sesion_id"])

    assert resultado == {articulo_a: ["Juan"]}


def test_asignados_por_articulo_sin_pasada_devuelve_vacio(con):
    con.execute(
        "INSERT INTO sesion (nombre, fecha_creacion) VALUES ('Suelta', ?)",
        ("2026-08-17T10:00:00Z",),
    )
    sesion_id = con.execute("SELECT id FROM sesion WHERE nombre = 'Suelta'").fetchone()["id"]

    assert asignaciones.asignados_por_articulo(con, sesion_id) == {}


# --- de_operario_en_sesion trae la pasada activa, no siempre la general ----

def test_de_operario_en_sesion_devuelve_la_pasada_general_sin_recuento(con, escenario):
    asignaciones.reemplazar(
        con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"]
    )

    resultado = asignaciones.de_operario_en_sesion(
        con, escenario["sesion_id"], escenario["juan"]["id"]
    )

    assert resultado["pasada_id"] == escenario["pasada_id"]
    assert resultado["pasada_numero"] == 1
    assert resultado["pasada_etiqueta"] == "Conteo 1"
    assert resultado["es_parcial"] is False
    assert resultado["articulos_permitidos"] == []
    assert resultado["ubicaciones"] == ["Deposito A"]


def test_de_operario_en_sesion_devuelve_el_recuento_cuando_esta_asignado(con, escenario):
    from app.repos import pasada_item

    articulo_a = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-17T10:00:00Z"),
    )
    pasada_2 = cursor.lastrowid
    pasada_item.agregar(con, pasada_2, [articulo_a])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["Deposito A"])

    resultado = asignaciones.de_operario_en_sesion(
        con, escenario["sesion_id"], escenario["juan"]["id"]
    )

    assert resultado["pasada_id"] == pasada_2
    assert resultado["pasada_numero"] == 2
    assert resultado["pasada_etiqueta"] == "Conteo 2"
    assert resultado["es_parcial"] is True
    assert resultado["articulos_permitidos"] == [articulo_a]


# --- asignados_por_articulo y operarios_con_ubicaciones con recuentos ------

def test_asignados_por_articulo_con_recuento_muestra_los_dos(con, escenario):
    """Un articulo dentro del recuento suma el responsable general -toda la
    ubicacion- y el del recuento -ese SKU puntual-."""
    from app.repos import pasada_item

    maria = operarios.crear(con, "Maria")
    asignaciones.reemplazar(con, escenario["pasada_id"], maria["id"], ["Deposito A"])

    articulo_a = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-17T10:00:00Z"),
    )
    pasada_2 = cursor.lastrowid
    pasada_item.agregar(con, pasada_2, [articulo_a])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["Deposito A"])

    resultado = asignaciones.asignados_por_articulo(con, escenario["sesion_id"])

    assert resultado[articulo_a] == ["Juan", "Maria"]


def test_asignados_por_articulo_fuera_del_recuento_solo_el_general(con, escenario):
    """El SKU C (Deposito A, fuera del recuento) no recibe al asignado del
    recuento -que solo marco al SKU A-, solo al general."""
    from app.repos import pasada_item

    con.execute(
        "INSERT INTO articulo (sesion_id, id_orden, sku, descripcion, unidad, "
        "ubicacion, creado_en) VALUES (?, 3, 'C', 'Tuerca', 'UN', 'Deposito A', ?)",
        (escenario["sesion_id"], "2026-08-17T10:00:00Z"),
    )
    articulo_c = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'C'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]

    maria = operarios.crear(con, "Maria")
    asignaciones.reemplazar(con, escenario["pasada_id"], maria["id"], ["Deposito A"])

    articulo_a = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-17T10:00:00Z"),
    )
    pasada_2 = cursor.lastrowid
    pasada_item.agregar(con, pasada_2, [articulo_a])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["Deposito A"])

    resultado = asignaciones.asignados_por_articulo(con, escenario["sesion_id"])

    assert resultado.get(articulo_c, []) == ["Maria"]


def test_operarios_con_ubicaciones_usa_la_pasada_activa_de_cada_uno(con, escenario):
    from app.repos import pasada_item

    articulo_a = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-17T10:00:00Z"),
    )
    pasada_2 = cursor.lastrowid
    pasada_item.agregar(con, pasada_2, [articulo_a])
    asignaciones.reemplazar(con, pasada_2, escenario["juan"]["id"], ["Deposito B"])

    lista = asignaciones.operarios_con_ubicaciones(con)
    juan = next(o for o in lista if o["id"] == escenario["juan"]["id"])

    assert juan["ubicaciones_asignadas"] == ["Deposito B"]


def test_operarios_con_ubicaciones_ajeno_al_recuento_muestra_lo_general(con, escenario):
    """Con un recuento abierto, un operario que no esta asignado ahi tiene
    que seguir viendo lo que le toca en la pasada general, no una lista
    vacia por mirar la pasada equivocada."""
    from app.repos import pasada_item

    articulo_a = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? AND sku = 'A'",
        (escenario["sesion_id"],),
    ).fetchone()["id"]
    asignaciones.reemplazar(con, escenario["pasada_id"], escenario["juan"]["id"], ["Deposito A"])

    maria = operarios.crear(con, "Maria")
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (escenario["sesion_id"], "2026-08-17T10:00:00Z"),
    )
    pasada_2 = cursor.lastrowid
    pasada_item.agregar(con, pasada_2, [articulo_a])
    asignaciones.reemplazar(con, pasada_2, maria["id"], ["Deposito B"])
    # Juan no está en el recuento: sigue en la general con "Deposito A".

    lista = asignaciones.operarios_con_ubicaciones(con)
    juan = next(o for o in lista if o["id"] == escenario["juan"]["id"])

    assert juan["ubicaciones_asignadas"] == ["Deposito A"]
