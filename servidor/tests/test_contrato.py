"""El contrato que la app Android consume.

Los archivos de `celular/contrato/` son la referencia contra la que se
prueba la app. Estos tests **ejercen el servidor de verdad** y comparan lo
que devuelve contra esos archivos: si alguien renombra un campo, rompe acá
y en la app a la vez, en la PC, en vez de fallar en el depósito.

Comparar el archivo contra sí mismo no serviría de nada: los dos lados
leerían el mismo texto congelado y el servidor podría derivar libremente.
"""

import json
from pathlib import Path

import pytest

CONTRATO = Path(__file__).resolve().parent.parent.parent / "celular" / "contrato"

ARCHIVOS = [
    "vinculacion", "maestro", "conteos-respuesta", "alta-rapida",
    "mis-ubicaciones", "operarios", "identificacion",
]

CSV = (
    "sku,descripcion,unidad,ubicacion,stock\n"
    "7790001001234,Fideos guisero 500g,UN,P-1,50\n"
    "7790002005678,Aceite girasol 900ml,UN,P-2,30\n"
).encode("utf-8")


def leer(nombre):
    return json.loads((CONTRATO / f"{nombre}.json").read_text(encoding="utf-8"))


def forma(valor, ruta=""):
    """El conjunto de rutas de claves, sin los valores.

    Compara la estructura y no el contenido: los identificadores y las
    fechas cambian en cada corrida, pero el contrato es la forma.
    """
    claves = set()
    if isinstance(valor, dict):
        for clave, adentro in valor.items():
            claves.add(f"{ruta}.{clave}")
            claves |= forma(adentro, f"{ruta}.{clave}")
    elif isinstance(valor, list):
        for adentro in valor[:1]:
            claves |= forma(adentro, f"{ruta}[]")
    return claves


@pytest.fixture(scope="module")
def vivo(tmp_path_factory):
    """Las respuestas de un servidor real, repitiendo lo que hace capturar.py."""
    from fastapi.testclient import TestClient

    from app.main import crear_app

    ruta = tmp_path_factory.mktemp("contrato") / "contrato.db"
    app = crear_app(str(ruta))
    respuestas = {}

    with TestClient(app) as c:
        from tests.conftest import loguear
        loguear(c)

        proyecto = c.post("/api/proyectos", json={"nombre": "Contrato"}).json()
        c.post(
            f"/api/proyectos/{proyecto['id']}/maestro",
            files={"archivo": ("m.csv", CSV, "text/csv")},
            data={"mapeo": json.dumps({
                "sku": "sku", "descripcion": "descripcion",
                "unidad": "unidad", "ubicacion": "ubicacion",
                "stock_sistema": "stock",
            })},
        )
        operario = c.post("/api/operarios", json={"nombre": "Contrato"}).json()
        cab = {"X-Token": operario["token_dispositivo"]}

        respuestas["vinculacion"] = c.post(
            "/api/dispositivo/vincular", headers=cab
        ).json()
        respuestas["operarios"] = c.get(
            "/api/dispositivo/operarios", headers=cab
        ).json()
        respuestas["identificacion"] = c.post(
            "/api/dispositivo/identificar", headers=cab, json={"nombre": "Contrato"},
        ).json()
        respuestas["maestro"] = c.get(
            "/api/dispositivo/maestro", headers=cab
        ).json()
        respuestas["conteos-respuesta"] = c.post(
            "/api/dispositivo/conteos", headers=cab, json=leer("conteos-pedido"),
        ).json()
        respuestas["alta-rapida"] = c.post(
            "/api/dispositivo/articulos", headers=cab,
            json={"codigo": "7790009999999", "descripcion": "Sin etiqueta",
                  "unidad": "UN", "ubicacion": "P-9"},
        ).json()

        # Hay que repartirle algo antes de preguntar, igual que en
        # capturar.py: sin asignación la respuesta viene con la lista vacía
        # y no fija ningún nombre de campo.
        c.put(
            f"/api/proyectos/{proyecto['id']}/operarios/{operario['id']}/asignacion",
            json={"ubicaciones": ["P-1"]},
        )
        respuestas["mis-ubicaciones"] = c.get(
            "/api/dispositivo/mis-ubicaciones", headers=cab
        ).json()

    return respuestas


