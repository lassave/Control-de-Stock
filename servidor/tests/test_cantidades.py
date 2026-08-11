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


@pytest.mark.parametrize("texto", [
    "", "   ", "abc", "1,2,3", None,
    ".", ",", "-", "-,",           # separador suelto: celda rota, no cero
    "1 2",                         # dos números pegados, no doce mil
    "1.23.456",                    # grupos de miles mal formados
    "inf", "-inf", "nan", "snan",  # Decimal los acepta; acá no son cantidades
    "1e3", "1_000",                # notación que ningún ERP exporta
])
def test_a_milesimas_rechaza_invalidos(texto):
    with pytest.raises(ValueError):
        cantidades.a_milesimas(texto)


@pytest.mark.parametrize("texto, esperado", [
    ("1.234.567", 1234567000),
    ("1,234,567", 1234567000),
])
def test_acepta_miles_agrupados_sin_decimales(texto, esperado):
    """«1.234.567» es la forma normal de escribir un número grande acá."""
    assert cantidades.a_milesimas(texto) == esperado


@pytest.mark.parametrize("texto, esperado", [
    ("1,2345", 1235),   # redondea para arriba
    ("1,2344", 1234),   # redondea para abajo
    ("0,0005", 1),      # medio hacia arriba
    ("0,0004", 0),
])
def test_redondea_los_decimales_sobrantes(texto, esperado):
    """Truncar sesgaría todas las cantidades a la baja de forma sistemática."""
    assert cantidades.a_milesimas(texto) == esperado


def test_siempre_devuelve_enteros():
    """La base rechaza cualquier float: la columna tiene CHECK typeof integer."""
    for texto in ["24", "3,5", "1.234,56", "0,0005"]:
        assert isinstance(cantidades.a_milesimas(texto), int)
        assert isinstance(cantidades.a_centavos(texto), int)


@pytest.mark.parametrize("texto", ["", "abc", ".", "12,,5"])
def test_a_centavos_rechaza_invalidos(texto):
    with pytest.raises(ValueError):
        cantidades.a_centavos(texto)


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


@pytest.mark.parametrize("centavos, esperado", [
    (12345, "123,45"),
    (1000, "10,00"),
    (5, "0,05"),
    (0, "0,00"),
    (-5000, "-50,00"),
    (None, ""),
])
def test_a_texto_importe(centavos, esperado):
    """La plata sale siempre con dos decimales: '10' a secas se lee como diez pesos."""
    assert cantidades.a_texto_importe(centavos) == esperado
