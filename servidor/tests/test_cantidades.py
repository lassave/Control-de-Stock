import pytest

from app import cantidades


@pytest.mark.parametrize("texto, esperado", [
    ("24", 24000),
    ("0", 0),
    ("3,5", 3500),
    ("3.5", 3500),
    ("0,001", 1),
    ("1.234,56", 1234560),
    ("1,234.56", 1234560),
    ("  12  ", 12000),
    ("-4", -4000),
])
def test_a_milesimas(texto, esperado):
    assert cantidades.a_milesimas(texto) == esperado


@pytest.mark.parametrize("texto", ["", "abc", "1,2,3", None])
def test_a_milesimas_rechaza_invalidos(texto):
    with pytest.raises(ValueError):
        cantidades.a_milesimas(texto)


@pytest.mark.parametrize("milesimas, esperado", [
    (24000, "24"),
    (0, "0"),
    (3500, "3,5"),
    (1, "0,001"),
    (1234560, "1234,56"),
    (-4000, "-4"),
])
def test_a_texto(milesimas, esperado):
    assert cantidades.a_texto(milesimas) == esperado


def test_ida_y_vuelta_no_pierde_precision():
    for texto in ["24", "3,5", "0,001", "999999,999"]:
        assert cantidades.a_texto(cantidades.a_milesimas(texto)) == texto


def test_suma_de_decimales_es_exacta():
    total = sum(cantidades.a_milesimas("0,1") for _ in range(10))
    assert total == cantidades.a_milesimas("1")


def test_a_centavos():
    assert cantidades.a_centavos("1.234,56") == 123456
    assert cantidades.a_centavos("10") == 1000