def test_los_archivos_del_contrato_existen():
    """Sin ellos, la app se prueba contra nada."""
    for nombre in ARCHIVOS + ["conteos-pedido"]:
        assert (CONTRATO / f"{nombre}.json").exists(), f"falta {nombre}.json"


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_el_servidor_sigue_cumpliendo_el_contrato(vivo, nombre):
    """Lo que el servidor devuelve hoy tiene la forma que la app espera.

    Es el test que sostiene toda la app: sin él, el servidor puede cambiar
    un nombre de campo y nadie se entera hasta el depósito.
    """
    del_archivo = forma(leer(nombre))
    del_servidor = forma(vivo[nombre])

    assert del_servidor == del_archivo, (
        f"«{nombre}» cambió. Falta en el servidor: "
        f"{sorted(del_archivo - del_servidor)}. Nuevo en el servidor: "
        f"{sorted(del_servidor - del_archivo)}. "
        f"Si el cambio es a propósito, volvé a capturar con "
        f"celular/contrato/capturar.py y ajustá los tipos de Kotlin."
    )


def test_el_servidor_acepta_el_pedido_de_conteos_tal_como_lo_manda_la_app(vivo):
    """La mitad saliente del contrato: los nombres que la app escribe.

    Un typo en «timestamp_dispositivo» o en «ubicacion_real» compila del
    lado Kotlin y hace que el servidor rechace cada conteo del lote.
    """
    assert vivo["conteos-respuesta"]["registrados"] == 1


def test_el_maestro_no_expone_stock_ni_costo(vivo):
    """Conteo a ciegas: el dato no debe existir en el celular."""
    for articulo in vivo["maestro"]["articulos"]:
        assert "stock_sistema" not in articulo
        assert "costo_unitario" not in articulo


def test_la_vinculacion_trae_operario_proyecto_y_pasada():
    datos = leer("vinculacion")

    assert set(datos) == {"operario", "proyecto", "pasada"}
    assert set(datos["operario"]) == {"id", "nombre"}
    assert set(datos["proyecto"]) == {"id", "nombre"}
    assert "etiqueta" in datos["pasada"]
    assert "numero" in datos["pasada"]


def test_el_maestro_trae_articulos_codigos_y_unidades():
    datos = leer("maestro")

    assert set(datos) == {"proyecto_id", "articulos", "codigos", "unidades"}
    assert set(datos["articulos"][0]) == {
        "id", "id_orden", "tipo", "material", "sku", "descripcion",
        "grupo", "ubicacion", "unidad", "origen",
    }
    assert set(datos["codigos"][0]) == {"codigo", "articulo_id"}
    assert set(datos["unidades"][0]) == {"codigo", "nombre", "admite_decimales"}


def test_mis_ubicaciones_viene_envuelto_y_no_como_lista_pelada():
    """`forma()` no ve adentro de una lista de textos.

    Una respuesta que fuera `["P-1"]` daría el conjunto vacío: el archivo no
    fijaría nada y el test de contrato pasaría con cualquier cosa. Envuelta
    en un objeto, al menos la clave queda clavada.
    """
    datos = leer("mis-ubicaciones")

    assert set(datos) == {
        "pasada_id", "pasada_numero", "pasada_etiqueta", "es_parcial",
        "articulos_permitidos", "ubicaciones",
    }
    assert isinstance(datos["ubicaciones"], list)
    assert datos["ubicaciones"], "capturalo con una ubicación asignada"


def test_la_respuesta_de_conteos_distingue_lo_reintentable(vivo):
    """El celular necesita saber si conservar el evento o descartarlo."""
    datos = vivo["conteos-respuesta"]

    assert set(datos) == {"registrados", "duplicados", "rechazados"}
    assert datos["registrados"] == 1
    rechazado = datos["rechazados"][0]
    assert set(rechazado) == {"uuid", "motivo", "reintentable"}
    assert rechazado["reintentable"] is False


def test_el_alta_rapida_dice_si_creo_o_ya_estaba(vivo):
    datos = vivo["alta-rapida"]

    assert datos["creado"] is True
    assert "stock_sistema" not in datos
    assert "costo_unitario" not in datos
    assert datos["sku"] == "7790009999999"


def test_operarios_trae_id_nombre_y_tiene_pin():
    datos = leer("operarios")

    assert set(datos) == {"operarios"}
    assert set(datos["operarios"][0]) == {"id", "nombre", "tiene_pin"}


def test_identificacion_trae_lo_mismo_que_la_vinculacion_mas_el_token():
    datos = leer("identificacion")

    assert set(datos) == {"operario", "proyecto", "pasada", "token"}
    assert set(datos["operario"]) == {"id", "nombre"}
    assert set(datos["proyecto"]) == {"id", "nombre"}
