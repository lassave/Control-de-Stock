"""Acceso a la base SQLite: conexión y creación del esquema."""

import sqlite3
import threading
from pathlib import Path

RUTA_ESQUEMA = Path(__file__).parent / "esquema.sql"


class ConexionPorHilo:
    """Conexión SQLite con una instancia propia por hilo.

    FastAPI atiende los endpoints sincrónicos en un pool de hilos, y SQLite
    prohíbe usar una conexión desde un hilo distinto del que la creó.
    Compartir una sola conexión hace fallar el segundo pedido simultáneo:
    exactamente lo que pasa cuando dos operarios sincronizan a la vez.

    Expone la misma interfaz mínima que `sqlite3.Connection` (`execute`,
    `executescript`, `commit`, `close`), así los repositorios la usan sin
    enterarse.
    """

    def __init__(self, ruta):
        self.ruta = str(ruta)
        self._local = threading.local()

    @property
    def _conexion(self):
        conexion = getattr(self._local, "conexion", None)
        if conexion is None:
            conexion = sqlite3.connect(self.ruta)
            conexion.row_factory = sqlite3.Row
            conexion.execute("PRAGMA foreign_keys = ON")
            # Si otro hilo está escribiendo, esperar en vez de fallar con
            # "database is locked".
            conexion.execute("PRAGMA busy_timeout = 5000")
            if self.ruta != ":memory:":
                # WAL permite leer mientras otro hilo escribe: el tablero se
                # refresca solo mientras los celulares sincronizan.
                conexion.execute("PRAGMA journal_mode = WAL")
            self._local.conexion = conexion
        return conexion

    def execute(self, sql, parametros=()):
        return self._conexion.execute(sql, parametros)

    def executescript(self, script):
        return self._conexion.executescript(script)

    def commit(self):
        self._conexion.commit()

    def rollback(self):
        self._conexion.rollback()

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traza):
        """Confirma al salir bien y descarta al salir con error.

        Sin esto, una operación de dos escrituras que falla en la segunda
        deja la primera pendiente, y el commit de cualquier operación
        posterior la persiste: aparece una sesión sin pasada, que no se
        puede usar ni cerrar.
        """
        if tipo is None:
            self.commit()
        else:
            self.rollback()
        return False

    def close(self):
        conexion = getattr(self._local, "conexion", None)
        if conexion is not None:
            conexion.close()
            self._local.conexion = None


def conectar(ruta):
    """Abre la base y devuelve filas accesibles por nombre de columna.

    Con `:memory:` cada hilo tendría su propia base vacía, así que ese modo
    sirve solo para tests de un único hilo.
    """
    return ConexionPorHilo(ruta)


def crear_esquema(con):
    """Crea las tablas si no existen. Se puede ejecutar cuantas veces haga falta."""
    con.executescript(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    con.commit()
