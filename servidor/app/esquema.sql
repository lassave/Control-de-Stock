PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sesion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    fecha_creacion      TEXT NOT NULL,
    estado              TEXT NOT NULL DEFAULT 'abierta',
    tolerancia_pct      REAL NOT NULL DEFAULT 2.0,
    tolerancia_min_abs  INTEGER NOT NULL DEFAULT 1000,
    CHECK (estado IN ('abierta', 'cerrada')),
    CHECK (typeof(tolerancia_min_abs) = 'integer')
);

-- Una sola sesión abierta a la vez: los dispositivos se vinculan a «la»
-- sesión abierta. El repositorio ya lo valida, pero dos hilos pueden pasar
-- esa validación a la vez; este índice lo vuelve imposible.
CREATE UNIQUE INDEX IF NOT EXISTS ix_sesion_abierta
    ON sesion(estado) WHERE estado = 'abierta';

CREATE TABLE IF NOT EXISTS pasada (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id       INTEGER NOT NULL REFERENCES sesion(id),
    numero          INTEGER NOT NULL,
    estado          TEXT NOT NULL DEFAULT 'abierta',
    fecha_apertura  TEXT NOT NULL,
    fecha_cierre    TEXT,
    abierta_por     TEXT,
    cerrada_por     TEXT,
    UNIQUE (sesion_id, numero),
    CHECK (estado IN ('abierta', 'cerrada'))
);

