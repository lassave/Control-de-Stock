import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import crear_app

RUTA_PANEL = Path(__file__).resolve().parent.parent / "panel"


@pytest.fixture
def cliente(tmp_path):
    app = crear_app(str(tmp_path / "prueba.db"))
    with TestClient(app) as cliente:
        yield cliente


def test_el_panel_se_sirve_en_la_raiz(cliente):
    respuesta = cliente.get("/")

    assert respuesta.status_code == 200
    assert "Control de Stock" in respuesta.text


@pytest.mark.parametrize("archivo", ["estilos.css", "app.js"])
def test_los_archivos_del_panel_se_sirven(cliente, archivo):
    """Si el montaje estático se rompe, el panel queda sin estilos ni lógica."""
    assert cliente.get(f"/{archivo}").status_code == 200


def test_la_api_gana_sobre_los_archivos_estaticos(cliente):
    """El panel se monta en la raíz: no puede tapar las rutas de la API."""
    assert cliente.get("/api/sesiones").status_code == 200


@pytest.mark.parametrize("ruta", ["/", "/app.js", "/estilos.css"])
def test_el_panel_le_pregunta_al_servidor_antes_de_reusar_lo_que_tiene(cliente, ruta):
    """Sin `Cache-Control`, el navegador se guarda el derecho a no preguntar.

    Con `ETag` y `Last-Modified` solos, alcanza para que el navegador estime
    por su cuenta cuánto vale lo que ya bajó y siga usándolo sin consultar.
    Después de actualizar el sistema, el panel viejo sigue corriendo y no hay
    nada en pantalla que lo diga: pasó acá, con un `app.js` anterior al QR de
    vinculación: el operario no podía vincular el celular y el panel se veía
    perfecto. `no-cache` no prohíbe guardar, obliga a revalidar; con el ETag
    la respuesta suele ser un 304 sin cuerpo, que en la red del depósito no
    cuesta nada.
    """
    respuesta = cliente.get(ruta)

    assert "no-cache" in respuesta.headers.get("cache-control", "")


def test_no_hay_referencias_a_recursos_externos():
    """Durante el conteo puede no haber internet: todo se sirve local."""
    patron = re.compile(r'(src|href)\s*=\s*["\']https?://', re.IGNORECASE)

    for archivo in RUTA_PANEL.rglob("*"):
        if archivo.suffix in {".html", ".css", ".js"}:
            contenido = archivo.read_text(encoding="utf-8")
            assert not patron.search(contenido), f"{archivo.name} carga algo externo"


def test_los_estados_usan_texto_ademas_de_color():
    """El estado no puede comunicarse solo con color (spec, sección 8)."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    for estado in ["SIN CONTAR", "CONSOLIDADO", "A RECONTAR"]:
        assert estado in contenido


DATOS_DEL_SERVIDOR = re.compile(r"\b(fila|sesion|operario|vista|resultado|estado)\.")

# Solo se auditan las plantillas que arman marcado. Lo que va por
# `textContent` no interpreta HTML, y escaparlo ahí mostraría «&amp;» en
# pantalla cada vez que una sesión se llame «Juan & Hnos».
PLANTILLAS = re.compile(r"`([^`]*)`", re.DOTALL)
INTERPOLACION = re.compile(r"\$\{([^{}]*)\}")


def test_los_datos_del_servidor_se_escapan_antes_de_ir_al_html():
    """El maestro lo escribe el cliente: una descripción con «<» rompe la tabla.

    No hace falta mala fe. Alcanza con un «CAÑO 3/4 <PVC>» en el CSV del ERP
    para que la fila entera desaparezca de la pantalla sin ningún aviso.
    """
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    crudas = [
        expresion
        for plantilla in PLANTILLAS.findall(contenido)
        if "<" in plantilla
        for expresion in INTERPOLACION.findall(plantilla)
        if DATOS_DEL_SERVIDOR.search(expresion) and "esc(" not in expresion
    ]

    assert crudas == [], f"Interpolaciones sin escapar: {crudas}"


def test_el_panel_muestra_el_token_de_cada_operario():
    """Es lo único con lo que se vincula un celular: sin verlo no hay conteo.

    La API lo devuelve desde el primer día, pero si el panel no lo muestra
    hay que abrir la base a mano para poner en marcha un dispositivo.
    """
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "token_dispositivo" in contenido


def test_el_panel_muestra_el_qr_de_vinculacion():
    """Sin el QR hay que transcribir a mano 43 caracteres y la IP del lugar."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "/qr" in contenido


@pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado")
def test_el_javascript_del_panel_parsea():
    """Un error de sintaxis deja el panel en blanco y ningún otro test lo ve.

    Los demás tests leen `app.js` como texto: una coma de más lo pasa entero
    y recién se descubre abriendo el navegador durante el inventario.
    """
    resultado = subprocess.run(
        [shutil.which("node"), "--check", str(RUTA_PANEL / "app.js")],
        capture_output=True, text=True,
    )

    assert resultado.returncode == 0, resultado.stderr


def test_exportar_arrastra_los_filtros_del_tablero():
    """Se exporta lo que está en pantalla, no el depósito entero."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "exportar/resumen?" in contenido
    assert "exportar/detalle?" in contenido


def _cuerpo_de(js, nombre):
    """El código entre las llaves de una función, contando el anidamiento.

    Buscar el nombre en el archivo entero no alcanza: una función definida
    y nunca llamada aparece igual.
    """
    apertura = js.index("{", js.index(f"function {nombre}("))
    profundidad = 0
    for posicion in range(apertura, len(js)):
        if js[posicion] == "{":
            profundidad += 1
        elif js[posicion] == "}":
            profundidad -= 1
            if profundidad == 0:
                return js[apertura + 1:posicion]
    raise AssertionError(f"«{nombre}» no cierra sus llaves")


def test_el_panel_esconde_la_instalacion_si_no_hay_apk():
    """Ofrecer una descarga que devuelve 404 es peor que no ofrecer nada."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "/api/instalacion" in contenido
    assert "estado.disponible" in contenido
    # Las dos de arriba quedan verdes con el toggle invertido —el bloque
    # aparecería justo cuando NO hay APK— y también si nadie llama a
    # `cargarInstalacion`, con lo que no aparecería nunca.
    assert "!estado.disponible" in contenido
    assert "cargarInstalacion" in _cuerpo_de(contenido, "cargarOperarios")


