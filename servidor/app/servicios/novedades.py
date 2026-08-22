"""Lectura de las notas de versión para la pestaña Novedades del panel.

El archivo lo mantiene a mano quien publica: una sección por versión,
`## <título>`, seguida de viñetas `- `. No hay que inventarle estructura al
resto —comentarios HTML, líneas sueltas— porque el título ya explica el
formato ahí mismo.
"""

import re

PATRON_TITULO = re.compile(r"^##\s+(.+?)\s*$")
PATRON_VINIETA = re.compile(r"^-\s+(.+?)\s*$")


def leer(texto: str) -> list[dict]:
    """Devuelve una lista de {"titulo", "items"}, en el orden del archivo."""
    secciones = []
    actual = None

    for linea in texto.splitlines():
        titulo = PATRON_TITULO.match(linea)
        if titulo:
            actual = {"titulo": titulo.group(1), "items": []}
            secciones.append(actual)
            continue

        if actual is None:
            continue

        vinieta = PATRON_VINIETA.match(linea)
        if vinieta:
            actual["items"].append(vinieta.group(1))

    return secciones
