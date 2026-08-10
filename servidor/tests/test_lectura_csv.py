import pytest

from app.servicios import lectura_csv


def test_lee_utf8_con_comas():
    contenido = "sku,descripcion\n10453,Tornillo\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["10453", "Tornillo"]]


def test_lee_punto_y_coma():
    contenido = "sku;descripcion\n10453;Tornillo\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["10453", "Tornillo"]]


def test_lee_cp1252_con_acentos():
    contenido = "sku;descripcion\n1;Cañería de bronce\n".encode("cp1252")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0][1] == "Cañería de bronce"


def test_lee_utf8_con_bom():
    contenido = "﻿sku,descripcion\n1,Tornillo\n".encode("utf-8")

    encabezados, _ = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]


def test_respeta_comas_dentro_de_comillas():
    contenido = 'sku,descripcion\n1,"Tornillo 3/8, hexagonal"\n'.encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0][1] == "Tornillo 3/8, hexagonal"


def test_ignora_filas_completamente_vacias():
    contenido = "sku,descripcion\n1,Tornillo\n\n2,Tuerca\n\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert len(filas) == 2


def test_completa_filas_con_menos_columnas():
    contenido = "sku,descripcion,grupo\n1,Tornillo\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0] == ["1", "Tornillo", ""]


def test_conserva_las_columnas_de_mas_en_vez_de_descartarlas():
    """Un campo de más delata un archivo mal armado: no se pierde en silencio."""
    contenido = "sku,descripcion\n1,Tornillo,SOBRA\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas[0] == ["1", "Tornillo", "SOBRA"]


def test_no_se_confunde_con_un_separador_dentro_de_comillas():
    """Contar caracteres fusionaría SKU y descripción en una sola columna."""
    contenido = 'sku,"descripcion; larga"\n1,Tornillo\n'.encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion; larga"]
    assert filas[0] == ["1", "Tornillo"]


def test_saltea_un_titulo_antes_del_encabezado():
    """Varios ERP anteponen el nombre del listado o la fecha de emisión."""
    contenido = (
        "Listado de stock al 10/08/2026\n"
        "sku;descripcion\n"
        "1;Tornillo\n"
        "2;Tuerca\n"
    ).encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert len(filas) == 2


def test_respeta_el_encabezado_aunque_las_filas_tengan_menos_columnas():
    """Elegir el encabezado por «ancho dominante» lo descartaba acá."""
    contenido = (
        "sku,descripcion,grupo\n"
        "1,Tornillo\n"
        "2,Tuerca\n"
        "3,Clavo\n"
    ).encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion", "grupo"]
    assert len(filas) == 3


def test_respeta_el_encabezado_aunque_las_filas_tengan_mas_columnas():
    contenido = (
        "sku,descripcion\n"
        "1,Tornillo,X\n"
        "2,Tuerca,Y\n"
        "3,Clavo,Z\n"
    ).encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert len(filas) == 3


def test_ignora_las_filas_de_relleno_que_deja_excel():
    """Excel suele dejar líneas con solo separadores o espacios al final."""
    contenido = "sku,descripcion\n1,Tornillo\n,\n,\n".encode("utf-8")

    _, filas = lectura_csv.leer(contenido)

    assert filas == [["1", "Tornillo"]]


def test_ignora_las_lineas_en_blanco_del_final():
    contenido = "sku,descripcion\n1,Tornillo\n   \n   \n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["1", "Tornillo"]]


def test_ignora_la_columna_vacia_que_deja_un_separador_final():
    contenido = "sku,descripcion,\n1,Tornillo,\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas[0][:2] == ["1", "Tornillo"]


def test_el_encabezado_es_la_primera_linea_con_contenido():
    """Una línea de relleno arriba se saltea igual que en cualquier otra parte."""
    contenido = ",,\nsku,descripcion\n1,Tornillo\n".encode("utf-8")

    encabezados, filas = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]
    assert filas == [["1", "Tornillo"]]


def test_rechaza_un_archivo_de_puro_relleno():
    contenido = ",,\n,,\n".encode("utf-8")

    with pytest.raises(ValueError, match="vacío"):
        lectura_csv.leer(contenido)


@pytest.mark.parametrize("texto, esperado", [
    ("sku;descripcion\n1;Tornillo", ";"),
    ("sku,descripcion\n1,Tornillo", ","),
    ("sku\tdescripcion\n1\tTornillo", "\t"),
    ("sku|descripcion\n1|Tornillo", "|"),
    ("una sola columna\nsin separadores", ","),
    ("", ","),
])
def test_detectar_separador(texto, esperado):
    assert lectura_csv.detectar_separador(texto) == esperado


@pytest.mark.parametrize("texto, codificacion, esperada", [
    ("Cañería", "utf-8", "utf-8-sig"),
    ("Cañería", "cp1252", "cp1252"),
    ("sin acentos", "ascii", "utf-8-sig"),
])
def test_detectar_codificacion(texto, codificacion, esperada):
    """UTF-8 se prueba primero: casi todo UTF-8 también decodifica como cp1252."""
    assert lectura_csv.detectar_codificacion(texto.encode(codificacion)) == esperada


def test_recorta_espacios_de_los_encabezados():
    contenido = " sku , descripcion \n1,Tornillo\n".encode("utf-8")

    encabezados, _ = lectura_csv.leer(contenido)

    assert encabezados == ["sku", "descripcion"]


def test_rechaza_archivo_vacio():
    with pytest.raises(ValueError, match="vacío"):
        lectura_csv.leer(b"")


def test_rechaza_encabezados_duplicados():
    contenido = "sku,sku\n1,2\n".encode("utf-8")

    with pytest.raises(ValueError, match="duplicada"):
        lectura_csv.leer(contenido)
