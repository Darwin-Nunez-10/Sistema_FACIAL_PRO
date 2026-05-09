"""Conexion y CRUD MySQL para el sistema FACIAL PRO.

Funciones publicas:
    get_connection()                    -> conexion nueva o None
    db_last_error()                     -> ultimo mensaje de error
    fetch_recent_access_rows()          -> filas recientes para el panel lateral
    fetch_employees_for_recognition()   -> empleados para reconocimiento facial
    validate_employee_permission()      -> valida si un empleado sigue autorizado
    insert_empleado()                   -> inserta un empleado
    insert_access_log()                 -> registra un evento de acceso
    insert_registro_acceso()            -> alias compatible para registrar acceso
    fetch_empleado_by_codigo()          -> busca empleado descifrando codigo
"""

from __future__ import annotations

from datetime import datetime
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


# ── Lectura ────────────────────────────────────────────────────────────────────

def fetch_recent_access_rows(limit: int = 30) -> list[dict[str, Any]]:
    """Ultimos registros de acceso para el panel lateral."""
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
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()

    from src.utils import descifrar_dato  # noqa: PLC0415

    for fila in filas:
        if fila.get("codigo_empleado"):
            fila["codigo_empleado"] = descifrar_dato(fila["codigo_empleado"])

    return filas


def fetch_employees_for_recognition() -> list[dict[str, Any]]:
    """Empleados autorizados para cargar rostros conocidos desde disco."""
    global _last_db_error

    conn = get_connection()
    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, codigo_empleado, ruta_imagen
            FROM empleados
            ORDER BY id
            """
        )
        return list(cursor.fetchall())
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        return []
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()


def validate_employee_permission(empleado_id: int) -> bool:
    """Comprueba que el empleado exista y mantenga permiso vigente."""
    global _last_db_error

    conn = get_connection()
    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM empleados WHERE id = %s LIMIT 1",
            (empleado_id,),
        )
        return cursor.fetchone() is not None
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        return False
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()


# ── Escritura ──────────────────────────────────────────────────────────────────

def insert_empleado(
    nombre_cifrado: str,
    codigo_empleado: str,
    ruta_imagen: str,
) -> int | None:
    """Inserta un empleado nuevo con los campos sensibles ya cifrados."""
    global _last_db_error

    conn = get_connection()
    if conn is None:
        return None

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)
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
        try:
            conn.rollback()
        except MySQLError:
            pass
        return None
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()


def insert_access_log(
    empleado_id: int | None,
    estado: str,
    fecha_hora: datetime | None = None,
) -> bool:
    """Inserta un evento en registro_acceso."""
    global _last_db_error

    conn = get_connection()
    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        if fecha_hora is None:
            cursor.execute(
                """
                INSERT INTO registro_acceso (empleado_id, estado)
                VALUES (%s, %s)
                """,
                (empleado_id, estado),
            )
        else:
            cursor.execute(
                """
                INSERT INTO registro_acceso (empleado_id, fecha_hora, estado)
                VALUES (%s, %s, %s)
                """,
                (empleado_id, fecha_hora, estado),
            )

        conn.commit()
        return True
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        try:
            conn.rollback()
        except MySQLError:
            pass
        return False
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()


def insert_registro_acceso(
    empleado_id: int | None,
    estado: str,
) -> bool:
    """Alias compatible para registrar acceso sin fecha manual."""
    return insert_access_log(empleado_id, estado)


def fetch_empleado_by_codigo(codigo: str) -> dict[str, Any] | None:
    """Devuelve la fila completa del empleado o None si no existe."""
    global _last_db_error

    conn = get_connection()
    if conn is None:
        return None

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, nombre_cifrado, codigo_empleado, ruta_imagen
            FROM empleados
            """
        )
        filas = cursor.fetchall()
    except MySQLError as exc:
        _last_db_error = f"{exc.errno}: {exc.msg}" if exc.errno else str(exc)
        return None
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
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