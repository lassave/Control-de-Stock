"""Registro de conteos.

Nada se edita ni se borra: cada escaneo es una fila y una corrección es
otra fila que anula la anterior. Eso vuelve la sincronización idempotente
—reenviar es inofensivo— y deja el conteo auditable de punta a punta.
"""

import sqlite3

from app import reloj
from app.repos import sesiones

CAMPOS_PUBLICOS = (
    "a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion, "
    "a.grupo, a.ubicacion, a.unidad"
)

# Los eventos llegan del JSON del celular, así que puede venir cualquier cosa
# en cualquier campo. Se validan los tipos completos y no solo la presencia:
# un valor no escalar (una lista, un objeto) explota recién al ligarlo a la
# consulta, como sqlite3.ProgrammingError, que no es ValueError y volaría el
# lote entero.
TEXTOS_REQUERIDOS = ("uuid", "codigo", "timestamp_dispositivo")
TEXTOS_OPCIONALES = ("anula_uuid", "ubicacion_real", "observaciones")

# El mayor entero que SQLite guarda. Los de JSON no tienen tope.
MAXIMO_ENTERO = 2 ** 63 - 1


class EventoInvalido(ValueError):
    """Un evento que no se pudo registrar.

    `reintentable` distingue el que podría funcionar más tarde —una anulación
    que llegó antes que el conteo que anula, porque los celulares sincronizan
    en cualquier orden— del que nunca va a funcionar. Sin esa distinción el
    celular no sabe si conservar el evento o descartarlo.
    """

    def __init__(self, motivo, reintentable=False):
        super().__init__(motivo)
        self.reintentable = reintentable


def buscar_por_codigo(con, sesion_id, codigo):
    """Busca el artículo por código de barras.

    Devuelve solo campos que pueden viajar a un dispositivo: sin
    stock_sistema ni costo_unitario, por el conteo a ciegas.
    """
    fila = con.execute(
        f"""
        SELECT {CAMPOS_PUBLICOS}
        FROM codigo_barras cb
        JOIN articulo a ON a.id = cb.articulo_id
        WHERE cb.codigo = ? AND a.sesion_id = ? AND a.fusionado_en IS NULL
        ORDER BY a.id
        LIMIT 1
        """,
        (codigo, sesion_id),
    ).fetchone()
    return dict(fila) if fila else None


def _ya_registrado(con, uuid):
    return con.execute(
        "SELECT 1 FROM conteo WHERE uuid = ?", (uuid,)
    ).fetchone() is not None


