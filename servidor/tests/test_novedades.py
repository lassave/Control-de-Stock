from app.servicios import novedades


def test_una_seccion_con_sus_viñetas():
    texto = "## 2026-08-21 · build 223\n\n- Primer cambio\n- Segundo cambio\n"

    assert novedades.leer(texto) == [
        {"titulo": "2026-08-21 · build 223", "items": ["Primer cambio", "Segundo cambio"]},
    ]


def test_varias_secciones_mantienen_el_orden_del_archivo():
    texto = (
        "## build 223\n- Nuevo\n\n"
        "## build 187\n- Viejo\n"
    )

    resultado = novedades.leer(texto)

    assert [seccion["titulo"] for seccion in resultado] == ["build 223", "build 187"]


def test_texto_vacio_no_tiene_secciones():
    assert novedades.leer("") == []


def test_ignora_comentarios_html_y_lineas_sueltas():
    texto = (
        "<!-- un comentario que explica el formato -->\n\n"
        "## build 223\n"
        "una línea que no es viñeta, se ignora\n"
        "- Esto sí es una viñeta\n"
    )

    assert novedades.leer(texto) == [
        {"titulo": "build 223", "items": ["Esto sí es una viñeta"]},
    ]