CREATE TABLE IF NOT EXISTS unidad (
    codigo            TEXT PRIMARY KEY,
    nombre            TEXT NOT NULL,
    admite_decimales  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS articulo (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id       INTEGER NOT NULL REFERENCES sesion(id),
    id_orden        INTEGER NOT NULL,
    tipo            TEXT,
    material        TEXT,
    sku             TEXT NOT NULL,
    descripcion     TEXT NOT NULL,
    grupo           TEXT,
    ubicacion       TEXT,
    unidad          TEXT NOT NULL DEFAULT 'UN' REFERENCES unidad(codigo),
    stock_sistema   INTEGER NOT NULL DEFAULT 0,
    costo_unitario  INTEGER,
    origen          TEXT NOT NULL DEFAULT 'importado',
    ausente_erp     INTEGER NOT NULL DEFAULT 0,
    creado_por      TEXT,
    creado_en       TEXT NOT NULL,
    fusionado_en    INTEGER REFERENCES articulo(id),
    UNIQUE (sesion_id, sku),
    CHECK (origen IN ('importado', 'alta_rapida')),
    -- La afinidad INTEGER de SQLite no es una restricción de tipo: acepta y
    -- guarda un 3.5 como REAL. Sin este CHECK, un solo decimal colado anula
    -- en silencio la exactitud que justifica guardar milésimas y centavos.
    CHECK (typeof(stock_sistema) = 'integer'),
    CHECK (costo_unitario IS NULL OR typeof(costo_unitario) = 'integer')
);

CREATE TABLE IF NOT EXISTS codigo_barras (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    articulo_id  INTEGER NOT NULL REFERENCES articulo(id),
    codigo       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_codigo_barras_codigo ON codigo_barras(codigo);

CREATE TABLE IF NOT EXISTS operario (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL UNIQUE,
    pin               TEXT,
    token_dispositivo TEXT NOT NULL UNIQUE,
    activo            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS conteo (
    uuid                    TEXT PRIMARY KEY,
    sesion_id               INTEGER NOT NULL REFERENCES sesion(id),
    pasada_id               INTEGER NOT NULL REFERENCES pasada(id),
    articulo_id             INTEGER NOT NULL REFERENCES articulo(id),
    cantidad                INTEGER NOT NULL,
    operario_id             INTEGER NOT NULL REFERENCES operario(id),
    ubicacion_real          TEXT,
    observaciones           TEXT,
    fuera_asignacion        INTEGER NOT NULL DEFAULT 0,
    timestamp_dispositivo   TEXT NOT NULL,
    timestamp_servidor      TEXT NOT NULL,
    anula_uuid              TEXT REFERENCES conteo(uuid),
    CHECK (typeof(cantidad) = 'integer')
);

CREATE INDEX IF NOT EXISTS ix_conteo_articulo ON conteo(articulo_id, pasada_id);
CREATE INDEX IF NOT EXISTS ix_conteo_anula ON conteo(anula_uuid);
CREATE INDEX IF NOT EXISTS ix_conteo_sesion ON conteo(sesion_id, operario_id);

CREATE TABLE IF NOT EXISTS pasada_item (
    pasada_id    INTEGER NOT NULL REFERENCES pasada(id),
    articulo_id  INTEGER NOT NULL REFERENCES articulo(id),
    PRIMARY KEY (pasada_id, articulo_id)
);

CREATE TABLE IF NOT EXISTS asignacion (
    pasada_id         INTEGER NOT NULL REFERENCES pasada(id),
    operario_id       INTEGER NOT NULL REFERENCES operario(id),
    ubicacion         TEXT NOT NULL,
    fecha_asignacion  TEXT NOT NULL,
    PRIMARY KEY (pasada_id, operario_id, ubicacion)
);

CREATE TABLE IF NOT EXISTS mapeo_columnas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE,
    definicion_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS codigo_aprendido (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sku               TEXT NOT NULL,
    codigo            TEXT NOT NULL,
    fecha             TEXT NOT NULL,
    sesion_origen_id  INTEGER REFERENCES sesion(id),
    UNIQUE (sku, codigo)
);

CREATE TABLE IF NOT EXISTS evento_auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id       INTEGER REFERENCES sesion(id),
    fecha           TEXT NOT NULL,
    autor           TEXT NOT NULL,
    accion          TEXT NOT NULL,
    entidad         TEXT,
    entidad_id      TEXT,
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    detalle         TEXT
);

-- Cuentas para entrar al panel. Separadas de `operario` a propósito: son
-- dos identidades sin relación entre sí, y compartir tabla o vocabulario
-- las confundiría la primera vez que alguien lea el esquema.
--
-- Hay exactamente un superusuario, para siempre: se crea a mano, directo
-- contra la base, nunca a través de un endpoint. Las cuentas de rol
-- `menor` no tienen segundo factor —el login no lo pide para nadie, y
-- ellas se recuperan por mail, no por TOTP— así que `otp_secreto` es
-- opcional.
CREATE TABLE IF NOT EXISTS cuenta_panel (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario     TEXT NOT NULL,
    clave_hash  TEXT NOT NULL,
    otp_secreto TEXT,
    activo      INTEGER NOT NULL DEFAULT 1,
    rol         TEXT NOT NULL DEFAULT 'menor' CHECK (rol IN ('superusuario', 'menor'))
);

-- Única solo entre cuentas activas: como `desactivar()` es una baja
-- lógica (nunca se borra la fila), esto permite recrear una cuenta con
-- el mismo usuario después de darla de baja —es el único camino de
-- recuperación de un OTP perdido.
CREATE UNIQUE INDEX IF NOT EXISTS cuenta_panel_usuario_activo
    ON cuenta_panel(usuario) WHERE activo = 1;

CREATE TABLE IF NOT EXISTS sesion_panel (
    token      TEXT PRIMARY KEY,
    cuenta_id  INTEGER NOT NULL REFERENCES cuenta_panel(id),
    creado_en  TEXT NOT NULL,
    -- Con "Recordarme" tildado: la sesión no vence por tiempo, solo con
    -- un logout explícito. `sesion_valida()` no revisa el vencimiento
    -- de estas filas.
    recordar   INTEGER NOT NULL DEFAULT 0
);

-- Un código de recuperación por cuenta: pedir uno nuevo reemplaza al
-- anterior, no lo acumula. Solo lo usan las cuentas de rol `menor`
-- —el superusuario recupera con el TOTP que ya tiene, sin necesitar
-- esta tabla—.
CREATE TABLE IF NOT EXISTS codigo_recuperacion (
    cuenta_id   INTEGER PRIMARY KEY REFERENCES cuenta_panel(id),
    codigo_hash TEXT NOT NULL,
    creado_en   TEXT NOT NULL
);

INSERT OR IGNORE INTO unidad (codigo, nombre, admite_decimales) VALUES
    ('UN',   'Unidad',      0),
    ('CJ',   'Caja',        0),
    ('PACK', 'Pack',        0),
    ('KG',   'Kilogramo',   1),
    ('GR',   'Gramo',       1),
    ('LT',   'Litro',       1),
    ('ML',   'Mililitro',   1),
    ('MT',   'Metro',       1);
