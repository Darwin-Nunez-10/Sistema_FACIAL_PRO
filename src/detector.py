"""Detecci?n de rostros, reconocimiento contra empleados en MySQL y utilidades."""

from __future__ import annotations

from pathlib import Path

import face_recognition
import numpy as np

import config
from src.database import fetch_employees_for_recognition


def resolve_face_image_path(ruta_imagen: str) -> Path:
    p = Path(ruta_imagen.strip())
    if p.is_absolute():
        return p
    return config.PROJECT_ROOT / p


def build_known_encodings_from_db() -> tuple[list[int], list[np.ndarray]]:
    """
    Lee empleados desde MySQL y genera encodings a partir de ruta_imagen.
    Omite filas sin archivo o sin rostro detectable en la imagen.
    """
    rows = fetch_employees_for_recognition()
    ids: list[int] = []
    encodings: list[np.ndarray] = []
    for row in rows:
        path = resolve_face_image_path(str(row["ruta_imagen"]))
        if not path.is_file():
            continue
        try:
            image = face_recognition.load_image_file(str(path))
        except OSError:
            continue
        found = face_recognition.face_encodings(image)
        if not found:
            continue
        ids.append(int(row["id"]))
        encodings.append(found[0])
    return ids, encodings


def best_match_employee_id(
    face_encoding: np.ndarray,
    known_ids: list[int],
    known_encodings: list[np.ndarray],
    tolerance: float = 0.6,
) -> int | None:
    """Devuelve el id de empleado con menor distancia si est? por debajo del umbral."""
    if not known_encodings:
        return None
    distances = face_recognition.face_distance(known_encodings, face_encoding)
    idx = int(np.argmin(distances))
    if float(distances[idx]) <= tolerance:
        return int(known_ids[idx])
    return None
