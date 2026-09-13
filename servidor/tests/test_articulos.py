import pytest

from app.repos import articulos, conteos, operarios, proyectos


@pytest.fixture
def escenario(con):
    proyecto_id = proyectos.crear(con, "Cliente X")
    juan = operarios.crear(con, "Juan")
    return {"proyecto_id": proyecto_id, "juan": juan}


def crear(con, escenario, **datos):
    completo = {
        "codigo": "999",
        "descripcion": "Caño de bronce",
        "unidad": "UN",
        "ubicacion": "P-9",
    }
    completo.update(datos)
    return articulos.crear_alta_rapida(
        con, escenario["proyecto_id"], escenario["juan"]["id"], completo
    )


def test_crea_el_articulo_con_origen_alta_rapida(con, escenario):
    articulo = crear(con, escenario)

    fila = con.execute(
        "SELECT origen, creado_por, descripcion, ubicacion FROM articulo WHERE id = ?",
        (articulo["id"],),
    ).fetchone()
    assert fila["origen"] == "alta_rapida"
    assert fila["creado_por"] == "Juan"
    assert fila["descripcion"] == "Caño de bronce"
    assert fila["ubicacion"] == "P-9"


def test_el_sku_es_el_codigo_escaneado(con, escenario):
    articulo = crear(con, escenario, codigo="7790001001234")

    assert articulo["sku"] == "7790001001234"


def test_el_codigo_queda_asociado_y_el_escaneo_siguiente_lo_encuentra(con, escenario):
    """Sin esto, el mismo producto se daría de alta una vez por escaneo."""
    crear(con, escenario, codigo="7790001001234")

    encontrado = conteos.buscar_por_codigo(
        con, escenario["proyecto_id"], "7790001001234"
    )
    assert encontrado["descripcion"] == "Caño de bronce"


def test_sin_codigo_genera_un_sku_correlativo(con, escenario):
    """Un producto sin etiqueta legible igual tiene que poder contarse."""
    primero = crear(con, escenario, codigo="")
    segundo = crear(con, escenario, codigo="")

    assert primero["sku"] == "AR-1"
    assert segundo["sku"] == "AR-2"


def test_el_sku_generado_queda_asociado_como_codigo(con, escenario):
    """Sin esto el artículo existe pero no se puede contar nunca.

    El conteo resuelve el artículo por `codigo_barras`; un alta sin etiqueta
    que no asocie su propio SKU deja cero filas ahí, y el conteo del operario
    se rechaza como «código desconocido» sin posibilidad de reintento.
    """
    articulo = crear(con, escenario, codigo="")

    encontrado = conteos.buscar_por_codigo(con, escenario["proyecto_id"], articulo["sku"])
    assert encontrado is not None
    assert encontrado["id"] == articulo["id"]


def test_el_sku_generado_no_choca_con_uno_del_maestro(con, escenario):
    """El maestro puede traer SKUs con la misma forma que los generados.

    Contar cuántos hay no dice cuál está libre: el choque cae como error del
    servidor y el operario se queda sin poder dar de alta.
    """
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, 'AR-3', 'Del maestro', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["proyecto_id"],),
    )
    con.commit()

    generados = [crear(con, escenario, codigo="")["sku"] for _ in range(3)]

    assert "AR-3" not in generados
    assert len(set(generados)) == 3


def test_el_sku_generado_sigue_al_mayor_existente(con, escenario):
    """«Correlativo» quiere decir sin huecos y sin marcha atrás.

    Contando cuántos hay, con un AR-3 del maestro salen AR-2, AR-4, AR-5: la
    numeración que el operario ve en la planilla saltea y va para atrás.
    """
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, 'AR-3', 'Del maestro', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["proyecto_id"],),
    )
    con.commit()

    generados = [crear(con, escenario, codigo="")["sku"] for _ in range(3)]

    assert generados == ["AR-4", "AR-5", "AR-6"]


def test_un_codigo_que_ya_es_sku_devuelve_el_articulo_existente(con, escenario):
    """El maestro pudo traer un código de barras propio distinto del SKU.

    Crear un duplicado violaría la unicidad de SKU por proyecto y partiría el
    conteo de un mismo producto en dos filas del tablero.
    """
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, 'A-100', 'Tornillo', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["proyecto_id"],),
    )
    con.commit()

    articulo = crear(con, escenario, codigo="A-100", descripcion="Otra cosa")

    assert articulo["sku"] == "A-100"
    assert articulo["descripcion"] == "Tornillo"  # no se pisa el maestro
    cuantos = con.execute(
        "SELECT COUNT(*) AS n FROM articulo WHERE proyecto_id = ?",
        (escenario["proyecto_id"],),
    ).fetchone()["n"]
    assert cuantos == 1
    assert conteos.buscar_por_codigo(con, escenario["proyecto_id"], "A-100") is not None


def test_el_alta_nueva_avisa_que_creo_el_articulo(con, escenario):
    """Sin este campo la app no puede distinguir un alta de un «ya estaba»."""
    articulo = crear(con, escenario)

    assert articulo["creado"] is True


def test_el_alta_de_un_codigo_ya_dado_de_alta_avisa_que_ya_existia(con, escenario):
    crear(con, escenario, codigo="7790001001234")

    segundo = crear(con, escenario, codigo="7790001001234", descripcion="Otra cosa")

    assert segundo["creado"] is False


