import pytest
from fastapi.testclient import TestClient

from app.main import crear_app


@pytest.fixture
def cliente(tmp_path):
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def sesion(cliente):
    respuesta = cliente.post("/api/sesiones", json={"nombre": "Cliente X"})
    return respuesta.json()


CSV_MAESTRO = (
    "sku,detalle,stock\n"
    "A,Tornillo,100\n"
    "B,Tuerca,50\n"
).encode("utf-8")


def importar(cliente, sesion_id):
    return cliente.post(
        f"/api/sesiones/{sesion_id}/maestro",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
        data={"mapeo": '{"sku": "sku", "descripcion": "detalle", "stock_sistema": "stock"}'},
    )


def test_crear_sesion(cliente):
    respuesta = cliente.post("/api/sesiones", json={"nombre": "Cliente X"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["nombre"] == "Cliente X"
    assert cuerpo["pasada"]["etiqueta"] == "Conteo 1"


def test_no_permite_dos_sesiones_abiertas(cliente, sesion):
    respuesta = cliente.post("/api/sesiones", json={"nombre": "Otra"})

    assert respuesta.status_code == 409
    assert "sesión abierta" in respuesta.json()["detail"]


def test_previsualizar_maestro(cliente):
    respuesta = cliente.post(
        "/api/maestro/previsualizar",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["encabezados"] == ["sku", "detalle", "stock"]


def test_importar_maestro(cliente, sesion):
    respuesta = importar(cliente, sesion["id"])

    assert respuesta.status_code == 200
    assert respuesta.json()["importados"] == 2


def test_mapeo_invalido_devuelve_400(cliente, sesion):
    respuesta = cliente.post(
        f"/api/sesiones/{sesion['id']}/maestro",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
        data={"mapeo": '{"sku": "sku"}'},
    )

    assert respuesta.status_code == 400


def test_tablero_devuelve_filas_y_resumen(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/tablero")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["filas"]) == 2
    assert cuerpo["resumen"]["articulos"] == 2


def test_tablero_acepta_filtros(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(
        f"/api/sesiones/{sesion['id']}/tablero", params={"texto": "torni"}
    )

    assert len(respuesta.json()["filas"]) == 1


def test_vincular_dispositivo(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/vincular", headers={"X-Token": operario["token_dispositivo"]}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["operario"]["nombre"] == "Juan"
    assert cuerpo["sesion"]["id"] == sesion["id"]


def test_vincular_con_token_invalido_devuelve_401(cliente, sesion):
    respuesta = cliente.post(
        "/api/dispositivo/vincular", headers={"X-Token": "inventado"}
    )

    assert respuesta.status_code == 401


def test_maestro_para_dispositivo_no_expone_stock(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(
        "/api/dispositivo/maestro", headers={"X-Token": operario["token_dispositivo"]}
    )

    assert respuesta.status_code == 200
    articulos = respuesta.json()["articulos"]
    assert len(articulos) == 2
    for articulo in articulos:
        assert "stock_sistema" not in articulo
        assert "costo_unitario" not in articulo


def test_enviar_conteos(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/conteos",
        headers={"X-Token": operario["token_dispositivo"]},
        json={"conteos": [
            {"uuid": "u-1", "codigo": "A", "cantidad": 98000,
             "timestamp_dispositivo": "2026-08-10T10:00:00Z"},
        ]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["registrados"] == 1


def test_reenviar_conteos_no_duplica(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cuerpo = {"conteos": [
        {"uuid": "u-1", "codigo": "A", "cantidad": 98000,
         "timestamp_dispositivo": "2026-08-10T10:00:00Z"},
    ]}
    encabezados = {"X-Token": operario["token_dispositivo"]}

    cliente.post("/api/dispositivo/conteos", headers=encabezados, json=cuerpo)
    respuesta = cliente.post("/api/dispositivo/conteos", headers=encabezados, json=cuerpo)

    assert respuesta.json()["duplicados"] == 1

    tablero = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()
    fila_a = next(f for f in tablero["filas"] if f["sku"] == "A")
    assert fila_a["ultimo_conteo"] == 98000


def test_exportar_resumen(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/exportar/resumen")

    assert respuesta.status_code == 200
    assert "text/csv" in respuesta.headers["content-type"]

    lineas = respuesta.text.lstrip("﻿").splitlines()
    assert lineas[0].startswith("id_orden;tipo;material;sku")
    assert len(lineas) == 3  # encabezado + dos artículos


def test_exportar_tipo_inexistente_devuelve_404(cliente, sesion):
    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/exportar/inventado")

    assert respuesta.status_code == 404


def test_exportar_respeta_los_filtros_del_tablero(cliente, sesion):
    """Se exporta lo que está en pantalla: si no, el archivo dice otra cosa."""
    importar(cliente, sesion["id"])

    respuesta = cliente.get(
        f"/api/sesiones/{sesion['id']}/exportar/resumen", params={"texto": "torni"}
    )

    lineas = respuesta.text.lstrip("﻿").splitlines()
    assert len(lineas) == 2  # encabezado + solo el tornillo


def test_exportar_lleva_bom_para_que_excel_lea_los_acentos(cliente, sesion):
    importar(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/exportar/resumen")

    assert respuesta.content.startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("pedido", [
    lambda cliente: cliente.get("/api/sesiones/999/tablero"),
    lambda cliente: cliente.get("/api/sesiones/999/resumen"),
    lambda cliente: cliente.get("/api/sesiones/999"),
    lambda cliente: cliente.post("/api/sesiones/999/cerrar"),
    lambda cliente: cliente.get("/api/sesiones/999/exportar/resumen"),
    lambda cliente: cliente.put(
        "/api/sesiones/999/tolerancia", json={"pct": 2.0, "min_abs": 1000}
    ),
])
def test_una_sesion_inexistente_devuelve_404_y_no_un_error_del_servidor(
    cliente, pedido
):
    """Un 500 le dice al panel «se rompió»; lo único que pasa es que no está."""
    assert pedido(cliente).status_code == 404


def test_tolerancia_mal_expresada_devuelve_400(cliente, sesion):
    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/tolerancia",
        json={"pct": 2.0, "min_abs": 1500.5},
    )

    assert respuesta.status_code == 400


def test_fijar_tolerancia_devuelve_la_sesion_actualizada(cliente, sesion):
    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/tolerancia",
        json={"pct": 5.0, "min_abs": 2000},
    )

    assert respuesta.json()["tolerancia_pct"] == 5.0
    assert respuesta.json()["tolerancia_min_abs"] == 2000


def test_mapeo_que_no_es_json_devuelve_400(cliente, sesion):
    respuesta = cliente.post(
        f"/api/sesiones/{sesion['id']}/maestro",
        files={"archivo": ("maestro.csv", CSV_MAESTRO, "text/csv")},
        data={"mapeo": "esto no es json"},
    )

    assert respuesta.status_code == 400


def test_operario_repetido_devuelve_409(cliente):
    cliente.post("/api/operarios", json={"nombre": "Juan"})

    respuesta = cliente.post("/api/operarios", json={"nombre": "Juan"})

    assert respuesta.status_code == 409


def test_el_dispositivo_sin_sesion_abierta_recibe_409(cliente):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/vincular", headers={"X-Token": operario["token_dispositivo"]}
    )

    assert respuesta.status_code == 409


def test_mis_conteos_devuelve_lo_que_mando_el_operario(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    encabezados = {"X-Token": operario["token_dispositivo"]}
    cliente.post("/api/dispositivo/conteos", headers=encabezados, json={"conteos": [
        {"uuid": "u-1", "codigo": "A", "cantidad": 98000,
         "timestamp_dispositivo": "2026-08-10T10:00:00Z"},
    ]})

    respuesta = cliente.get("/api/dispositivo/mis-conteos", headers=encabezados)

    assert respuesta.status_code == 200
    assert [c["uuid"] for c in respuesta.json()] == ["u-1"]


def test_el_maestro_del_dispositivo_trae_los_codigos_de_barras(cliente, sesion):
    """Sin códigos, el escáner del celular no encuentra ningún artículo."""
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    cuerpo = cliente.get(
        "/api/dispositivo/maestro", headers={"X-Token": operario["token_dispositivo"]}
    ).json()

    assert {c["codigo"] for c in cuerpo["codigos"]} == {"A", "B"}
    assert len(cuerpo["unidades"]) == 8


def test_listar_sesiones(cliente, sesion):
    respuesta = cliente.get("/api/sesiones")

    assert [s["id"] for s in respuesta.json()] == [sesion["id"]]


def test_cerrar_sesion_permite_abrir_otra(cliente, sesion):
    cliente.post(f"/api/sesiones/{sesion['id']}/cerrar")

    respuesta = cliente.post("/api/sesiones", json={"nombre": "Otra"})

    assert respuesta.status_code == 200


def test_el_qr_del_operario_se_sirve_como_svg(cliente):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(f"/api/operarios/{operario['id']}/qr")

    assert respuesta.status_code == 200
    assert "image/svg+xml" in respuesta.headers["content-type"]
    assert "<svg" in respuesta.text


def test_el_qr_no_apunta_a_loopback(cliente):
    """El celular tiene que llegar por la red, no a sí mismo."""
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(f"/api/operarios/{operario['id']}/qr")

    assert "127.0.0.1" not in respuesta.text


def test_el_qr_de_un_operario_inexistente_devuelve_404(cliente):
    assert cliente.get("/api/operarios/999/qr").status_code == 404


def alta_rapida(cliente, token, **datos):
    cuerpo = {
        "codigo": "999", "descripcion": "Caño de bronce",
        "unidad": "UN", "ubicacion": "P-9",
    }
    cuerpo.update(datos)
    return cliente.post(
        "/api/dispositivo/articulos", headers={"X-Token": token}, json=cuerpo
    )


def test_alta_rapida_crea_el_articulo(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"])

    assert respuesta.status_code == 200
    assert respuesta.json()["descripcion"] == "Caño de bronce"


def test_lo_dado_de_alta_se_puede_contar_enseguida(cliente, sesion):
    """Es el punto del alta rápida: destrabar el conteo, no anotar para después."""
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    encabezados = {"X-Token": operario["token_dispositivo"]}
    alta_rapida(cliente, operario["token_dispositivo"], codigo="7790001001234")

    respuesta = cliente.post("/api/dispositivo/conteos", headers=encabezados, json={
        "conteos": [{"uuid": "u-9", "codigo": "7790001001234", "cantidad": 3000,
                     "timestamp_dispositivo": "2026-08-11T10:00:00Z"}],
    })

    assert respuesta.json()["registrados"] == 1


def test_el_alta_rapida_no_expone_stock_ni_costo(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    cuerpo = alta_rapida(cliente, operario["token_dispositivo"]).json()

    assert "stock_sistema" not in cuerpo
    assert "costo_unitario" not in cuerpo


def test_el_alta_rapida_sin_token_devuelve_401(cliente, sesion):
    assert alta_rapida(cliente, "inventado").status_code == 401


def test_el_alta_rapida_con_datos_invalidos_devuelve_400(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"], descripcion="")

    assert respuesta.status_code == 400
    assert "descripción" in respuesta.json()["detail"]


def test_el_alta_rapida_aparece_en_el_tablero(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    alta_rapida(cliente, operario["token_dispositivo"])

    filas = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"]

    nuevo = next(f for f in filas if f["descripcion"] == "Caño de bronce")
    assert nuevo["origen"] == "alta_rapida"


APK_FALSO = b"PK\x03\x04 esto hace de APK en los tests"


def test_sin_apk_la_descarga_devuelve_404(cliente):
    assert cliente.get("/app.apk").status_code == 404


def test_sin_apk_la_instalacion_se_informa_como_no_disponible(cliente):
    """El panel no puede ofrecer una descarga que va a fallar."""
    respuesta = cliente.get("/api/instalacion")

    assert respuesta.status_code == 200
    assert respuesta.json()["disponible"] is False


def test_con_apk_presente_se_descarga(cliente, tmp_path, monkeypatch):
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)

    respuesta = cliente.get("/app.apk")

    assert respuesta.status_code == 200
    assert respuesta.content == APK_FALSO
    assert "android.package-archive" in respuesta.headers["content-type"]


def test_con_apk_presente_la_instalacion_informa_la_direccion_de_red(
    cliente, tmp_path, monkeypatch
):
    """El QR lo escanea un celular: 127.0.0.1 lo mandaría a sí mismo."""
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["disponible"] is True
    assert cuerpo["url"].endswith("/app.apk")
    assert "127.0.0.1" not in cuerpo["url"]


def test_el_qr_de_instalacion_es_svg(cliente, tmp_path, monkeypatch):
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)

    respuesta = cliente.get("/api/instalacion/qr")

    assert respuesta.status_code == 200
    assert "image/svg+xml" in respuesta.headers["content-type"]


def test_el_qr_de_instalacion_sin_apk_devuelve_404(cliente):
    assert cliente.get("/api/instalacion/qr").status_code == 404
