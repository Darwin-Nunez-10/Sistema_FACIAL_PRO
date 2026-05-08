"""Alertas sonoras y captura de evidencia de intrusos."""

import logging
import time
from datetime import datetime
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
