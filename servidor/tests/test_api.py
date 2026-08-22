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


CSV_CON_UBICACION = (
    "sku,detalle,ubic\n"
    "A,Tornillo,Deposito A\n"
    "B,Tuerca,Deposito B\n"
).encode("utf-8")


def importar_con_ubicacion(cliente, sesion_id):
    return cliente.post(
        f"/api/sesiones/{sesion_id}/maestro",
        files={"archivo": ("maestro.csv", CSV_CON_UBICACION, "text/csv")},
        data={"mapeo": '{"sku": "sku", "descripcion": "detalle", "ubicacion": "ubic"}'},
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


def test_lo_dado_de_alta_sin_codigo_tambien_se_puede_contar(cliente, sesion):
    """El caso que motiva el SKU correlativo: producto sin etiqueta legible.

    Si el SKU generado no queda como código, el conteo vuelve rechazado y
    —peor— como no reintentable: la app lo descarta y el dato se pierde.
    """
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    encabezados = {"X-Token": operario["token_dispositivo"]}
    alta = alta_rapida(cliente, operario["token_dispositivo"], codigo="").json()

    respuesta = cliente.post("/api/dispositivo/conteos", headers=encabezados, json={
        "conteos": [{"uuid": "u-7", "codigo": alta["sku"], "cantidad": 2000,
                     "timestamp_dispositivo": "2026-08-11T10:00:00Z"}],
    })

    assert respuesta.json()["registrados"] == 1


def test_el_alta_rapida_no_expone_stock_ni_costo(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"])

    # Sin esto el test pasa en verde contra un 404: el cuerpo de un error
    # tampoco trae stock, y la regla que se quiere fijar queda sin fijar.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert "stock_sistema" not in cuerpo
    assert "costo_unitario" not in cuerpo


def test_el_alta_rapida_con_una_unidad_que_no_es_texto_devuelve_400(cliente, sesion):
    """Un cliente que serializa la unidad como número no puede colar un alta.

    Tomarlo como ausente daría de alta con «UN» algo que se cuenta en metros:
    el operario ve la unidad que no es y cuenta con la que no es.
    """
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"], unidad=5)

    assert respuesta.status_code == 400
    assert "unidad" in respuesta.json()["detail"]


def test_el_alta_rapida_con_una_ubicacion_que_no_es_texto_devuelve_400(cliente, sesion):
    """Un pasillo numérico llega como número y la ubicación se perdería."""
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"], ubicacion=7)

    assert respuesta.status_code == 400
    assert "ubicación" in respuesta.json()["detail"]


def test_el_alta_rapida_sin_token_devuelve_401(cliente, sesion):
    assert alta_rapida(cliente, "inventado").status_code == 401


def test_el_alta_rapida_con_datos_invalidos_devuelve_400(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = alta_rapida(cliente, operario["token_dispositivo"], descripcion="")

    assert respuesta.status_code == 400
    assert "descripción" in respuesta.json()["detail"]


def test_el_alta_rapida_con_un_cuerpo_que_no_es_objeto_devuelve_400(cliente, sesion):
    """Un cliente a medio escribir manda una lista; eso es culpa del pedido."""
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/articulos",
        headers={"X-Token": operario["token_dispositivo"]},
        json=["a", "b"],
    )

    assert respuesta.status_code == 400
    assert "artículo" in respuesta.json()["detail"]


def cortes(texto_con_acento, texto_sin_acento):
    """Los dos modos en que un corte de red deja el cuerpo inservible.

    Para Python son fallas distintas, y hay que atrapar las dos. Si el corte
    cae adentro de un carácter acentuado —media eñe— los bytes ni siquiera
    forman texto y falla la decodificación. Si cae en cualquier otro lado, el
    texto se arma pero queda incompleto y falla el parseo. En un sistema en
    castellano el primero no es un borde raro.
    """
    return [
        pytest.param(texto_con_acento.encode()[:-1], id="adentro-de-la-enie"),
        pytest.param(texto_sin_acento.encode(), id="entre-caracteres"),
    ]


@pytest.mark.parametrize(
    "cuerpo", cortes('{"descripcion": "Cañ', '{"descripcion": "Cano'),
)
def test_el_alta_rapida_con_el_cuerpo_cortado_devuelve_422(cliente, sesion, cuerpo):
    """Una conexión cortada a mitad de envío deja el cuerpo truncado.

    No es 400 a propósito, y la diferencia no es cosmética: el 400 del alta
    significa «leí tu artículo y lo rechazo por lo que es», y el celular lo
    usa para cerrar el alta y sus conteos para siempre. Un cuerpo cortado es
    lo contrario —el pedido no llegó entero— y reintentarlo funciona. Con el
    mismo código, un corte de WiFi le destruiría al operario conteos que se
    habrían subido solos.
    """
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/articulos",
        headers={"X-Token": operario["token_dispositivo"],
                 "Content-Type": "application/json"},
        content=cuerpo,
    )

    assert respuesta.status_code == 422
    assert "incompleto" in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "cuerpo",
    cortes(
        '{"conteos": [{"ubicacion_real": "Pasillo ñ',
        '{"conteos": [{"ubicacion_real": "Pasillo A',
    ),
)
def test_los_conteos_con_el_cuerpo_cortado_devuelven_422(cliente, sesion, cuerpo):
    """El mismo corte de red, en el endpoint por el que sube todo el trabajo."""
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.post(
        "/api/dispositivo/conteos",
        headers={"X-Token": operario["token_dispositivo"],
                 "Content-Type": "application/json"},
        content=cuerpo,
    )

    assert respuesta.status_code == 422
    assert "incompleto" in respuesta.json()["detail"]