def test_el_codigo_que_es_sku_del_maestro_avisa_que_ya_existia(con, escenario):
    """El operario escribe «Caño de bronce» y le vuelve «Tornillo».

    Está bien que no se pise el maestro, pero la pantalla tiene que poder
    decir «ese código ya estaba», y para eso hace falta saberlo sin adivinar.
    """
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 1, 'A-100', 'Tornillo', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["proyecto_id"],),
    )
    con.commit()

    articulo = crear(con, escenario, codigo="A-100")

    assert articulo["creado"] is False
    assert articulo["descripcion"] == "Tornillo"


def test_el_id_orden_queda_por_encima_del_mayor_existente(con, escenario):
    """Comparte criterio con la importación: el orden define el recorrido."""
    con.execute(
        "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
        "stock_sistema, creado_en) VALUES (?, 57, 'A-100', 'Tornillo', 'UN', 0, "
        "'2026-08-11T00:00:00Z')",
        (escenario["proyecto_id"],),
    )
    con.commit()

    articulo = crear(con, escenario)

    assert articulo["id_orden"] == 58


def test_no_devuelve_stock_ni_costo(con, escenario):
    """Conteo a ciegas: el dato no puede llegar al dispositivo."""
    articulo = crear(con, escenario)

    assert "stock_sistema" not in articulo
    assert "costo_unitario" not in articulo


def test_rechaza_una_descripcion_vacia(con, escenario):
    with pytest.raises(ValueError, match="descripción"):
        crear(con, escenario, descripcion="   ")


def test_rechaza_una_descripcion_que_no_es_texto(con, escenario):
    """El cuerpo llega del JSON del celular: puede venir cualquier cosa.

    El mensaje distingue el tipo equivocado de la falta: con «necesita una
    descripción», el operario que escribió una se queda mirando la pantalla
    sin entender qué le reclama.
    """
    with pytest.raises(ValueError, match="descripción.*texto"):
        crear(con, escenario, descripcion=123)


def test_rechaza_un_codigo_que_no_es_texto(con, escenario):
    """Un EAN serializado como número JSON es lo natural, y no puede perderse.

    Descartarlo en silencio daría de alta el artículo sin código asociado: el
    escaneo siguiente de la misma etiqueta no lo encontraría y crearía otro, y
    así uno por escaneo.
    """
    with pytest.raises(ValueError, match="código.*texto"):
        crear(con, escenario, codigo=7790001001234)


def test_rechaza_un_cuerpo_que_no_es_un_objeto(con, escenario):
    """Una lista o un texto sueltos explotarían en `.get` como AttributeError.

    El conteo ya se defiende igual y con el motivo en castellano: la asimetría
    confunde a quien escribe el cliente y el error sale como falla del
    servidor, que hace pensar que el pedido estaba bien.
    """
    with pytest.raises(ValueError, match="datos del artículo"):
        articulos.crear_alta_rapida(
            con, escenario["proyecto_id"], escenario["juan"]["id"], ["a", "b"]
        )


def test_rechaza_una_unidad_que_no_existe(con, escenario):
    """La clave foránea lo rechazaría con un mensaje que no dice nada."""
    with pytest.raises(ValueError, match="unidad"):
        crear(con, escenario, unidad="CAJA")


def test_la_ubicacion_es_opcional(con, escenario):
    articulo = crear(con, escenario, ubicacion="")

    assert articulo["ubicacion"] is None


def test_dos_altas_del_mismo_codigo_no_duplican(con, escenario):
    """Dos operarios pueden escanear la misma etiqueta desconocida a la vez."""
    primero = crear(con, escenario, codigo="7790001001234")
    segundo = crear(con, escenario, codigo="7790001001234")

    assert primero["id"] == segundo["id"]


def test_el_alta_que_pierde_la_carrera_devuelve_la_del_otro(con, escenario, monkeypatch):
    """El otro operario da de alta el mismo código entre la búsqueda y el INSERT.

    El choque sale como IntegrityError, que no es ValueError: el endpoint no lo
    atrapa y el operario ve un error del servidor, aunque el artículo ya existe
    y el reintento andaría. Sin idempotencia real la app no puede reintentar.
    """
    original = articulos.operarios.obtener

    def se_adelanta_otro_operario(conexion, operario_id):
        monkeypatch.setattr(articulos.operarios, "obtener", original)
        cursor = conexion.execute(
            "INSERT INTO articulo (proyecto_id, id_orden, sku, descripcion, unidad, "
            "stock_sistema, creado_en) VALUES (?, 1, '999', 'Del otro operario', "
            "'UN', 0, '2026-08-11T00:00:00Z')",
            (escenario["proyecto_id"],),
        )
        conexion.execute(
            "INSERT INTO codigo_barras (articulo_id, codigo) VALUES (?, '999')",
            (cursor.lastrowid,),
        )
        conexion.commit()
        return original(conexion, operario_id)

    monkeypatch.setattr(articulos.operarios, "obtener", se_adelanta_otro_operario)

    articulo = crear(con, escenario, codigo="999")

    assert articulo["descripcion"] == "Del otro operario"
    cuantos = con.execute(
        "SELECT COUNT(*) AS n FROM articulo WHERE proyecto_id = ?",
        (escenario["proyecto_id"],),
    ).fetchone()["n"]
    assert cuantos == 1
