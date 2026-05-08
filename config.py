"""Config from environment variables. Do not store real secrets in source code."""

import os
from pathlib import Path

# Project root (directory containing main.py)
PROJECT_ROOT = Path(__file__).resolve().parent

# Data paths
KNOWN_FACES_DIR = PROJECT_ROOT / "data" / "known_faces"
UNKNOWN_FACES_DIR = PROJECT_ROOT / "data" / "unknown_faces"

# MySQL (localhost -> 127.0.0.1 evita fallo con Docker en Linux: ::1 vs IPv4)
_raw_mysql_host = os.environ.get("MYSQL_HOST", "127.0.0.1").strip()
MYSQL_HOST = (
    "127.0.0.1" if _raw_mysql_host.lower() in ("localhost", "::1") else _raw_mysql_host
)
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER = os.environ.get("MYSQL_USER", "")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "facial_pro_db")

# Email (notifications)
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SECURITY_EMAIL = os.environ.get("SECURITY_EMAIL", "")

# Alertas e Intrusos
ALERT_SOUND_ENABLED = os.environ.get("ALERT_SOUND_ENABLED", "True").lower() == "true"
ALERT_SOUND_PATH = PROJECT_ROOT / "assets" / "alert.wav"
INTRUDER_COOLDOWN_SEC = float(os.environ.get("INTRUDER_COOLDOWN_SEC", "5.0"))
