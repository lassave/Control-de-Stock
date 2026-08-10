import pytest

from app.repos import sesiones
from app.servicios import importacion


@pytest.fixture
def sesion_id(con):
    return sesiones.crear(con, "Cliente X")


def test_previsualizar_devuelve_encabezados_y_muestra():
    contenido = "sku,detalle\n1,Tornillo\n2,Tuerca\n3,Arandela\n".encode("utf-8")

    vista = importacion.previsualizar(contenido, cantidad=2)

    assert vista["encabezados"] == ["sku", "detalle"]
    assert len(vista["filas"]) == 2


def test_importa_articulos_con_mapeo(con, sesion_id):
    # Punto y coma como separador: es lo habitual cuando las cantidades
    # llevan coma decimal, como el 12,5 de la segunda fila.
    contenido = (
        "Codigo;Detalle;Rubro;Deposito;UM;Existencia\n"
        "10453;Tornillo hex 3/8;Buloneria;A-03-2;UN;48\n"
        "10454;Cañeria bronce;Sanitarios;B-01;MT;12,5\n"
    ).encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "Codigo",
        "descripcion": "Detalle",
        "grupo": "Rubro",
        "ubicacion": "Deposito",
        "unidad": "UM",
        "stock_sistema": "Existencia",
    })

    assert resultado["importados"] == 2

    filas = con.execute(
        "SELECT * FROM articulo WHERE sesion_id = ? ORDER BY id_orden", (sesion_id,)
    ).fetchall()
    assert filas[0]["sku"] == "10453"
    assert filas[0]["descripcion"] == "Tornillo hex 3/8"
    assert filas[0]["grupo"] == "Buloneria"
    assert filas[0]["ubicacion"] == "A-03-2"
    assert filas[0]["unidad"] == "UN"
    assert filas[0]["stock_sistema"] == 48000
    assert filas[1]["stock_sistema"] == 12500


def test_genera_id_orden_si_no_viene(con, sesion_id):
    contenido = "sku,detalle\nA,Uno\nB,Dos\nC,Tres\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    ordenes = [
        fila["id_orden"]
        for fila in con.execute(
            "SELECT id_orden FROM articulo WHERE sesion_id = ? ORDER BY id", (sesion_id,)
        )
    ]
    assert ordenes == [1, 2, 3]


def test_respeta_id_orden_del_archivo(con, sesion_id):
    contenido = "nro,sku,detalle\n100,A,Uno\n200,B,Dos\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "id_orden": "nro", "sku": "sku", "descripcion": "detalle",
    })

    ordenes = [
        fila["id_orden"]
        for fila in con.execute(
            "SELECT id_orden FROM articulo WHERE sesion_id = ? ORDER BY id", (sesion_id,)
        )
    ]
    assert ordenes == [100, 200]


def test_crea_codigo_de_barras_cuando_se_mapea(con, sesion_id):
    contenido = "sku,detalle,ean\n10453,Tornillo,7791234567890\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "codigo_barras": "ean",
    })

    assert resultado["codigos"] == 1
    fila = con.execute("SELECT codigo FROM codigo_barras").fetchone()
    assert fila["codigo"] == "7791234567890"


def test_usa_el_sku_como_codigo_si_no_se_mapea(con, sesion_id):
    contenido = "sku,detalle\n10453,Tornillo\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    fila = con.execute("SELECT codigo FROM codigo_barras").fetchone()
    assert fila["codigo"] == "10453"


def test_unidad_por_defecto_cuando_no_se_mapea(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    importacion.importar(
        con, sesion_id, contenido,
        {"sku": "sku", "descripcion": "detalle"},
        unidad_por_defecto="KG",
    )

    fila = con.execute("SELECT unidad FROM articulo").fetchone()
    assert fila["unidad"] == "KG"


def test_importa_costo_en_centavos(con, sesion_id):
    contenido = "sku,detalle,costo\n1,Tornillo,\"1.234,56\"\n".encode("utf-8")

    importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "costo_unitario": "costo",
    })

    fila = con.execute("SELECT costo_unitario FROM articulo").fetchone()
    assert fila["costo_unitario"] == 123456


def test_rechaza_mapeo_sin_campos_obligatorios(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="descripcion"):
        importacion.importar(con, sesion_id, contenido, {"sku": "sku"})


def test_rechaza_mapeo_a_columna_inexistente(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="no existe en el archivo"):
        importacion.importar(con, sesion_id, contenido, {
            "sku": "sku", "descripcion": "detalle", "grupo": "Rubro",
        })


def test_saltea_filas_sin_sku(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n,Sin codigo\n2,Tuerca\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert len(resultado["descartadas"]) == 1


def test_una_unidad_desconocida_no_frena_la_importacion(con, sesion_id):
    """La clave foránea abortaría el archivo entero: se ataja antes."""
    contenido = "sku,detalle,um\n1,Tornillo,UN\n2,Tuerca,CAJA\n3,Clavo,KG\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "unidad": "um",
    })

    assert resultado["importados"] == 3
    assert any("CAJA" in a["motivo"] for a in resultado["advertencias"])

    unidades = {
        fila["sku"]: fila["unidad"]
        for fila in con.execute("SELECT sku, unidad FROM articulo")
    }
    assert unidades == {"1": "UN", "2": "UN", "3": "KG"}


def test_un_sku_repetido_se_cuenta_una_sola_vez(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n1,Tornillo corregido\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 1
    assert any("más de una vez" in a["motivo"] for a in resultado["advertencias"])

    fila = con.execute("SELECT descripcion FROM articulo").fetchone()
    assert fila["descripcion"] == "Tornillo corregido"


def test_rechaza_una_unidad_por_defecto_inexistente(con, sesion_id):
    contenido = "sku,detalle\n1,Tornillo\n".encode("utf-8")

    with pytest.raises(ValueError, match="no existe"):
        importacion.importar(
            con, sesion_id, contenido,
            {"sku": "sku", "descripcion": "detalle"},
            unidad_por_defecto="INVENTADA",
        )


def test_reporta_las_filas_con_columnas_de_mas(con, sesion_id):
    """Una columna de más suele delatar una comilla sin cerrar."""
    contenido = "sku,detalle\n1,Tornillo\n2,Tuerca,SOBRA\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle",
    })

    assert resultado["importados"] == 2
    assert any("más columnas" in a["motivo"] for a in resultado["advertencias"])


def test_stock_invalido_queda_en_cero_y_se_reporta(con, sesion_id):
    contenido = "sku,detalle,stock\n1,Tornillo,mucho\n".encode("utf-8")

    resultado = importacion.importar(con, sesion_id, contenido, {
        "sku": "sku", "descripcion": "detalle", "stock_sistema": "stock",
    })

    fila = con.execute("SELECT stock_sistema FROM articulo").fetchone()
    assert fila["stock_sistema"] == 0
    assert len(resultado["advertencias"]) == 1
