"""Registro de conteos.

Nada se edita ni se borra: cada escaneo es una fila y una corrección es
otra fila que anula la anterior. Eso vuelve la sincronización idempotente
—reenviar es inofensivo— y deja el conteo auditable de punta a punta.
"""

from app import reloj
from app.repos import sesiones

CAMPOS_PUBLICOS = (
    "a.id, a.id_orden, a.tipo, a.material, a.sku, a.descripcion, "
    "a.grupo, a.ubicacion, a.unidad"
)

CAMPOS_REQUERIDOS = ("uuid", "codigo", "cantidad", "timestamp_dispositivo")


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
    # Se chequea la forma antes que los campos: sobre algo que no es un
    # diccionario, `.get` levanta AttributeError, que registrar_lote no
    # atrapa, y el lote entero se caería por un solo elemento mal formado.
    if not isinstance(evento, dict):
        raise EventoInvalido("El evento no es un diccionario")

    # Todo lo que falte se valida antes de tocar la base. Cualquier acceso
    # directo a una clave ausente sería un KeyError, que registrar_lote no
    # atrapa: volaría el lote entero y, como el celular reintenta el mismo
    # payload, la cola quedaría trabada para siempre.
    for campo in CAMPOS_REQUERIDOS:
        if evento.get(campo) is None:
            raise EventoInvalido(f"Al evento le falta «{campo}»")

    if not isinstance(evento["timestamp_dispositivo"], str) or \
            not evento["timestamp_dispositivo"].strip():
        raise EventoInvalido("La fecha del dispositivo llegó vacía")

    if _ya_registrado(con, evento["uuid"]):
        return "duplicado"

    cantidad = evento["cantidad"]
    if not isinstance(cantidad, int) or isinstance(cantidad, bool):
        # La columna tiene CHECK typeof = integer, así que un decimal caería
        # como IntegrityError y frenaría el lote entero.
        raise EventoInvalido("La cantidad tiene que venir en milésimas, como entero")
    if cantidad < 0:
        # Ningún escaneo produce una cantidad negativa; las correcciones van
        # por anulación.
        raise EventoInvalido("La cantidad no puede ser negativa")

    articulo = buscar_por_codigo(con, sesion_id, evento["codigo"])
    if articulo is None:
        raise EventoInvalido(f"Código desconocido: {evento['codigo']}")

    anula = evento.get("anula_uuid")
    if anula:
        original = con.execute(
            "SELECT sesion_id, articulo_id FROM conteo WHERE uuid = ?", (anula,)
        ).fetchone()
        # Se valida la sesión y no solo la existencia: un conteo de otro
        # inventario no se puede anular desde este.
        if original is None or original["sesion_id"] != sesion_id:
            # Puede ser que el conteo original todavía no haya llegado: los
            # celulares sincronizan en cualquier orden.
            raise EventoInvalido(
                f"El conteo que se intenta anular no existe: {anula}",
                reintentable=True,
            )
        if original["articulo_id"] != articulo["id"]:
            raise EventoInvalido("La anulación no corresponde a ese artículo")

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
        except (ValueError, KeyError, TypeError) as error:
            # KeyError y TypeError como red de seguridad: un evento con una
            # forma inesperada se rechaza solo, nunca frena a los demás.
            rechazados.append({
                "uuid": evento.get("uuid") if isinstance(evento, dict) else None,
                "motivo": str(error),
                "reintentable": getattr(error, "reintentable", False),
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