def test_el_alta_rapida_aparece_en_el_tablero(cliente, sesion):
    importar(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    alta_rapida(cliente, operario["token_dispositivo"])

    filas = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"]

    nuevo = next(f for f in filas if f["descripcion"] == "Caño de bronce")
    assert nuevo["origen"] == "alta_rapida"


APK_FALSO = b"PK\x03\x04 esto hace de APK en los tests"


# Las dos fixturas apuntan `RUTA_APK` a un archivo de la carpeta temporal.
# Sin eso los tests miran `servidor/app.apk`, que existe o no según si esta
# máquina compiló la app: los mismos tests pasan hoy y fallan mañana.
@pytest.fixture
def sin_apk(monkeypatch, tmp_path):
    from app.api import panel as modulo_panel

    monkeypatch.setattr(modulo_panel, "RUTA_APK", tmp_path / "no-hay-app.apk")


@pytest.fixture
def con_apk(monkeypatch, tmp_path):
    from app.api import panel as modulo_panel

    apk = tmp_path / "app.apk"
    apk.write_bytes(APK_FALSO)
    monkeypatch.setattr(modulo_panel, "RUTA_APK", apk)
    return apk


def test_sin_apk_la_descarga_devuelve_404(cliente, sin_apk):
    assert cliente.get("/app.apk").status_code == 404


def test_sin_apk_la_instalacion_se_informa_como_no_disponible(cliente, sin_apk):
    """El panel no puede ofrecer una descarga que va a fallar."""
    respuesta = cliente.get("/api/instalacion")

    assert respuesta.status_code == 200
    assert respuesta.json()["disponible"] is False


def test_con_apk_presente_se_descarga(cliente, con_apk):
    respuesta = cliente.get("/app.apk")

    assert respuesta.status_code == 200
    assert respuesta.content == APK_FALSO
    assert "android.package-archive" in respuesta.headers["content-type"]


def test_con_apk_presente_la_instalacion_informa_la_direccion_de_red(cliente, con_apk):
    """El QR lo escanea un celular: 127.0.0.1 lo mandaría a sí mismo."""
    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["disponible"] is True
    assert cuerpo["url"].endswith("/app.apk")
    assert "127.0.0.1" not in cuerpo["url"]


def test_el_qr_de_instalacion_es_svg(cliente, con_apk):
    respuesta = cliente.get("/api/instalacion/qr")

    assert respuesta.status_code == 200
    assert "image/svg+xml" in respuesta.headers["content-type"]


def test_el_qr_de_instalacion_sin_apk_devuelve_404(cliente, sin_apk):
    assert cliente.get("/api/instalacion/qr").status_code == 404


def test_la_instalacion_informa_la_version_publicada(cliente, con_apk):
    """El responsable tiene que poder mirar el panel y saber si el cliente
    tiene la versión nueva o la vieja, sin desinstalar nada para comparar."""
    con_apk.with_name("app.apk.txt").write_text("2026-08-13 (build 42)", encoding="utf-8")

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["version"] == "2026-08-13 (build 42)"


def test_sin_el_archivo_de_version_igual_se_informa_cuando_se_publico(cliente, con_apk):
    """Alguien copió un APK a mano. La fecha sale del archivo, así que no
    puede desactualizarse, y responde la misma pregunta."""
    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["version"] == ""
    assert cuerpo["publicado"].endswith("Z")


def test_la_fecha_de_publicacion_es_la_del_archivo(cliente, con_apk):
    import os
    from datetime import datetime, timezone

    # Construida y no escrita a mano: un número de época puesto a ojo se
    # equivoca de día y el test pasa a probar la aritmética del que lo
    # escribió.
    momento = datetime(2026, 8, 13, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    os.utime(con_apk, (momento, momento))

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["publicado"] == "2026-08-13T12:00:00Z"


def test_sin_apk_no_se_informa_ninguna_version(cliente, sin_apk):
    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["disponible"] is False
    assert cuerpo["version"] == ""
    assert cuerpo["publicado"] == ""


@pytest.fixture
def con_novedades(monkeypatch, tmp_path):
    from app.api import panel as modulo_panel

    archivo = tmp_path / "novedades.md"
    archivo.write_text("## build 223\n- Primer cambio\n", encoding="utf-8")
    monkeypatch.setattr(modulo_panel, "RUTA_NOVEDADES", archivo)
    return archivo


def test_las_novedades_se_devuelven_parseadas(cliente, con_novedades):
    cuerpo = cliente.get("/api/novedades").json()

    assert cuerpo == [{"titulo": "build 223", "items": ["Primer cambio"]}]


def test_sin_el_archivo_de_novedades_devuelve_lista_vacia(cliente, monkeypatch, tmp_path):
    from app.api import panel as modulo_panel

    monkeypatch.setattr(modulo_panel, "RUTA_NOVEDADES", tmp_path / "no-existe.md")

    assert cliente.get("/api/novedades").json() == []


def test_una_version_con_saltos_de_linea_no_ensucia_el_panel(cliente, con_apk):
    """El archivo lo escribe la publicación, pero es un archivo del disco:
    el que llegue con un salto de línea de más no puede romper el renglón."""
    con_apk.with_name("app.apk.txt").write_text(
        "2026-08-13 (build 42)\n", encoding="utf-8"
    )

    assert cliente.get("/api/instalacion").json()["version"] == "2026-08-13 (build 42)"


def test_archivo_de_version_en_utf16_se_informa_como_ausente(cliente, con_apk):
    """PowerShell Out-File escribe UTF-16 por defecto. Cmd escribe cp1252.
    Si el archivo no es UTF-8, no se puede leer sin romper /api/instalacion.
    La regla es: si falta o no se puede leer, se informa vacía."""
    archivo = con_apk.with_name("app.apk.txt")
    archivo.write_bytes("2026-08-13 (build 42)".encode("utf-16"))

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["version"] == ""
    assert cuerpo["disponible"] is True


def test_archivo_de_version_con_bom_se_limpia(cliente, con_apk):
    """Set-Content -Encoding UTF8 de PowerShell antepone BOM.
    U+FEFF no es espacio en blanco, así que strip() no lo toca.
    La versión viajaría con un carácter invisible adelante, rompiendo
    cualquier comparación («¿es la misma versión?»)."""
    archivo = con_apk.with_name("app.apk.txt")
    # Escribo los bytes crudos: BOM UTF-8 (EF BB BF) + contenido
    archivo.write_bytes(b'\xef\xbb\xbf2026-08-13 (build 42)')

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["version"] == "2026-08-13 (build 42)"
    assert "﻿" not in cuerpo["version"]


def test_archivo_de_version_multilinea_o_muy_largo_queda_en_una_linea(cliente, con_apk):
    """El docstring promete que no puede romper el renglón. Strip limpia
    las puntas pero adentro pasa cualquier cosa: varias líneas, un archivo
    de 3 MB. El panel debe quedarse con la primera línea y un largo sensato."""
    archivo = con_apk.with_name("app.apk.txt")
    contenido = "2026-08-13 (build 42)\nSEGUNDA LINEA\nTERCERA LINEA"
    archivo.write_text(contenido, encoding="utf-8")

    version = cliente.get("/api/instalacion").json()["version"]

    assert version == "2026-08-13 (build 42)"
    assert "\n" not in version


def test_directorio_donde_va_version_no_rompe_instalacion(cliente, con_apk):
    """Si en lugar del archivo hay una carpeta (o el archivo está bloqueado
    por antivirus), en Windows levanta PermissionError, no IsADirectoryError.
    La captura debe ser OSError, que es el padre de ambos. Si no, /api/instalacion
    devuelve 500 y el panel no puede mostrar el QR ni el enlace."""
    directorio = con_apk.with_name("app.apk.txt")
    directorio.mkdir()

    cuerpo = cliente.get("/api/instalacion").json()

    assert cuerpo["disponible"] is True
    assert cuerpo["version"] == ""


def test_version_muy_larga_se_trunca_a_largo_sensato(cliente, con_apk):
    """Una sola línea de 3 MB pasa entera sin el tope. El panel comparte
    el renglón con el QR: renderizar 3 millones de caracteres lo rompe."""
    archivo = con_apk.with_name("app.apk.txt")
    # Una línea con 10.000 caracteres (mucho más que una versión razonable)
    version_larga = "2026-08-13 (build 42)" + "x" * 10000
    archivo.write_text(version_larga, encoding="utf-8")

    version = cliente.get("/api/instalacion").json()["version"]

    # La versión debe truncarse a un largo sensato. Un número de versión
    # típico no excede 100 caracteres; permitimos hasta 200 para ser generoso.
    assert len(version) <= 200
    assert version.startswith("2026-08-13 (build 42)")


def test_ubicaciones_de_la_sesion_abierta(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/ubicaciones")

    assert respuesta.status_code == 200
    assert respuesta.json() == ["Deposito A", "Deposito B"]


def test_ubicaciones_de_sesion_inexistente_da_404(cliente):
    assert cliente.get("/api/sesiones/9999/ubicaciones").status_code == 404


def test_operarios_traen_ubicaciones_asignadas_vacias_por_defecto(cliente, sesion):
    cliente.post("/api/operarios", json={"nombre": "Juan"})

    respuesta = cliente.get("/api/operarios")

    assert respuesta.json()[0]["ubicaciones_asignadas"] == []


def test_asignar_ubicaciones_a_un_operario(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"], "pasada_id": sesion["pasada"]["id"]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ubicaciones"] == ["Deposito A"]

    lista = cliente.get("/api/operarios").json()
    juan = next(o for o in lista if o["id"] == operario["id"])
    assert juan["ubicaciones_asignadas"] == ["Deposito A"]


def test_asignar_reemplaza_lo_anterior(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"], "pasada_id": sesion["pasada"]["id"]},
    )

    cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito B"], "pasada_id": sesion["pasada"]["id"]},
    )

    lista = cliente.get("/api/operarios").json()
    juan = next(o for o in lista if o["id"] == operario["id"])
    assert juan["ubicaciones_asignadas"] == ["Deposito B"]


def test_asignar_a_un_operario_inexistente_da_404(cliente, sesion):
    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/9999/asignacion",
        json={"ubicaciones": [], "pasada_id": sesion["pasada"]["id"]},
    )
    assert respuesta.status_code == 404


def test_asignar_con_la_sesion_cerrada_da_409(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post(f"/api/sesiones/{sesion['id']}/cerrar")

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": [], "pasada_id": sesion["pasada"]["id"]},
    )

    assert respuesta.status_code == 409


def test_asignar_sin_lista_de_ubicaciones_da_400(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={},
    )

    assert respuesta.status_code == 400


# --- La lista de ubicaciones asignadas que baja el celular -------------------

def asignar(cliente, sesion_id, operario_id, ubicaciones, pasada_id=None):
    if pasada_id is None:
        pasada_id = cliente.get(f"/api/sesiones/{sesion_id}").json()["pasada"]["id"]
    return cliente.put(
        f"/api/sesiones/{sesion_id}/operarios/{operario_id}/asignacion",
        json={"ubicaciones": ubicaciones, "pasada_id": pasada_id},
    )


def test_mis_ubicaciones_devuelve_lo_asignado(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    asignar(cliente, sesion["id"], operario["id"], ["Deposito B", "Deposito A"])

    respuesta = cliente.get(
        "/api/dispositivo/mis-ubicaciones",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ubicaciones"] == ["Deposito A", "Deposito B"]
    assert respuesta.json()["pasada_id"] == sesion["pasada"]["id"]


def test_mis_ubicaciones_sin_asignar_devuelve_lista_vacia(cliente, sesion):
    """Que no le hayan repartido nada es una respuesta, no un error."""
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.get(
        "/api/dispositivo/mis-ubicaciones",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ubicaciones"] == []


def test_mis_ubicaciones_no_trae_nada_mas(cliente, sesion):
    """Un endpoint de dispositivo no puede engordar sin que alguien lo note."""
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    cuerpo = cliente.get(
        "/api/dispositivo/mis-ubicaciones",
        headers={"X-Token": operario["token_dispositivo"]},
    ).json()

    assert set(cuerpo) == {
        "pasada_id", "pasada_numero", "pasada_etiqueta", "es_parcial",
        "articulos_permitidos", "ubicaciones",
    }


def test_mis_ubicaciones_con_token_inventado(cliente, sesion):
    respuesta = cliente.get(
        "/api/dispositivo/mis-ubicaciones", headers={"X-Token": "inventado"}
    )

    assert respuesta.status_code == 401


def test_mis_ubicaciones_sin_sesion_abierta(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post(f"/api/sesiones/{sesion['id']}/cerrar")

    respuesta = cliente.get(
        "/api/dispositivo/mis-ubicaciones",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 409


def test_mis_ubicaciones_sin_conteo_abierto_avisa_en_vez_de_romper(cliente, sesion):
    """Una lista vacia seria mentira: el celular la escribiria encima de la
    que tenia y le borraria el reparto al operario. Mejor decirle que ahora
    no se puede contestar, y que conserve lo suyo."""
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    con = cliente.app.state.con
    con.execute(
        "UPDATE pasada SET estado = 'cerrada' WHERE sesion_id = ?", (sesion["id"],)
    )
    con.commit()

    respuesta = cliente.get(
        "/api/dispositivo/mis-ubicaciones",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 409
    assert "conteo" in respuesta.json()["detail"].lower()


# --- La pestaña de reparto ---------------------------------------------------

def test_ver_reparto(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    asignar(cliente, sesion["id"], operario["id"], ["Deposito A"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/reparto")

    assert respuesta.status_code == 200
    filas = respuesta.json()["filas"]
    fila_a = next(f for f in filas if f["sku"] == "A")
    assert fila_a["asignado_a"] == ["Juan"]


def test_ver_reparto_sesion_inexistente(cliente):
    respuesta = cliente.get("/api/sesiones/999/reparto")

    assert respuesta.status_code == 404


def test_ver_reparto_respeta_los_filtros(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])

    respuesta = cliente.get(
        f"/api/sesiones/{sesion['id']}/reparto", params={"ubicacion": "Deposito B"}
    )

    assert [f["sku"] for f in respuesta.json()["filas"]] == ["B"]


def test_exportar_reparto(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/exportar/reparto")

    assert respuesta.status_code == 200
    assert "ubicacion;sku;descripcion" in respuesta.text


def test_ver_avance_por_operario(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    asignar(cliente, sesion["id"], operario["id"], ["Deposito A"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/reparto/operarios")

    assert respuesta.status_code == 200
    operarios = respuesta.json()["operarios"]
    assert operarios[0]["operario"] == "Juan"
    assert operarios[0]["total"] == 1


def test_ver_avance_por_operario_sesion_inexistente(cliente):
    respuesta = cliente.get("/api/sesiones/999/reparto/operarios")

    assert respuesta.status_code == 404


# --- Vincular resuelve la pasada activa del operario -------------------------

def test_vincular_devuelve_la_pasada_activa_del_operario(cliente, sesion):
    """Con un recuento abierto y el operario asignado ahí, /vincular tiene
    que devolver ESA pasada, no la de numero mas alto por default."""
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    con = cliente.app.state.con
    from app.repos import asignaciones as asignaciones_repo
    from app.repos import pasada_item as pasada_item_repo

    articulo_id = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? LIMIT 1", (sesion["id"],)
    ).fetchone()["id"]
    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion["id"], "2026-08-17T10:00:00Z"),
    )
    pasada_2_id = cursor.lastrowid
    pasada_item_repo.agregar(con, pasada_2_id, [articulo_id])
    asignaciones_repo.reemplazar(con, pasada_2_id, operario["id"], ["Deposito A"])
    con.commit()

    respuesta = cliente.post(
        "/api/dispositivo/vincular",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["pasada"]["id"] == pasada_2_id
    assert respuesta.json()["pasada"]["numero"] == 2


def test_vincular_sin_pasada_activa_devuelve_409(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    con = cliente.app.state.con
    con.execute(
        "UPDATE pasada SET estado = 'cerrada' WHERE sesion_id = ?", (sesion["id"],)
    )
    con.commit()

    respuesta = cliente.post(
        "/api/dispositivo/vincular",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.status_code == 409


def test_vincular_operario_ajeno_al_recuento_sigue_en_la_general(cliente, sesion):
    """El numero de pasada mas alto no puede ganar solo porque es el mas
    alto: si el operario no esta asignado ahi, le toca la general."""
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    con = cliente.app.state.con
    con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion["id"], "2026-08-17T10:00:00Z"),
    )
    con.commit()
    # Juan no está asignado a la pasada 2.

    respuesta = cliente.post(
        "/api/dispositivo/vincular",
        headers={"X-Token": operario["token_dispositivo"]},
    )

    assert respuesta.json()["pasada"]["numero"] == 1


# --- La sesión expone la pasada general, no la de numero mas alto ----------

def test_ver_sesion_expone_la_pasada_general_con_un_recuento_abierto(cliente, sesion):
    con = cliente.app.state.con
    con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion["id"], "2026-08-17T10:00:00Z"),
    )
    con.commit()

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}")

    assert respuesta.json()["pasada"]["numero"] == 1


# --- Asignar exige pasada_id y valida exclusividad de recuento -------------

def test_asignar_sin_pasada_id_devuelve_400(cliente, sesion):
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"]},
    )

    assert respuesta.status_code == 400


def test_asignar_a_la_general_funciona_con_pasada_id_explicito(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    pasada_general_id = sesion["pasada"]["id"]

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"], "pasada_id": pasada_general_id},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ubicaciones"] == ["Deposito A"]


def test_asignar_a_un_segundo_recuento_abierto_se_rechaza(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    con = cliente.app.state.con

    articulo_id = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? LIMIT 1", (sesion["id"],)
    ).fetchone()["id"]

    from app.repos import pasada_item as pasada_item_repo

    cursor_1 = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion["id"], "2026-08-17T10:00:00Z"),
    )
    recuento_1 = cursor_1.lastrowid
    pasada_item_repo.agregar(con, recuento_1, [articulo_id])

    cursor_2 = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 3, ?)",
        (sesion["id"], "2026-08-17T10:00:00Z"),
    )
    recuento_2 = cursor_2.lastrowid
    pasada_item_repo.agregar(con, recuento_2, [articulo_id])
    con.commit()

    primera = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"], "pasada_id": recuento_1},
    )
    assert primera.status_code == 200

    segunda = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito B"], "pasada_id": recuento_2},
    )

    assert segunda.status_code == 409


def test_reasignar_dentro_del_mismo_recuento_no_se_bloquea(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    con = cliente.app.state.con

    articulo_id = con.execute(
        "SELECT id FROM articulo WHERE sesion_id = ? LIMIT 1", (sesion["id"],)
    ).fetchone()["id"]

    from app.repos import pasada_item as pasada_item_repo

    cursor = con.execute(
        "INSERT INTO pasada (sesion_id, numero, fecha_apertura) VALUES (?, 2, ?)",
        (sesion["id"], "2026-08-17T10:00:00Z"),
    )
    recuento = cursor.lastrowid
    pasada_item_repo.agregar(con, recuento, [articulo_id])
    con.commit()

    cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"], "pasada_id": recuento},
    )

    respuesta = cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A", "Deposito B"], "pasada_id": recuento},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["ubicaciones"] == ["Deposito A", "Deposito B"]


def test_listar_pasadas_devuelve_conteo_1(cliente, sesion):
    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/pasadas")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["etiqueta"] == "Conteo 1"
    assert cuerpo[0]["es_parcial"] is False


def test_abrir_pasada_crea_un_recuento(cliente, sesion):
    importar(cliente, sesion["id"])
    articulo_id = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"][0]["id"]

    respuesta = cliente.post(
        f"/api/sesiones/{sesion['id']}/pasadas", json={"articulo_ids": [articulo_id]}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["etiqueta"] == "Conteo 2"
    assert cuerpo["es_parcial"] is True

    pasadas = cliente.get(f"/api/sesiones/{sesion['id']}/pasadas").json()
    assert len(pasadas) == 2


def test_abrir_pasada_sin_articulos_devuelve_400(cliente, sesion):
    respuesta = cliente.post(f"/api/sesiones/{sesion['id']}/pasadas", json={"articulo_ids": []})

    assert respuesta.status_code == 400


def test_abrir_pasada_en_sesion_inexistente_devuelve_404(cliente):
    respuesta = cliente.post("/api/sesiones/999/pasadas", json={"articulo_ids": [1]})

    assert respuesta.status_code == 404


def test_abrir_pasada_con_sesion_cerrada_devuelve_409(cliente, sesion):
    importar(cliente, sesion["id"])
    articulo_id = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"][0]["id"]
    cliente.post(f"/api/sesiones/{sesion['id']}/cerrar")

    respuesta = cliente.post(
        f"/api/sesiones/{sesion['id']}/pasadas", json={"articulo_ids": [articulo_id]}
    )

    assert respuesta.status_code == 409


def test_avance_de_pasada(cliente, sesion):
    importar_con_ubicacion(cliente, sesion["id"])
    articulo_a = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"][0]["id"]
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()

    recuento = cliente.post(
        f"/api/sesiones/{sesion['id']}/pasadas", json={"articulo_ids": [articulo_a]}
    ).json()
    asignar(cliente, sesion["id"], operario["id"], ["Deposito A"], pasada_id=recuento["id"])

    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/pasadas/{recuento['id']}/avance")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo[0]["operario"] == "Juan"
    assert cuerpo[0]["total"] == 1


def test_avance_de_pasada_inexistente_devuelve_404(cliente, sesion):
    respuesta = cliente.get(f"/api/sesiones/{sesion['id']}/pasadas/999/avance")

    assert respuesta.status_code == 404


def test_borrar_pasada_sin_conteos(cliente, sesion):
    importar(cliente, sesion["id"])
    articulo_id = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"][0]["id"]
    recuento = cliente.post(
        f"/api/sesiones/{sesion['id']}/pasadas", json={"articulo_ids": [articulo_id]}
    ).json()

    respuesta = cliente.delete(f"/api/sesiones/{sesion['id']}/pasadas/{recuento['id']}")

    assert respuesta.status_code == 200
    pasadas = cliente.get(f"/api/sesiones/{sesion['id']}/pasadas").json()
    assert [p["id"] for p in pasadas] == [sesion["pasada"]["id"]]


def test_borrar_pasada_con_conteos_devuelve_409(cliente, sesion):
    importar(cliente, sesion["id"])
    articulo_id = cliente.get(f"/api/sesiones/{sesion['id']}/tablero").json()["filas"][0]["id"]
    recuento = cliente.post(
        f"/api/sesiones/{sesion['id']}/pasadas", json={"articulo_ids": [articulo_id]}
    ).json()
    operario = cliente.post("/api/operarios", json={"nombre": "Juan"}).json()
    cliente.post(
        "/api/dispositivo/vincular", headers={"X-Token": operario["token_dispositivo"]}
    )
    cliente.put(
        f"/api/sesiones/{sesion['id']}/operarios/{operario['id']}/asignacion",
        json={"ubicaciones": ["Deposito A"], "pasada_id": recuento["id"]},
    )
    cliente.post(
        "/api/dispositivo/conteos",
        headers={"X-Token": operario["token_dispositivo"]},
        json={"conteos": [{
            "uuid": "u1", "codigo": "A", "cantidad": 1000,
            "timestamp_dispositivo": "2026-08-17T10:00:00Z",
        }]},
    )

    respuesta = cliente.delete(f"/api/sesiones/{sesion['id']}/pasadas/{recuento['id']}")

    assert respuesta.status_code == 409


def test_borrar_pasada_general_devuelve_400(cliente, sesion):
    respuesta = cliente.delete(f"/api/sesiones/{sesion['id']}/pasadas/{sesion['pasada']['id']}")

    assert respuesta.status_code == 400


def test_borrar_pasada_inexistente_devuelve_404(cliente, sesion):
    respuesta = cliente.delete(f"/api/sesiones/{sesion['id']}/pasadas/999")

    assert respuesta.status_code == 404
