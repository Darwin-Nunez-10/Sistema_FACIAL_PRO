"""Conexion y CRUD MySQL para el sistema FACIAL PRO.

Funciones publicas:
    get_connection()              → conexion nueva o None
    db_last_error()               → ultimo mensaje de error
    fetch_recent_access_rows()    → filas para el panel lateral (SELECT)
    insert_empleado()             → agrega o recupera un empleado (INSERT/SELECT)
    insert_registro_acceso()      → registra un evento de acceso (INSERT)
    fetch_empleado_by_codigo()    → busca empleado descifrando codigo en Python
"""

from __future__ import annotations

from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError

import config

_last_db_error: str | None = None


# ── Conexion ───────────────────────────────────────────────────────────────────

def db_last_error() -> str | None:
    return _last_db_error


def get_connection() -> mysql.connector.MySQLConnection | None:
    global _last_db_error
    _last_db_error = None
    if not config.MYSQL_USER or not config.MYSQL_PASSWORD:
        _last_db_error = "Faltan MYSQL_USER o MYSQL_PASSWORD en .env"
        return None
    try:
        return mysql.connector.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
        )
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        return None


# ── Lectura (panel lateral) ────────────────────────────────────────────────────

def fetch_recent_access_rows(limit: int = 30) -> list[dict[str, Any]]:
    """Ultimos registros de acceso para el panel lateral.

    NOTA: codigo_empleado se almacena cifrado; se descifra aqui antes de
    devolver las filas para que la GUI pueda mostrarlo en texto plano.
    """
    global _last_db_error
    conn = get_connection()
    if conn is None:
        return []
    cursor = None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                r.id,
                r.empleado_id,
                r.fecha_hora,
                r.estado,
                e.codigo_empleado
            FROM registro_acceso r
            LEFT JOIN empleados e ON e.id = r.empleado_id
            ORDER BY r.fecha_hora DESC
            LIMIT %s
            """,
            (limit,),
        )
        filas = list(cursor.fetchall())
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        return []
    finally:
        if cursor:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()

    # Descifrar codigo_empleado para mostrarlo legible en la GUI
    from src.utils import descifrar_dato  # noqa: PLC0415
    for fila in filas:
        if fila.get("codigo_empleado"):
            fila["codigo_empleado"] = descifrar_dato(fila["codigo_empleado"])
    return filas


# ── Escritura ──────────────────────────────────────────────────────────────────

def insert_empleado(
    nombre_cifrado: str,
    codigo_empleado: str,   # ya llega cifrado desde detector.py
    ruta_imagen: str,       # ya llega cifrada desde detector.py
) -> int | None:
    """Inserta un empleado nuevo.

    Los tres campos sensibles (nombre_cifrado, codigo_empleado, ruta_imagen)
    llegan ya cifrados desde detector._sincronizar_empleado().
    Como el codigo se cifra con Fernet (no determinista), la busqueda de
    duplicados se realiza en fetch_empleado_by_codigo() descifrando en Python.
    """
    global _last_db_error
    conn = get_connection()
    if conn is None:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO empleados (nombre_cifrado, codigo_empleado, ruta_imagen)
            VALUES (%s, %s, %s)
            """,
            (nombre_cifrado, codigo_empleado, ruta_imagen),
        )
        conn.commit()
        return cursor.lastrowid
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def insert_registro_acceso(
    empleado_id: int | None,
    estado: str,
) -> bool:
    """Inserta una fila en registro_acceso."""
    global _last_db_error
    conn = get_connection()
    if conn is None:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO registro_acceso (empleado_id, estado) VALUES (%s, %s)",
            (empleado_id, estado),
        )
        conn.commit()
        return True
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def fetch_empleado_by_codigo(codigo: str) -> dict[str, Any] | None:
    """Devuelve la fila completa del empleado o None si no existe.

    Como codigo_empleado se almacena cifrado con Fernet (token no determinista),
    no se puede comparar directamente en SQL.  Se traen todas las filas y se
    descifra en Python para encontrar la coincidencia.
    """
    global _last_db_error
    conn = get_connection()
    if conn is None:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, nombre_cifrado, codigo_empleado, ruta_imagen FROM empleados"
        )
        filas = cursor.fetchall()
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        return None
    finally:
        cursor.close()
        conn.close()

    from src.utils import descifrar_dato  # noqa: PLC0415
    for fila in filas:
        try:
            codigo_plain = descifrar_dato(fila["codigo_empleado"])
        except Exception:
            codigo_plain = fila["codigo_empleado"]
        if codigo_plain == codigo:
            return fila
    return None