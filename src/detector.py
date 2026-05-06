"""Logica de reconocimiento facial y cifrado de datos sensibles.

Responsabilidades:
  - Cargar encodings desde data/known_faces/<codigo_empleado>.<ext>.
  - Comparar un frame RGB contra el diccionario en memoria.
  - Delegar la persistencia (insert) a src.database.
  - El cifrado/descifrado se delega a src.utils (cifrar_dato / descifrar_dato)
    para evitar dependencias circulares con database.py.

Uso tipico desde gui.py:
    from src.detector import FaceDetector
    detector = FaceDetector()
    resultados = detector.procesar_frame(rgb_frame)
    # resultados → list[dict] con claves: nombre, emp_id, estado, bbox, encoding
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import face_recognition
import numpy as np

from src.database import (
    db_last_error,
    fetch_empleado_by_codigo,
    insert_empleado,
    insert_registro_acceso,
)
from src.utils import cifrar_dato, descifrar_dato

# Alias semanticos para mayor claridad en este modulo
cifrar_nombre   = cifrar_dato
descifrar_nombre = descifrar_dato

# ── Constantes ─────────────────────────────────────────────────────────────────

_TOLERANCE   = 0.50
_KNOWN_FACES = Path(__file__).resolve().parent.parent / "data" / "known_faces"
_IMG_EXTS    = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ── Motor de reconocimiento ────────────────────────────────────────────────────

class FaceDetector:
    """Motor de reconocimiento facial con respaldo en MySQL."""

    def __init__(self) -> None:
        self._conocidos: dict[int, tuple[str, np.ndarray]] = {}
        self.cargar_diccionario()

    # ── Carga del diccionario ──────────────────────────────────────────────────

    def cargar_diccionario(self) -> int:
        """Lee data/known_faces/ y sincroniza con MySQL.

        Convencion de archivo:
            <codigo_empleado>.<ext>   →   EMP001.jpg  /  ana_garcia.png
        Si el empleado no existe en MySQL se inserta automaticamente con
        nombre, codigo y ruta cifrados con Fernet.

        Retorna: cantidad de rostros cargados.
        """
        self._conocidos.clear()

        if not _KNOWN_FACES.exists():
            print(f"[Detector] Carpeta not found: {_KNOWN_FACES}")
            return 0

        imagenes = [p for p in _KNOWN_FACES.iterdir() if p.suffix.lower() in _IMG_EXTS]
        if not imagenes:
            print("[Detector] Sin imagenes en known_faces/ — diccionario vacio.")
            return 0

        cargados = 0
        for ruta in sorted(imagenes):
            codigo = ruta.stem
            try:
                img  = face_recognition.load_image_file(str(ruta))
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

    def _sincronizar_empleado(
        self, codigo: str, ruta_imagen: str
    ) -> tuple[int | None, str]:
        """Busca el empleado por codigo en MySQL.
        Si no existe lo inserta con nombre, codigo y ruta cifrados.
        Retorna (emp_id, nombre_en_texto_plano).
        """
        fila = fetch_empleado_by_codigo(codigo)
        if fila:
            nombre_plain = descifrar_dato(fila["nombre_cifrado"])
            return int(fila["id"]), nombre_plain

        # No existe → insertar con los tres campos sensibles cifrados
        nombre_cifrado = cifrar_dato(codigo)       # nombre inicial = codigo
        codigo_cifrado = cifrar_dato(codigo)       # cifrar codigo_empleado
        ruta_cifrada   = cifrar_dato(ruta_imagen)  # cifrar ruta_imagen

        emp_id = insert_empleado(nombre_cifrado, codigo_cifrado, ruta_cifrada)
        if emp_id is None:
            print(f"[Detector] insert_empleado fallo: {db_last_error()}")
            return None, codigo

        print(f"[Detector] Empleado nuevo insertado: {codigo} → id={emp_id}")
        return emp_id, codigo

    # ── Procesamiento de frame ─────────────────────────────────────────────────

    def procesar_frame(self, frame_rgb: np.ndarray) -> list[dict[str, Any]]:
        """Detecta y reconoce rostros en un frame RGB (ya reducido por gui.py)."""
        if frame_rgb is None or frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3:
            return []

        frame_rgb  = np.ascontiguousarray(frame_rgb, dtype=np.uint8)
        ubicaciones = face_recognition.face_locations(frame_rgb, model="hog")
        if not ubicaciones:
            return []

        encodings  = face_recognition.face_encodings(frame_rgb, ubicaciones)
        resultados: list[dict[str, Any]] = []

        for encoding, bbox in zip(encodings, ubicaciones):
            nombre, emp_id, estado = self._identificar(encoding)
            resultados.append(
                {
                    "nombre":   nombre,
                    "emp_id":   emp_id,
                    "estado":   estado,
                    "bbox":     bbox,
                    "encoding": encoding,
                }
            )
            insert_registro_acceso(emp_id, estado)

        return resultados

    def _identificar(
        self, encoding: np.ndarray
    ) -> tuple[str, int | None, str]:
        """Compara encoding contra el diccionario en memoria."""
        if not self._conocidos:
            return "Desconocido", None, "no_identificado"

        ids      = list(self._conocidos.keys())
        vectores = [self._conocidos[i][1] for i in ids]

        distancias = face_recognition.face_distance(vectores, encoding)
        mejor      = int(np.argmin(distancias))

        if distancias[mejor] <= _TOLERANCE:
            emp_id = ids[mejor]
            return self._conocidos[emp_id][0], emp_id, "permitido"

        return "Desconocido", None, "no_identificado"

    # ── Utilidades ─────────────────────────────────────────────────────────────

    def rostros_cargados(self) -> int:
        return len(self._conocidos)

    def recargar(self) -> int:
        return self.cargar_diccionario()