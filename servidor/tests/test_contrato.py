"""El contrato que la app Android consume.

Los archivos de `celular/contrato/` son la referencia contra la que se
prueba la app. Estos tests verifican que el servidor los siga cumpliendo:
si alguien renombra un campo, rompe acá y en la app a la vez, en la PC, en
vez de fallar en el depósito.
"""

import json
from pathlib import Path

import pytest

CONTRATO = Path(__file__).resolve().parent.parent.parent / "celular" / "contrato"


def leer(nombre):
    return json.loads((CONTRATO / f"{nombre}.json").read_text(encoding="utf-8"))


@pytest.fixture
def sesion_con_maestro(cliente_contrato):
    """Un servidor real con una sesión, un maestro y un operario."""
    return cliente_contrato


def test_los_archivos_del_contrato_existen():
    """Sin ellos, la app se prueba contra nada."""
    for nombre in ["vinculacion", "maestro", "conteos-respuesta", "alta-rapida"]:
        assert (CONTRATO / f"{nombre}.json").exists(), f"falta {nombre}.json"


def test_la_vinculacion_trae_operario_sesion_y_pasada():
    datos = leer("vinculacion")

    assert set(datos) == {"operario", "sesion", "pasada"}
    assert set(datos["operario"]) == {"id", "nombre"}
    assert set(datos["sesion"]) == {"id", "nombre"}
    assert "etiqueta" in datos["pasada"]
    assert "numero" in datos["pasada"]


def test_el_maestro_no_expone_stock_ni_costo():
    """Conteo a ciegas: el dato no debe existir en el celular."""
    datos = leer("maestro")

    for articulo in datos["articulos"]:
        assert "stock_sistema" not in articulo
        assert "costo_unitario" not in articulo


def test_el_maestro_trae_articulos_codigos_y_unidades():
    datos = leer("maestro")

    assert set(datos) == {"sesion_id", "articulos", "codigos", "unidades"}
    assert set(datos["articulos"][0]) == {
        "id", "id_orden", "tipo", "material", "sku", "descripcion",
        "grupo", "ubicacion", "unidad",
    }
    assert set(datos["codigos"][0]) == {"codigo", "articulo_id"}
    assert set(datos["unidades"][0]) == {"codigo", "nombre", "admite_decimales"}


def test_la_respuesta_de_conteos_distingue_lo_reintentable():
    """El celular necesita saber si conservar el evento o descartarlo."""
    datos = leer("conteos-respuesta")

    assert set(datos) == {"registrados", "duplicados", "rechazados"}
    assert datos["registrados"] == 1
    rechazado = datos["rechazados"][0]
    assert set(rechazado) == {"uuid", "motivo", "reintentable"}
    assert rechazado["reintentable"] is False


def test_el_alta_rapida_dice_si_creo_o_ya_estaba():
    datos = leer("alta-rapida")

    assert datos["creado"] is True
    assert "stock_sistema" not in datos
    assert "costo_unitario" not in datos
    assert datos["sku"] == "7790009999999"
