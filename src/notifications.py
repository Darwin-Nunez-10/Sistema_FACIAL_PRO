"""Alertas sonoras y captura de evidencia de intrusos."""

import logging
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import config

# Intentar importar pygame para alertas sonoras
try:
    import pygame
    pygame.mixer.init()
    _SOUND_LIB_AVAILABLE = True
except ImportError:
    _SOUND_LIB_AVAILABLE = False
    logging.warning("pygame no está instalado. Las alertas sonoras estarán desactivadas.")
except Exception as e:
    _SOUND_LIB_AVAILABLE = False
    logging.error(f"Error al inicializar pygame mixer: {e}")

def play_alert_sound() -> None:
    """Reproduce el sonido de alerta si está habilitado y disponible."""
    if not config.ALERT_SOUND_ENABLED or not _SOUND_LIB_AVAILABLE:
        return
    
    sound_path = config.ALERT_SOUND_PATH
    if not sound_path.exists():
        logging.warning(f"Archivo de alerta no encontrado: {sound_path}")
        return

    try:
        # Cargar y reproducir (no bloqueante)
        pygame.mixer.music.load(str(sound_path))
        pygame.mixer.music.play()
    except Exception as e:
        logging.error(f"No se pudo reproducir el sonido de alerta: {e}")

def save_intruder_evidence(frame: np.ndarray, face_location: tuple[int, int, int, int] | None = None) -> str | None:
    """
    Guarda una captura del intruso en la carpeta de auditoría.
    Si se proporciona face_location, se puede resaltar o recortar el rostro.
    """
    try:
        # Asegurar que el directorio de salida exista
        output_dir = config.UNKNOWN_FACES_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intruso_{timestamp}.jpg"
        filepath = output_dir / filename

        # Dibujar un recuadro si se proporciona la ubicación
        image_to_save = frame.copy()
        if face_location:
            t, r, b, l = face_location
            cv2.rectangle(image_to_save, (l, t), (r, b), (0, 0, 255), 2)
            cv2.putText(image_to_save, "INTRUSO", (l, t - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        ok = cv2.imwrite(str(filepath), image_to_save)
        if ok:
            logging.info(f"Evidencia guardada: {filepath}")
            return str(filepath)
        return None
    except Exception as e:
        logging.error(f"Error al guardar evidencia del intruso: {e}")
        return None
