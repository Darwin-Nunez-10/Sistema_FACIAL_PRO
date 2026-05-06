"""Funciones auxiliares compartidas entre modulos."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from cryptography.fernet import Fernet, InvalidToken

import config


# ── Cifrado Fernet (centralizado aqui para evitar importaciones circulares) ────

def _get_fernet() -> Fernet | None:
    """Instancia Fernet desde FERNET_KEY. Retorna None si no esta configurada."""
    key = config.FERNET_KEY
    if not key:
        print("[Utils] ADVERTENCIA: FERNET_KEY no configurada — datos sin cifrar.")
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        print(f"[Utils] FERNET_KEY invalida: {exc}")
        return None


def cifrar_dato(valor: str) -> str:
    """Cifra un string con Fernet. Sin clave devuelve texto plano."""
    f = _get_fernet()
    return f.encrypt(valor.encode()).decode() if f else valor


def descifrar_dato(token: str) -> str:
    """Descifra un token Fernet. Devuelve el token original si falla (fallback)."""
    f = _get_fernet()
    if f is None:
        return token
    try:
        return f.decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return token  # Dato no cifrado o clave incorrecta — retornar tal cual


# ── Utilidades generales ───────────────────────────────────────────────────────

def timestamp_str(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """Timestamp actual como string, util para nombres de archivo."""
    return datetime.now().strftime(fmt)


def escalar_bbox(
    bbox: tuple[int, int, int, int],
    escala: float,
) -> tuple[int, int, int, int]:
    """Escala un bounding box (top, right, bottom, left) por un factor."""
    top, right, bottom, left = bbox
    inv = 1.0 / escala
    return (
        int(top    * inv),
        int(right  * inv),
        int(bottom * inv),
        int(left   * inv),
    )


def recortar_rostro(
    frame_bgr: np.ndarray,
    bbox_original: tuple[int, int, int, int],
    margen: int = 20,
) -> np.ndarray:
    """Recorta el rostro de un frame BGR con un margen opcional."""
    h, w = frame_bgr.shape[:2]
    top, right, bottom, left = bbox_original
    t = max(0, top    - margen)
    r = min(w, right  + margen)
    b = min(h, bottom + margen)
    l = max(0, left   - margen)
    return frame_bgr[t:b, l:r].copy()


def asegurar_directorio(ruta: str | Path) -> Path:
    """Crea el directorio (y padres) si no existe. Retorna Path."""
    p = Path(ruta)
    p.mkdir(parents=True, exist_ok=True)
    return p