def registrar(con, sesion_id, operario_id, evento):
    """Registra un conteo. Devuelve 'registrado' o 'duplicado'.

    Reenviar un uuid ya recibido no es un error: es lo que hace el celular
    cuando no le llegó la confirmación.
    """
    # Se verifica el tipo antes que nada: sobre algo que no es un diccionario,
    # `.get` lanzaría AttributeError, que registrar_lote no atrapa, y el lote
    # volaría igual. Además así el motivo del rechazo queda en castellano y no
    # con el texto en inglés de la excepción.
    if not isinstance(evento, dict):
        raise EventoInvalido("El evento no tiene el formato esperado")

    # Todo se valida antes de tocar la base. Una clave ausente sería KeyError
    # y un valor no escalar sería sqlite3.ProgrammingError al ligarlo a la
    # consulta: los dos volarían el lote entero y, como el celular reintenta
    # el mismo payload, la cola quedaría trabada para siempre.
    for campo in TEXTOS_REQUERIDOS:
        valor = evento.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise EventoInvalido(f"«{campo}» tiene que ser un texto con contenido")

    for campo in TEXTOS_OPCIONALES:
        valor = evento.get(campo)
        if valor is not None and not isinstance(valor, str):
            raise EventoInvalido(f"«{campo}» tiene que ser un texto")

    if _ya_registrado(con, evento["uuid"]):
        return "duplicado"

    cantidad = evento.get("cantidad")
    if not isinstance(cantidad, int) or isinstance(cantidad, bool):
        # La columna tiene CHECK typeof = integer, así que un decimal caería
        # como IntegrityError y frenaría el lote entero.
        raise EventoInvalido("La cantidad tiene que venir en milésimas, como entero")
    if cantidad < 0:
        # Ningún escaneo produce una cantidad negativa; las correcciones van
        # por anulación.
        raise EventoInvalido("La cantidad no puede ser negativa")
    if cantidad > MAXIMO_ENTERO:
        # Los enteros de JSON no tienen límite, pero los de SQLite sí: uno
        # más grande explota como OverflowError al ligarlo, que no es
        # ValueError ni sqlite3.Error, y volaría el lote entero.
        raise EventoInvalido("La cantidad es demasiado grande")

    articulo = buscar_por_codigo(con, sesion_id, evento["codigo"])
    if articulo is None:
        raise EventoInvalido(f"Código desconocido: {evento['codigo']}")

    # Un anula_uuid vacío es «sin anulación», no una anulación rota: si se
    # dejara pasar, lo rechazaría la clave foránea y el motivo que llegaría al
    # celular sería el texto en inglés de SQLite.
    anula = evento.get("anula_uuid") or None
    if anula == evento["uuid"]:
        # Nunca va a poder cumplirse: la única fila que lo satisfaría es la
        # que se está rechazando. Marcarlo reintentable lo dejaría dando
        # vueltas para siempre.
        raise EventoInvalido("Un conteo no puede anularse a sí mismo")
    if anula:
        original = con.execute(
            "SELECT sesion_id, articulo_id, anula_uuid FROM conteo WHERE uuid = ?",
            (anula,),
        ).fetchone()

        if original is None:
            # Puede ser que el conteo original todavía no haya llegado: los
            # celulares sincronizan en cualquier orden, así que conviene
            # reintentarlo más tarde en vez de descartarlo.
            raise EventoInvalido(
                f"Todavía no llegó el conteo que se intenta anular: {anula}",
                reintentable=True,
            )
        if original["sesion_id"] != sesion_id:
            # El uuid es único en toda la base, así que un conteo de otro
            # inventario nunca va a pasar a ser de este: reintentar no sirve.
            raise EventoInvalido(
                f"El conteo que se intenta anular es de otro inventario: {anula}"
            )
        if original["articulo_id"] != articulo["id"]:
            raise EventoInvalido("La anulación no corresponde a ese artículo")
        if original["anula_uuid"] is not None:
            # Anular una anulación dejaría al conteo original excluido por una
            # fila que ya no vale, y el artículo volvería a figurar sin contar:
            # se perderían unidades que alguien sí contó. Para deshacer una
            # anulación se carga el conteo de nuevo.
            raise EventoInvalido("Una anulación no se puede anular")

    pasada = sesiones.pasada_abierta(con, sesion_id)

    con.execute(
        """
        INSERT INTO conteo (
            uuid, sesion_id, pasada_id, articulo_id, cantidad, operario_id,
            ubicacion_real, observaciones, fuera_asignacion,
            timestamp_dispositivo, timestamp_servidor, anula_uuid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            evento["uuid"], sesion_id, pasada["id"], articulo["id"],
            cantidad, operario_id,
            evento.get("ubicacion_real"), evento.get("observaciones"),
            evento["timestamp_dispositivo"], reloj.ahora(), anula,
        ),
    )
    con.commit()
    return "registrado"


def registrar_lote(con, sesion_id, operario_id, eventos):
    """Registra varios conteos. Un evento con problema no frena a los demás."""
    registrados = 0
    duplicados = 0
    rechazados = []

    for evento in eventos:
        try:
            resultado = registrar(con, sesion_id, operario_id, evento)
        except (ValueError, KeyError, TypeError, ArithmeticError, sqlite3.Error) as error:
            # La tupla es amplia a propósito: un evento con una forma
            # inesperada tiene que rechazarse solo, nunca frenar a los demás.
            # Perder un lote entero le cuesta al operario media jornada.
            reintentable = getattr(error, "reintentable", False)

            if isinstance(error, sqlite3.OperationalError):
                # «database is locked» y parientes son transitorios: pasan
                # cuando dos operarios sincronizan a la vez, que es para lo
                # que está el busy_timeout. Decirle al celular que no
                # reintente sería descartar un conteo que sí se hizo.
                reintentable = True

            rechazados.append({
                "uuid": evento.get("uuid") if isinstance(evento, dict) else None,
                "motivo": str(error),
                "reintentable": reintentable,
            })
            continue

        if resultado == "registrado":
            registrados += 1
        else:
            duplicados += 1

    return {
        "registrados": registrados,
        "duplicados": duplicados,
        "rechazados": rechazados,
    }


def de_operario(con, sesion_id, operario_id, limite=50):
    """Los conteos propios del operario, del más reciente al más viejo."""
    filas = con.execute(
        """
        SELECT c.uuid, c.cantidad, c.ubicacion_real, c.observaciones,
               c.timestamp_dispositivo, c.anula_uuid,
               a.sku, a.descripcion, a.unidad, a.ubicacion
        FROM conteo c
        JOIN articulo a ON a.id = c.articulo_id
        WHERE c.sesion_id = ? AND c.operario_id = ?
        ORDER BY c.rowid DESC
        LIMIT ?
        """,
        (sesion_id, operario_id, limite),
    ).fetchall()
    return [dict(fila) for fila in filas]
