"""Lectura de los CSV que exportan los ERP.

Cada sistema exporta distinto: separador de coma o punto y coma, y en
Windows es habitual cp1252 en vez de UTF-8. Adivinar mal cualquiera de
las dos cosas rompe la importación entera, así que se resuelve acá.
"""

import csv
import io

CODIFICACIONES = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]
SEPARADORES = [";", ",", "\t", "|"]


def detectar_codificacion(contenido):
    """Devuelve la primera codificación con la que el archivo se lee entero."""
    for codificacion in CODIFICACIONES:
        try:
            contenido.decode(codificacion)
            return codificacion
        except UnicodeDecodeError:
            continue
    return "latin-1"  # nunca falla: mapea cualquier byte


def detectar_separador(texto):
    """El separador es el que más veces aparece en la primera línea."""
    primera_linea = texto.splitlines()[0] if texto.splitlines() else ""
    conteos = {sep: primera_linea.count(sep) for sep in SEPARADORES}
    mejor = max(conteos, key=conteos.get)
    return mejor if conteos[mejor] > 0 else ","


def leer(contenido):
    """Devuelve (encabezados, filas) a partir del contenido binario del archivo."""
    if not contenido or not contenido.strip():
        raise ValueError("El archivo está vacío")

    texto = contenido.decode(detectar_codificacion(contenido))
    separador = detectar_separador(texto)

    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    todas = [fila for fila in lector if any(celda.strip() for celda in fila)]

    if not todas:
        raise ValueError("El archivo está vacío")

    encabezados = [celda.strip() for celda in todas[0]]

    vistos = set()
    for encabezado in encabezados:
        clave = encabezado.lower()
        if clave in vistos:
            raise ValueError(f"La columna «{encabezado}» está duplicada en el archivo")
        vistos.add(clave)

    cantidad = len(encabezados)
    filas = []
    for fila in todas[1:]:
        completa = [celda.strip() for celda in fila[:cantidad]]
        completa += [""] * (cantidad - len(completa))
        filas.append(completa)

    return encabezados, filas
