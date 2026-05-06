"""Alertas sonoras y notificaciones por correo electronico.

Funciones publicas:
    alertar_desconocido(frame_bgr, fecha_hora)
        → emite sonido + guarda imagen en data/unknown_faces/ + envia correo

Todas las credenciales se leen de config (EMAIL_SENDER, etc.).
"""

from __future__ import annotations

import smtplib
import threading
import time
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import cv2
import numpy as np

import config

_UNKNOWN_FACES = Path(__file__).resolve().parent.parent / "data" / "unknown_faces"
_UNKNOWN_FACES.mkdir(parents=True, exist_ok=True)

# Intervalo minimo entre alertas (segundos) para no saturar el correo
_ALERTA_COOLDOWN = 30.0
_ultimo_alerta: float = 0.0


# ── Punto de entrada principal ─────────────────────────────────────────────────

def alertar_desconocido(
    frame_bgr: np.ndarray,
    fecha_hora: datetime | None = None,
) -> None:
    """Dispara las tres acciones de alerta en un hilo separado para no bloquear la UI.

    1. Alerta sonora (beep del sistema).
    2. Captura del rostro guardada en data/unknown_faces/.
    3. Correo electronico al encargado de seguridad con la imagen adjunta.
    """
    global _ultimo_alerta
    ahora = time.monotonic()
    if ahora - _ultimo_alerta < _ALERTA_COOLDOWN:
        return          # cooldown activo — evitar spam
    _ultimo_alerta = ahora

    if fecha_hora is None:
        fecha_hora = datetime.now()

    # Copiar frame para no tener condicion de carrera con el hilo de captura
    frame_copia = frame_bgr.copy()

    hilo = threading.Thread(
        target=_ejecutar_alerta,
        args=(frame_copia, fecha_hora),
        daemon=True,
    )
    hilo.start()


# ── Implementacion interna ─────────────────────────────────────────────────────

def _ejecutar_alerta(frame_bgr: np.ndarray, fecha_hora: datetime) -> None:
    """Ejecutado en hilo secundario: sonido + captura + correo."""
    ruta_imagen = _guardar_captura(frame_bgr, fecha_hora)
    _emitir_sonido()
    if config.EMAIL_SENDER and config.EMAIL_RECEIVER:
        _enviar_correo(ruta_imagen, fecha_hora)
    else:
        print("[Notif] EMAIL_SENDER / EMAIL_RECEIVER no configurados — correo omitido.")


def _guardar_captura(frame_bgr: np.ndarray, fecha_hora: datetime) -> Path:
    """Guarda el frame en data/unknown_faces/ con timestamp en el nombre.
    Retorna la ruta del archivo guardado.
    """
    nombre_archivo = f"intruso_{fecha_hora.strftime('%Y%m%d_%H%M%S')}.jpg"
    ruta = _UNKNOWN_FACES / nombre_archivo
    cv2.imwrite(str(ruta), frame_bgr)
    print(f"[Notif] Captura guardada: {ruta}")
    return ruta


def _emitir_sonido() -> None:
    """Beep del sistema. Funciona en Linux, Windows y macOS."""
    try:
        # Linux con sox / beep
        import subprocess
        resultado = subprocess.run(
            ["paplay", "/usr/share/sounds/freedesktop/stereo/dialog-warning.oga"],
            capture_output=True,
            timeout=3,
        )
        if resultado.returncode != 0:
            raise RuntimeError("paplay fallo")
    except Exception:
        try:
            # Fallback universal: beep ASCII BEL
            print("\a", end="", flush=True)
        except Exception:
            pass


def _enviar_correo(ruta_imagen: Path, fecha_hora: datetime) -> None:
    """Envia correo al encargado con la captura adjunta via SMTP (TLS)."""
    asunto = f"[ALERTA SEGURIDAD] Intruso detectado — {fecha_hora.strftime('%Y-%m-%d %H:%M:%S')}"
    cuerpo = (
        f"Se ha detectado un rostro no identificado en el sistema de control de acceso.\n\n"
        f"Fecha y hora: {fecha_hora.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Imagen adjunta para revision.\n\n"
        f"-- Sistema FACIAL PRO"
    )

    msg = MIMEMultipart()
    msg["From"]    = config.EMAIL_SENDER
    msg["To"]      = config.EMAIL_RECEIVER
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    # Adjuntar imagen si existe
    if ruta_imagen.exists():
        with open(ruta_imagen, "rb") as f:
            img_data = f.read()
        adjunto = MIMEImage(img_data, name=ruta_imagen.name)
        adjunto.add_header(
            "Content-Disposition", "attachment", filename=ruta_imagen.name
        )
        msg.attach(adjunto)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            smtp.sendmail(config.EMAIL_SENDER, config.EMAIL_RECEIVER, msg.as_bytes())
        print(f"[Notif] Correo enviado a {config.EMAIL_RECEIVER}")
    except Exception as exc:
        print(f"[Notif] Error enviando correo: {exc}")
