"""Conexion y consultas MySQL: panel de registros, empleados y registro de acceso."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError

import config

_last_db_error: str | None = None


def db_last_error() -> str | None:
    """Ultimo mensaje de error de conexion o consulta (para la barra de estado)."""
    return _last_db_error


def get_connection() -> mysql.connector.MySQLConnection | None:
    """Abre una conexion usando config (variables de entorno)."""
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


def fetch_recent_access_rows(limit: int = 30) -> list[dict[str, Any]]:
    """
    Ultimos registros de acceso para el panel lateral.
    Incluye codigo de empleado si hay JOIN (sin descifrar nombre).
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
        rows = cursor.fetchall()
        return list(rows)
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


def fetch_employees_for_recognition() -> list[dict[str, Any]]:
    """
    Empleados autorizados para cargar rostros conocidos desde disco (ruta_imagen).
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
    """
    Consulta SQL al detectar un rostro identificado: comprueba que el empleado
    siga existiendo en la tabla (permiso vigente).
    """
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


def insert_access_log(
    empleado_id: int | None,
    estado: str,
    fecha_hora: datetime | None = None,
) -> bool:
    """Inserta un evento en registro_acceso. fecha_hora opcional (microsegundos)."""
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
