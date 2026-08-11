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
    if _ya_registrado(con, evento["uuid"]):
        return "duplicado"

    anula = evento.get("anula_uuid")
    if anula and not _ya_registrado(con, anula):
        raise ValueError(f"El conteo que se intenta anular no existe: {anula}")

    articulo = buscar_por_codigo(con, sesion_id, evento["codigo"])
    if articulo is None:
        raise ValueError(f"Código desconocido: {evento['codigo']}")

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
            evento["cantidad"], operario_id,
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
        except ValueError as error:
            rechazados.append({"uuid": evento.get("uuid"), "motivo": str(error)})
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
