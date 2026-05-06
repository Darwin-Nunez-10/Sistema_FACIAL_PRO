"""Configuracion central — lee variables del .env via python-dotenv.

Todas las credenciales viven en .env (nunca en el repositorio).
Variables requeridas:

    MYSQL_HOST        (default: localhost)
    MYSQL_PORT        (default: 3306)
    MYSQL_USER
    MYSQL_PASSWORD
    MYSQL_DATABASE    (default: facial_pro_db)

    FERNET_KEY        # Generar UNA sola vez:
                      # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
                      # GUARDAR con seguridad — sin ella los nombres cifrados son irrecuperables.

    EMAIL_SENDER      # Correo remitente (p.ej. cuenta Gmail)
    EMAIL_PASSWORD    # Contrasena de aplicacion Gmail (no la contrasena normal)
    EMAIL_RECEIVER    # Correo del encargado de seguridad
    SMTP_HOST         (default: smtp.gmail.com)
    SMTP_PORT         (default: 587)
"""

from __future__ import annotations
import os

# ── MySQL ──────────────────────────────────────────────────────────────────────
MYSQL_HOST:     str = os.getenv("MYSQL_HOST",     "localhost")
MYSQL_PORT:     int = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER:     str = os.getenv("MYSQL_USER",     "")
MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "facial_pro_db")

# ── Cifrado Fernet ─────────────────────────────────────────────────────────────
FERNET_KEY: str = os.getenv("FERNET_KEY", "")

# ── Email / alertas ────────────────────────────────────────────────────────────
EMAIL_SENDER:   str = os.getenv("EMAIL_SENDER",   "")
EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER: str = os.getenv("EMAIL_RECEIVER", "")
SMTP_HOST:      str = os.getenv("SMTP_HOST",      "smtp.gmail.com")
SMTP_PORT:      int = int(os.getenv("SMTP_PORT",  "587"))
