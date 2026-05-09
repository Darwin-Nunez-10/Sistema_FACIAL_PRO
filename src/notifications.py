"""Alertas sonoras, captura de evidencia y notificaciones por correo de intrusos."""

import logging
import smtplib
import threading
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import cv2
import numpy as np

import config

# Configuración de logging básica
logging.basicConfig(level=logging.INFO)

# Intentar importar pygame para alertas sonoras
_SOUND_LIB_AVAILABLE = False
_ALERT_SOUND = None

try:
    import pygame
    pygame.mixer.init()
    _SOUND_LIB_AVAILABLE = True
    
    # Pre-cargar el sonido si existe para mayor rapidez
    if config.ALERT_SOUND_PATH.exists():
        _ALERT_SOUND = pygame.mixer.Sound(str(config.ALERT_SOUND_PATH))
        logging.info("Sistema de audio iniciado y sonido de alerta cargado.")
    else:
        logging.warning(f"Archivo de audio no encontrado en la precarga: {config.ALERT_SOUND_PATH}")
except ImportError:
    logging.warning("pygame no está instalado. Las alertas sonoras estarán desactivadas.")
except Exception as e:
    logging.error(f"Error al inicializar el sistema de audio: {e}")

def play_alert_sound() -> None:
    """Reproduce el sonido de alerta de forma inmediata."""
    global _ALERT_SOUND
    
    if not config.ALERT_SOUND_ENABLED or not _SOUND_LIB_AVAILABLE:
        return
    
    try:
        # Si no se cargó al inicio, intentar cargarlo ahora
        if _ALERT_SOUND is None:
            if config.ALERT_SOUND_PATH.exists():
                _ALERT_SOUND = pygame.mixer.Sound(str(config.ALERT_SOUND_PATH))
            else:
                logging.error(f"No se pudo reproducir: archivo no existe {config.ALERT_SOUND_PATH}")
                return

        # Reproducir sonido
        _ALERT_SOUND.play()
        logging.info("Reproduciendo alerta sonora...")
    except Exception as e:
        logging.error(f"Error al reproducir sonido: {e}")

def save_intruder_evidence(frame: np.ndarray, face_location: tuple[int, int, int, int] | None = None) -> str | None:
    """Guarda una captura del intruso en la carpeta de auditoría."""
    try:
        output_dir = config.UNKNOWN_FACES_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intruso_{timestamp}.jpg"
        filepath = output_dir / filename

        image_to_save = frame.copy()
        if face_location:
            t, r, b, l = face_location
            # Dibujar recuadro y texto de advertencia
            cv2.rectangle(image_to_save, (l, t), (r, b), (0, 0, 255), 3)
            cv2.putText(image_to_save, "ALERTA: INTRUSO", (l, t - 15), 
                        cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 0, 255), 2)

        ok = cv2.imwrite(str(filepath), image_to_save)
        if ok:
            logging.info(f"Evidencia guardada exitosamente: {filepath}")
            return str(filepath)
        return None
    except Exception as e:
        logging.error(f"Error crítico al guardar evidencia: {e}")
        return None


def send_intruder_alert_email(image_path: str | None, event_dt: datetime) -> None:
    """Envía correo de alerta con la foto del intruso en un thread secundario."""
    if not all([config.SMTP_HOST, config.SMTP_USER, config.SMTP_PASSWORD, config.SECURITY_EMAIL]):
        logging.warning("Credenciales SMTP incompletas en .env — correo de alerta omitido.")
        return
    threading.Thread(
        target=_email_worker,
        args=(image_path, event_dt),
        daemon=True,
    ).start()


def _email_worker(image_path: str | None, event_dt: datetime) -> None:
    dt_str = event_dt.strftime("%Y-%m-%d %H:%M:%S")
    try:
        msg = MIMEMultipart()
        msg["From"] = config.SMTP_USER
        msg["To"] = config.SECURITY_EMAIL
        msg["Subject"] = f"ALERTA: Acceso no autorizado — {dt_str}"

        msg.attach(MIMEText(
            f"Se detectó un intento de acceso no autorizado.\n\n"
            f"Fecha y hora: {dt_str}\n"
            f"Se adjunta la fotografía capturada por el sistema.\n\n"
            f"— Sistema FACIAL PRO",
            "plain",
        ))

        if image_path and Path(image_path).is_file():
            with open(image_path, "rb") as f:
                part = MIMEBase("image", "jpeg")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{Path(image_path).name}"',
            )
            msg.attach(part)

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_USER, config.SECURITY_EMAIL, msg.as_string())

        logging.info(f"Correo de alerta enviado a {config.SECURITY_EMAIL}")
    except Exception as e:
        logging.error(f"Error al enviar correo de alerta: {e}")
