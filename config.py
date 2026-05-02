"""Configuración desde variables de entorno. No almacene secretos en el código."""

import os
from pathlib import Path

# Raíz del proyecto (directorio que contiene main.py)
PROJECT_ROOT = Path(__file__).resolve().parent

# Rutas de datos
KNOWN_FACES_DIR = PROJECT_ROOT / "data" / "known_faces"
UNKNOWN_FACES_DIR = PROJECT_ROOT / "data" / "unknown_faces"

# MySQL
MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "facial_pro_db")

# Correo (notificaciones)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SECURITY_EMAIL = os.environ.get("SECURITY_EMAIL", "")
