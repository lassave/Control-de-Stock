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