ETIQUETA_IMG = re.compile(r"<img[^>]*>")


def test_el_qr_de_instalacion_se_pide_recien_cuando_hay_apk():
    """Un `src` fijo se baja igual con el bloque escondido, y no se reintenta.

    Puesta en marcha real: se abre el panel sin APK y la imagen 404ea; se
    copia el APK; se da de alta un operario y el bloque se desesconde en
    caliente, pero con el QR roto y sin ninguna explicación. Hay que apretar
    F5 para verlo. Es también el 404 en la consola en cada carga sin APK.
    """
    html = (RUTA_PANEL / "index.html").read_text(encoding="utf-8")
    bloque = html.split('id="instalacion"', 1)[1].split("</section>", 1)[0]
    imagen = ETIQUETA_IMG.search(bloque).group(0)

    assert "src=" not in imagen, f"el QR de instalación tiene src fijo: {imagen}"
    assert "/api/instalacion/qr" in _cuerpo_de(
        (RUTA_PANEL / "app.js").read_text(encoding="utf-8"), "cargarInstalacion"
    )


REGLA_CSS = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _clases_que_el_panel_esconde():
    """Las clases de los elementos que arrancan o quedan con `oculta`."""
    html = (RUTA_PANEL / "index.html").read_text(encoding="utf-8")
    clases = set()
    for atributo in re.findall(r'class="([^"]+)"', html):
        nombres = atributo.split()
        if "oculta" in nombres:
            clases.update(nombres)
    return clases - {"oculta"}


def test_esconder_con_oculta_le_gana_a_las_reglas_de_cada_bloque():
    """Un bloque que define su propio `display` anula a `.oculta` en silencio.

    Las dos reglas tienen la misma especificidad, así que gana la última de
    la hoja. Le pasó al bloque de instalación: el JavaScript le ponía
    `oculta` y seguía en pantalla, ofreciendo una descarga que no existe.
    Ningún otro test lo ve, solo se nota abriendo el panel.
    """
    reglas = REGLA_CSS.findall((RUTA_PANEL / "estilos.css").read_text(encoding="utf-8"))
    posicion = next(i for i, (selector, _) in enumerate(reglas) if ".oculta" in selector)
    escondibles = _clases_que_el_panel_esconde()

    for selector, declaraciones in reglas[posicion + 1:]:
        clase = selector.strip().lstrip(".")
        if clase in escondibles and "display" in declaraciones:
            assert f".{clase}.oculta" in reglas[posicion][0], (
                f"«{clase}» define display después de `.oculta`: "
                "esconderlo no va a tener efecto"
            )


def test_la_version_del_apk_se_escribe_como_texto_y_no_como_marcado():
    """Sale de un archivo del disco, así que es dato como cualquier otro.

    Por `textContent` no interpreta HTML y no hace falta escaparlo; armado
    como marcado, un archivo con `<b>` adentro entraría al panel.
    """
    js_crudo = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    # Sacar comentarios de línea de forma más robusta: solo el texto
    # después de // que no esté adentro de un string literal
    patron_comentario = re.compile(r'//.*')
    js_sin_comentarios = patron_comentario.sub("", js_crudo)

    # Buscar todas las asignaciones a $("#version-apk") en el archivo entero
    # Patrón: $("#version-apk")...algo = valor
    patron_asignacion = re.compile(r'#["\']*version-apk["\']?\s*\)[^;]*=')
    asignaciones = patron_asignacion.findall(js_sin_comentarios)

    assert asignaciones, "No hay asignaciones a #version-apk en el código"

    # Cada asignación tiene que usar .textContent =, no otra cosa
    for asignacion in asignaciones:
        assert ".textContent" in asignacion, (
            f"Asignación sin textContent: {asignacion}"
        )
        # Prohibir toda la familia de métodos inseguros
        metodos_inseguros = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"]
        for metodo in metodos_inseguros:
            assert metodo not in asignacion, (
                f"Se usa {metodo} en asignación: {asignacion}"
            )


def test_el_panel_ofrece_asignar_sectores():
    """Sin esto no hay forma de repartir ubicaciones desde el panel."""
    html = (RUTA_PANEL / "index.html").read_text(encoding="utf-8")
    js = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert 'id="dialogo-sectores"' in html
    assert "showModal" in js
    assert "/asignacion" in js


def test_el_panel_tiene_la_pestana_de_reparto():
    """Sin esto no hay forma de ver, en el panel, quién tiene qué."""
    html = (RUTA_PANEL / "index.html").read_text(encoding="utf-8")

    assert 'data-vista="reparto"' in html
    assert 'id="vista-reparto"' in html


def test_reparto_exporta_con_los_filtros():
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "exportar/reparto?" in contenido


def test_reparto_escapa_cada_nombre_por_separado():
    """Cada nombre se escapa antes de unirse, no la lista entera después."""
    contenido = (RUTA_PANEL / "app.js").read_text(encoding="utf-8")

    assert "asignado_a.map((n) => esc(n))" in contenido
    assert "contado_por.map((n) => esc(n))" in contenido
