import pytest

from app.repos import proyectos
from app.servicios import importacion


@pytest.fixture
def proyecto_id(con):
    return proyectos.crear(con, "Cliente X")


def test_previsualizar_devuelve_encabezados_y_muestra():
    contenido = "sku,detalle\n1,Tornillo\n2,Tuerca\n3,Arandela\n".encode("utf-8")

    vista = importacion.previsualizar(contenido, cantidad=2)

    assert vista["encabezados"] == ["sku", "detalle"]
    assert len(vista["filas"]) == 2


def test_importa_articulos_con_mapeo(con, proyecto_id):
    # Punto y coma como separador: es lo habitual cuando las cantidades
    # llevan coma decimal, como el 12,5 de la segunda fila.
    contenido = (
        "Codigo;Detalle;Rubro;Deposito;UM;Existencia\n"
        "10453;Tornillo hex 3/8;Buloneria;A-03-2;UN;48\n"
        "10454;Cañeria bronce;Sanitarios;B-01;MT;12,5\n"
    ).encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "Codigo",
        "descripcion": "Detalle",
        "grupo": "Rubro",
        "ubicacion": "Deposito",
        "unidad": "UM",
        "stock_sistema": "Existencia",
    })

    assert resultado["importados"] == 2

    filas = con.execute(
        "SELECT * FROM articulo WHERE proyecto_id = ? ORDER BY id_orden", (proyecto_id,)
    ).fetchall()
    assert filas[0]["sku"] == "10453"
    assert filas[0]["descripcion"] == "Tornillo hex 3/8"
    assert filas[0]["grupo"] == "Buloneria"
    assert filas[0]["ubicacion"] == "A-03-2"
    assert filas[0]["unidad"] == "UN"
    assert filas[0]["stock_sistema"] == 48000
    assert filas[1]["stock_sistema"] == 12500


def test_genera_id_orden_si_no_viene(con, proyecto_id):
    contenido = "sku,detalle\nA,Uno\nB,Dos\nC,Tres\n".encode("utf-8")

    importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    ordenes = [
        fila["id_orden"]
        for fila in con.execute(
            "SELECT id_orden FROM articulo WHERE proyecto_id = ? ORDER BY id", (proyecto_id,)
        )
    ]
    assert ordenes == [1, 2, 3]


def test_respeta_id_orden_del_archivo(con, proyecto_id):
    contenido = "nro,sku,detalle\n100,A,Uno\n200,B,Dos\n".encode("utf-8")

    importacion.importar(con, proyecto_id, contenido, {
        "id_orden": "nro", "sku": "sku", "descripcion": "detalle",
    })

    ordenes = [
        fila["id_orden"]
        for fila in con.execute(
            "SELECT id_orden FROM articulo WHERE proyecto_id = ? ORDER BY id", (proyecto_id,)
        )
    ]
    assert ordenes == [100, 200]


def test_crea_codigo_de_barras_cuando_se_mapea(con, proyecto_id):
    contenido = "sku,detalle,ean\n10453,Tornillo,7791234567890\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "codigo_barras": "ean",
    })

    assert resultado["codigos"] == 1
    fila = con.execute("SELECT codigo FROM codigo_barras").fetchone()
    assert fila["codigo"] == "7791234567890"


def test_usa_el_sku_como_codigo_si_no_se_mapea(con, proyecto_id):
    contenido = "sku,detalle\n10453,Tornillo\n".encode("utf-8")

    importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    fila = con.execute("SELECT codigo FROM codigo_barras").fetchone()
    assert fila["codigo"] == "10453"


def test_unidad_por_defecto_cuando_no_se_mapea(con, proyecto_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    importacion.importar(
        con, proyecto_id, contenido,
        {"sku": "sku", "descripcion": "detalle"},
        unidad_por_defecto="KG",
    )

    fila = con.execute("SELECT unidad FROM articulo").fetchone()
    assert fila["unidad"] == "KG"


def test_importa_costo_en_centavos(con, proyecto_id):
    contenido = "sku,detalle,costo\n1,Tornillo,\"1.234,56\"\n".encode("utf-8")

    importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "costo_unitario": "costo",
    })

    fila = con.execute("SELECT costo_unitario FROM articulo").fetchone()
    assert fila["costo_unitario"] == 123456


def test_rechaza_mapeo_sin_campos_obligatorios(con, proyecto_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="descripcion"):
        importacion.importar(con, proyecto_id, contenido, {"sku": "sku"})


def test_rechaza_mapeo_a_columna_inexistente(con, proyecto_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="no existe en el archivo"):
        importacion.importar(con, proyecto_id, contenido, {
            "sku": "sku", "descripcion": "detalle", "grupo": "Rubro",
        })


def test_saltea_filas_sin_sku(con, proyecto_id):
    contenido = "sku,detalle\n1,Tornillo\n,Sin codigo\n2,Tuerca\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert len(resultado["descartadas"]) == 1


