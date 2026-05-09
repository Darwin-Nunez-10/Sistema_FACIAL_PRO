"""Logica de reconocimiento facial, cifrado de datos sensibles y carga desde MySQL.

Responsabilidades:
  - Cargar encodings desde data/known_faces/<codigo_empleado>.<ext>.
  - Sincronizar empleados locales con MySQL usando campos sensibles cifrados.
  - Cargar empleados ya registrados desde MySQL para reconocimiento.
  - Comparar rostros contra encodings conocidos.
  - Delegar persistencia a src.database.
  - Delegar cifrado/descifrado a src.utils.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import face_recognition
import numpy as np

import config
from src.database import (
    db_last_error,
    fetch_empleado_by_codigo,
    fetch_employees_for_recognition,
    insert_empleado,
    insert_registro_acceso,
)
from src.utils import cifrar_dato, descifrar_dato

# Alias semanticos para mayor claridad en este modulo
cifrar_nombre = cifrar_dato
descifrar_nombre = descifrar_dato

# ── Constantes ─────────────────────────────────────────────────────────────────

_TOLERANCE = 0.50
_KNOWN_FACES = Path(__file__).resolve().parent.parent / "data" / "known_faces"
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ── Utilidades de carga desde MySQL ────────────────────────────────────────────

def _safe_descifrar_dato(valor: str) -> str:
    """Devuelve el dato descifrado si aplica; si no, devuelve el valor original."""
    try:
        return descifrar_dato(valor)
    except Exception:
        return valor


def resolve_face_image_path(ruta_imagen: str) -> Path:
    """Resuelve una ruta de imagen absoluta o relativa al proyecto."""
    ruta_plain = _safe_descifrar_dato(ruta_imagen)
    path = Path(ruta_plain.strip())

    if path.is_absolute():
        return path

    return config.PROJECT_ROOT / path


def build_known_encodings_from_db() -> tuple[list[int], list[np.ndarray]]:
    """Lee empleados desde MySQL y genera encodings desde ruta_imagen."""
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
    tolerance: float = _TOLERANCE,
) -> int | None:
    """Devuelve el id del empleado con menor distancia si cumple el umbral."""
    if not known_encodings:
        return None

    distances = face_recognition.face_distance(known_encodings, face_encoding)
    idx = int(np.argmin(distances))

    if float(distances[idx]) <= tolerance:
        return int(known_ids[idx])

    return None


# ── Motor de reconocimiento ────────────────────────────────────────────────────

class FaceDetector:
    """Motor de reconocimiento facial con respaldo en MySQL."""

    def __init__(self) -> None:
        self._conocidos: dict[int, tuple[str, np.ndarray]] = {}
        self.cargar_diccionario()

    # ── Carga del diccionario ──────────────────────────────────────────────────

    def cargar_diccionario(self) -> int:
        """Lee data/known_faces/ y sincroniza empleados con MySQL."""
        self._conocidos.clear()

        if not _KNOWN_FACES.exists():
            print(f"[Detector] Carpeta not found: {_KNOWN_FACES}")
            return 0

        imagenes = [
            path for path in _KNOWN_FACES.iterdir()
            if path.suffix.lower() in _IMG_EXTS
        ]

        if not imagenes:
            print("[Detector] Sin imagenes en known_faces/ — diccionario vacio.")
            return 0

        cargados = 0

        for ruta in sorted(imagenes):
            codigo = ruta.stem

            try:
                img = face_recognition.load_image_file(str(ruta))
                encs = face_recognition.face_encodings(img)

                if not encs:
                    print(f"[Detector] Sin rostro detectado en {ruta.name} — omitido.")
                    continue

                encoding = encs[0]
            except Exception as exc:
                print(f"[Detector] Error leyendo {ruta.name}: {exc}")
                continue

            emp_id, nombre_plain = self._sincronizar_empleado(codigo, str(ruta))

            if emp_id is None:
                print(f"[Detector] No se pudo sincronizar {codigo} con MySQL.")
                continue

            self._conocidos[emp_id] = (nombre_plain, encoding)
            cargados += 1

            print(f"[Detector] OK  {ruta.name}  →  emp_id={emp_id}  nombre={nombre_plain}")

        print(f"[Detector] Diccionario listo: {cargados} rostro(s).")
        return cargados

    def cargar_diccionario_desde_db(self) -> int:
        """Carga rostros usando empleados registrados en MySQL."""
        self._conocidos.clear()

        rows = fetch_employees_for_recognition()
        cargados = 0

        for row in rows:
            emp_id = int(row["id"])
            codigo_plain = _safe_descifrar_dato(str(row["codigo_empleado"]))
            path = resolve_face_image_path(str(row["ruta_imagen"]))

            if not path.is_file():
                print(f"[Detector] Imagen no encontrada para empleado {emp_id}: {path}")
                continue

            try:
                image = face_recognition.load_image_file(str(path))
                encodings = face_recognition.face_encodings(image)

                if not encodings:
                    print(f"[Detector] Sin rostro detectado en {path.name} — omitido.")
                    continue
            except Exception as exc:
                print(f"[Detector] Error leyendo {path.name}: {exc}")
                continue

            self._conocidos[emp_id] = (codigo_plain, encodings[0])
            cargados += 1

        print(f"[Detector] Diccionario DB listo: {cargados} rostro(s).")
        return cargados

    def _sincronizar_empleado(
        self,
        codigo: str,
        ruta_imagen: str,
    ) -> tuple[int | None, str]:
        """Busca el empleado por codigo o lo inserta con datos cifrados."""
        fila = fetch_empleado_by_codigo(codigo)

        if fila:
            nombre_plain = descifrar_dato(fila["nombre_cifrado"])
            return int(fila["id"]), nombre_plain

        nombre_cifrado = cifrar_dato(codigo)
        codigo_cifrado = cifrar_dato(codigo)
        ruta_cifrada = cifrar_dato(ruta_imagen)

        emp_id = insert_empleado(nombre_cifrado, codigo_cifrado, ruta_cifrada)

        if emp_id is None:
            print(f"[Detector] insert_empleado fallo: {db_last_error()}")
            return None, codigo

        print(f"[Detector] Empleado nuevo insertado: {codigo} → id={emp_id}")
        return emp_id, codigo

    # ── Procesamiento de frame ─────────────────────────────────────────────────

    def procesar_frame(self, frame_rgb: np.ndarray) -> list[dict[str, Any]]:
        """Detecta y reconoce rostros en un frame RGB."""
        if frame_rgb is None or frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return []

        frame_rgb = np.ascontiguousarray(frame_rgb, dtype=np.uint8)

        ubicaciones = face_recognition.face_locations(frame_rgb, model="hog")

        if not ubicaciones:
            return []

        encodings = face_recognition.face_encodings(frame_rgb, ubicaciones)
        resultados: list[dict[str, Any]] = []

        for encoding, bbox in zip(encodings, ubicaciones):
            nombre, emp_id, estado = self._identificar(encoding)

            resultados.append(
                {
                    "nombre": nombre,
                    "emp_id": emp_id,
                    "estado": estado,
                    "bbox": bbox,
                    "encoding": encoding,
                }
            )

            insert_registro_acceso(emp_id, estado)

        return resultados

    def _identificar(
        self,
        encoding: np.ndarray,
    ) -> tuple[str, int | None, str]:
        """Compara un encoding contra el diccionario en memoria."""
        if not self._conocidos:
            return "Desconocido", None, "no_identificado"

        ids = list(self._conocidos.keys())
        vectores = [self._conocidos[emp_id][1] for emp_id in ids]

        emp_id = best_match_employee_id(
            face_encoding=encoding,
            known_ids=ids,
            known_encodings=vectores,
            tolerance=_TOLERANCE,
        )

        if emp_id is not None:
            return self._conocidos[emp_id][0], emp_id, "permitido"

        return "Desconocido", None, "no_identificado"

    # ── Utilidades ─────────────────────────────────────────────────────────────

    def rostros_cargados(self) -> int:
        return len(self._conocidos)

    def recargar(self) -> int:
        return self.cargar_diccionario()