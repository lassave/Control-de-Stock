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


DATOS_DEL_SERVIDOR = re.compile(r"\b(fila|sesion|operario|vista|resultado)\.")

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