def test_una_unidad_desconocida_no_frena_la_importacion(con, proyecto_id):
    """La clave foránea abortaría el archivo entero: se ataja antes."""
    contenido = "sku,detalle,um\n1,Tornillo,UN\n2,Tuerca,CAJA\n3,Clavo,KG\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "unidad": "um",
    })

    assert resultado["importados"] == 3
    assert any("CAJA" in a["motivo"] for a in resultado["advertencias"])

    unidades = {
        fila["sku"]: fila["unidad"]
        for fila in con.execute("SELECT sku, unidad FROM articulo")
    }
    assert unidades == {"1": "UN", "2": "UN", "3": "KG"}


def test_un_sku_repetido_se_cuenta_una_sola_vez(con, proyecto_id):
    contenido = "sku,detalle\n1,Tornillo\n1,Tornillo corregido\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 1
    assert any("más de una vez" in a["motivo"] for a in resultado["advertencias"])

    fila = con.execute("SELECT descripcion FROM articulo").fetchone()
    assert fila["descripcion"] == "Tornillo corregido"


def test_un_sku_repetido_no_desordena_la_numeracion(con, proyecto_id):
    """id_orden define el recorrido: dos artículos no pueden compartir número."""
    contenido = "sku,detalle\nA,Uno\nB,Dos\nA,Uno otra vez\nC,Tres\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 3

    ordenes = {
        fila["sku"]: fila["id_orden"]
        for fila in con.execute("SELECT sku, id_orden FROM articulo")
    }
    assert ordenes == {"A": 1, "B": 2, "C": 3}


def test_un_numero_de_orden_ilegible_no_pisa_a_los_del_archivo(con, proyecto_id):
    """El fallback tiene que quedar por encima de todos los números escritos."""
    contenido = "nro,sku,detalle\nxx,A,Uno\n1,B,Dos\n2,C,Tres\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "id_orden": "nro", "sku": "sku", "descripcion": "detalle",
    })

    ordenes = {
        fila["sku"]: fila["id_orden"]
        for fila in con.execute("SELECT sku, id_orden FROM articulo")
    }
    assert ordenes["B"] == 1
    assert ordenes["C"] == 2
    assert ordenes["A"] == 3  # por encima del mayor que trae el archivo
    assert len(set(ordenes.values())) == 3
    assert any("Número de orden inválido" in a["motivo"]
               for a in resultado["advertencias"])


def test_avisa_si_el_archivo_repite_un_numero_de_orden(con, proyecto_id):
    contenido = "nro,sku,detalle\n1,A,Uno\n1,B,Dos\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "id_orden": "nro", "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert any("ya lo usa otro artículo" in a["motivo"]
               for a in resultado["advertencias"])


def test_avisa_cuando_falta_la_descripcion(con, proyecto_id):
    contenido = "sku,detalle\n1,\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 1
    assert any("Sin descripción" in a["motivo"] for a in resultado["advertencias"])

    fila = con.execute("SELECT descripcion FROM articulo").fetchone()
    assert fila["descripcion"] == "1"


def test_reimportar_actualiza_sin_duplicar(con, proyecto_id):
    primero = "sku,detalle,stock\nA,Tornillo,10\nB,Tuerca,5\n".encode("utf-8")
    segundo = "sku,detalle,stock\nA,Tornillo hex,12\nB,Tuerca,5\n".encode("utf-8")
    mapeo = {"sku": "sku", "descripcion": "detalle", "stock_sistema": "stock"}

    importacion.importar(con, proyecto_id, primero, mapeo)
    importacion.importar(con, proyecto_id, segundo, mapeo)

    filas = list(con.execute(
        "SELECT sku, descripcion, stock_sistema FROM articulo ORDER BY id_orden"
    ))
    assert len(filas) == 2
    assert filas[0]["descripcion"] == "Tornillo hex"
    assert filas[0]["stock_sistema"] == 12000

    codigos = con.execute("SELECT COUNT(*) AS n FROM codigo_barras").fetchone()["n"]
    assert codigos == 2


def test_rechaza_una_unidad_por_defecto_inexistente(con, proyecto_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="no existe"):
        importacion.importar(
            con, proyecto_id, contenido,
            {"sku": "sku", "descripcion": "detalle"},
            unidad_por_defecto="INVENTADA",
        )


def test_reporta_las_filas_con_columnas_de_mas(con, proyecto_id):
    """Una columna de más suele delatar una comilla sin cerrar."""
    contenido = "sku,detalle\n1,Tornillo\n2,Tuerca,SOBRA\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert any("más columnas" in a["motivo"] for a in resultado["advertencias"])


def test_stock_invalido_queda_en_cero_y_se_reporta(con, proyecto_id):
    contenido = "sku,detalle,stock\n1,Tornillo,mucho\n".encode("utf-8")

    resultado = importacion.importar(con, proyecto_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "stock_sistema": "stock",
    })

    fila = con.execute("SELECT stock_sistema FROM articulo").fetchone()
    assert fila["stock_sistema"] == 0
    assert len(resultado["advertencias"]) == 1
