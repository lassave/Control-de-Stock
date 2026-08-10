"""Lectura de los CSV que exportan los ERP.

Cada sistema exporta distinto: separador de coma o punto y coma, y en
Windows es habitual cp1252 en vez de UTF-8. Adivinar mal cualquiera de
las dos cosas rompe la importación entera, así que se resuelve acá.
"""

import csv
import io

# utf-8-sig también decodifica UTF-8 sin BOM, así que cubre los dos casos.
# latin-1 va última y nunca falla: mapea cualquier byte.
CODIFICACIONES = ["utf-8-sig", "cp1252", "latin-1"]
SEPARADORES = [",", ";", "\t", "|"]

LINEAS_DE_MUESTRA = 20


def detectar_codificacion(contenido: bytes) -> str:
    """Devuelve la primera codificación con la que el archivo se lee entero.

    El orden importa: casi cualquier texto UTF-8 también decodifica sin
    error como cp1252, pero al revés no. Probar UTF-8 primero evita el
    clásico «CañerÃ­a» en las descripciones.
    """
    for codificacion in CODIFICACIONES:
        try:
            contenido.decode(codificacion)
            return codificacion
        except UnicodeDecodeError:
            continue
    return CODIFICACIONES[-1]


def _anchos(muestra: list[str], separador: str) -> list[int]:
    filas = list(csv.reader(muestra, delimiter=separador))
    return [len(fila) for fila in filas if fila]


def detectar_separador(texto: str) -> str:
    """Elige el separador que parte el archivo de forma consistente.

    Contar caracteres no alcanza por dos motivos. Una coma dentro de un
    campo entre comillas cuenta igual que una separadora, así que un
    encabezado como `sku,"descripcion; larga"` empata y puede resolverse
    a punto y coma, fusionando columnas sin que nadie lo note. Y mirar
    solo la primera línea falla cuando el ERP antepone un título, que no
    tiene ningún separador.

    Se prueba cada candidato con el lector de CSV real sobre las primeras
    líneas y gana el que produce más filas del mismo ancho.
    """
    muestra = [linea for linea in texto.splitlines() if linea.strip()]
    muestra = muestra[:LINEAS_DE_MUESTRA]
    if not muestra:
        return ","

    mejor = ","
    mejor_puntaje = (0, 0)

    for separador in SEPARADORES:
        anchos = _anchos(muestra, separador)
        if not anchos:
            continue

        # El ancho más frecuente; ante un empate, el mayor. Sin el desempate
        # el resultado depende del orden del conjunto y no es reproducible.
        ancho_dominante = max(anchos, key=lambda ancho: (anchos.count(ancho), ancho))
        if ancho_dominante < 2:
            continue  # una sola columna: este separador no separa nada

        puntaje = (anchos.count(ancho_dominante), ancho_dominante)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            mejor = separador

    return mejor


def leer(contenido: bytes) -> tuple[list[str], list[list[str]]]:
    """Devuelve (encabezados, filas) a partir del contenido binario del archivo."""
    if not contenido.strip():
        raise ValueError("El archivo está vacío")

    texto = contenido.decode(detectar_codificacion(contenido))
    separador = detectar_separador(texto)

    lector = csv.reader(io.StringIO(texto), delimiter=separador)
    todas = []
    for i, fila in enumerate(lector):
        # Mantén la primera fila para la detección de encabezados, luego filtra vacías
        if i == 0 or any(celda.strip() for celda in fila):
            todas.append(fila)

    if not todas:
        raise ValueError("El archivo está vacío")

    # Muchos ERP anteponen un título o una fecha antes del encabezado real.
    # Se reconoce porque queda como una línea suelta sin separadores entre
    # filas que sí los tienen. Solo se saltean esas: cualquier otra
    # diferencia de ancho es un encabezado legítimo con filas irregulares,
    # y elegir por «ancho dominante» descartaría el encabezado verdadero
    # apenas la mayoría de las filas omita la última columna.
    primera = 0
    if any(len(fila) > 1 for fila in todas):
        while primera < len(todas) - 1 and len(todas[primera]) <= 1:
            primera += 1

    encabezados = [celda.strip() for celda in todas[primera]]

    # Un encabezado que termina en separador deja una columna sin nombre.
    while encabezados and not encabezados[-1]:
        encabezados.pop()

    if not encabezados:
        raise ValueError("La primera fila del archivo no tiene nombres de columna")

    vistos = set()
    for encabezado in encabezados:
        clave = encabezado.lower()
        if clave in vistos:
            raise ValueError(f"La columna «{encabezado}» está duplicada en el archivo")
        vistos.add(clave)

    cantidad = len(encabezados)
    filas = []
    for fila in todas[primera + 1:]:
        # Las filas cortas se completan; las largas se conservan enteras. Un
        # campo de más suele delatar un archivo mal armado, y descartarlo acá
        # perdería el dato en silencio. La importación lo reporta.
        completa = [celda.strip() for celda in fila]
        completa += [""] * (cantidad - len(completa))
        filas.append(completa)

    return encabezados, filas
