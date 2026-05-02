"""Conexion y consultas MySQL para la interfaz (panel de registros)."""

from __future__ import annotations

from typing import Any

import mysql.connector
from mysql.connector import Error as MySQLError

import config


def get_connection() -> mysql.connector.MySQLConnection | None:
    """Abre una conexion usando config (variables de entorno)."""
    if not config.MYSQL_USER or not config.MYSQL_PASSWORD:
        return None
    try:
        return mysql.connector.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DATABASE,
        )
    except MySQLError:
        return None


def fetch_recent_access_rows(limit: int = 30) -> list[dict[str, Any]]:
    """
    Ultimos registros de acceso para el panel lateral.
    Incluye codigo de empleado si hay JOIN (sin descifrar nombre).
    """
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
    except MySQLError:
        return []
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except MySQLError:
                pass
        conn.close()
