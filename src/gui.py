"""Interfaz principal (Tkinter): video en vivo con reconocimiento facial y panel MySQL."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import cv2
import face_recognition
import numpy as np
from PIL import Image, ImageTk

import config
from src.database import (
    db_last_error,
    fetch_recent_access_rows,
    insert_access_log,
    validate_employee_permission,
)
from src.detector import (
    FaceDetector,
    best_match_employee_id,
    build_known_encodings_from_db,
)
from src.notifications import alertar_desconocido

# ── Constantes de visualizacion ────────────────────────────────────────────────

_FACE_SCALE = 0.25
_VIDEO_WIDTH = 1152
_PANEL_REFRESH_MS = 2_500
_RELOAD_KNOWN_FACES_EVERY_FRAMES = 180
_ACCESS_LOG_COOLDOWN_SEC = 4.0
_WIN_MIN = (1000, 640)
_WIN_INITIAL = "1280x780"

_COLOR_PERMITIDO = (0, 255, 0)
_COLOR_DENEGADO = (0, 0, 255)
_COLOR_NO_IDENTIFICADO = (0, 215, 255)


class MainWindow:
    """Ventana principal del sistema FACIAL PRO."""

    def __init__(self, camera_index: int = 0) -> None:
        self._camera_index = camera_index

        self._root = tk.Tk()
        self._root.title("Sistema FACIAL PRO")
        self._root.minsize(*_WIN_MIN)
        self._root.geometry(_WIN_INITIAL)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._running = True
        self._frame_lock = threading.Lock()
        self._known_lock = threading.Lock()
        self._latest_display: np.ndarray | None = None

        self._known_ids: list[int] = []
        self._known_encs: list[np.ndarray] = []
        self._last_log_mono: dict[str, float] = {}
        self._rostros_cargados = 0

        # Sincroniza known_faces/ con MySQL al iniciar.
        self._detector = FaceDetector()
        self._reload_known_faces()

        self._build_layout()

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
        )
        self._capture_thread.start()

        self._root.after(33, self._tick_video)
        self._root.after(_PANEL_REFRESH_MS, self._tick_panel)

    # ── Layout ─────────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        main = ttk.Frame(self._root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")

        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)

        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        paned = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew")

        video_frame = ttk.LabelFrame(paned, text="Video en vivo", padding=4)
        video_frame.rowconfigure(0, weight=1)
        video_frame.columnconfigure(0, weight=1)

        self._video_label = ttk.Label(video_frame)
        self._video_label.grid(row=0, column=0, sticky="nsew")

        panel = ttk.LabelFrame(paned, text="Ultimos registros (MySQL)", padding=4)

        paned.add(video_frame, weight=3)
        paned.add(panel, weight=2)

        cols = ("id", "empleado_id", "codigo", "fecha_hora", "estado")
        self._tree = ttk.Treeview(panel, columns=cols, show="headings", height=28)

        headings = {
            "id": "ID",
            "empleado_id": "Emp.",
            "codigo": "Codigo",
            "fecha_hora": "Fecha / hora",
            "estado": "Estado",
        }

        widths = (52, 60, 110, 155, 120)

        for column, width in zip(cols, widths):
            self._tree.heading(column, text=headings[column])
            self._tree.column(column, width=width, stretch=True)

        self._tree.tag_configure("permitido", background="#d4edda")
        self._tree.tag_configure("no_identificado", background="#f8d7da")
        self._tree.tag_configure("denegado", background="#fff3cd")

        scroll = ttk.Scrollbar(panel, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)

        barra = ttk.Frame(main)
        barra.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        barra.columnconfigure(0, weight=1)

        self._status = ttk.Label(
            barra,
            text=f"Rostros cargados: {self._rostros_cargados}",
        )
        self._status.grid(row=0, column=0, sticky="w")

        btn = ttk.Button(
            barra,
            text="Recargar diccionario",
            command=self._recargar_diccionario,
        )
        btn.grid(row=0, column=1, padx=(8, 0))

    # ── Carga de rostros ───────────────────────────────────────────────────────

    def _reload_known_faces(self) -> int:
        """Carga los encodings conocidos desde los empleados registrados en MySQL."""
        known_ids, known_encs = build_known_encodings_from_db()

        with self._known_lock:
            self._known_ids = known_ids
            self._known_encs = known_encs
            self._rostros_cargados = len(known_encs)

        return len(known_encs)

    # ── Bucle de captura ───────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        cap = cv2.VideoCapture(self._camera_index)

        if not cap.isOpened():
            self._status_set("ERROR: No se pudo abrir la camara.")
            return

        frame_n = 0

        try:
            while self._running:
                ok, frame = cap.read()

                if not ok or frame is None:
                    continue

                frame_n += 1

                if frame_n % _RELOAD_KNOWN_FACES_EVERY_FRAMES == 1:
                    self._reload_known_faces()

                h, w = frame.shape[:2]

                small = cv2.resize(
                    frame,
                    (0, 0),
                    fx=_FACE_SCALE,
                    fy=_FACE_SCALE,
                )
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                locations = face_recognition.face_locations(rgb, model="hog")
                encodings = face_recognition.face_encodings(rgb, locations)

                with self._known_lock:
                    known_ids = list(self._known_ids)
                    known_encs = list(self._known_encs)

                inv_scale = 1.0 / _FACE_SCALE
                now_mono = time.monotonic()

                for bbox, encoding in zip(locations, encodings):
                    top, right, bottom, left = bbox

                    top = int(top * inv_scale)
                    right = int(right * inv_scale)
                    bottom = int(bottom * inv_scale)
                    left = int(left * inv_scale)

                    matched_id = best_match_employee_id(
                        face_encoding=encoding,
                        known_ids=known_ids,
                        known_encodings=known_encs,
                    )

                    if matched_id is not None:
                        permitted = validate_employee_permission(matched_id)

                        if permitted:
                            color = _COLOR_PERMITIDO
                            estado = "permitido"
                            label = f"Empleado {matched_id}"
                            log_key = f"permitido_{matched_id}"
                            emp_for_log: int | None = matched_id
                        else:
                            color = _COLOR_DENEGADO
                            estado = "denegado"
                            label = f"Denegado {matched_id}"
                            log_key = f"denegado_{matched_id}"
                            emp_for_log = None
                    else:
                        color = _COLOR_NO_IDENTIFICADO
                        estado = "no_identificado"
                        label = "Desconocido"
                        log_key = "no_identificado"
                        emp_for_log = None

                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(
                        frame,
                        label,
                        (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        color,
                        2,
                    )

                    last_log = self._last_log_mono.get(log_key, 0.0)

                    if now_mono - last_log >= _ACCESS_LOG_COOLDOWN_SEC:
                        self._last_log_mono[log_key] = now_mono
                        insert_access_log(emp_for_log, estado, datetime.now())

                        if estado == "no_identificado":
                            alertar_desconocido(frame, datetime.now())

                display = cv2.resize(frame, (_VIDEO_WIDTH, int(h * _VIDEO_WIDTH / w)))

                with self._frame_lock:
                    self._latest_display = display

        finally:
            cap.release()

    # ── Ticks de la UI ─────────────────────────────────────────────────────────

    def _tick_video(self) -> None:
        if not self._running:
            return

        with self._frame_lock:
            frame = self._latest_display

        if frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            photo = ImageTk.PhotoImage(image=img)

            self._video_label.configure(image=photo)
            self._video_label.image = photo

        self._root.after(33, self._tick_video)

    def _tick_panel(self) -> None:
        if not self._running:
            return

        rows = fetch_recent_access_rows(limit=40)

        self._tree.delete(*self._tree.get_children())

        for row in rows:
            fh = row.get("fecha_hora")
            fh_str = (
                fh.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(fh, "strftime")
                else str(fh or "")
            )

            codigo = row.get("codigo_empleado") or ""
            estado = row.get("estado", "")
            tag = estado if estado in ("permitido", "no_identificado", "denegado") else ""

            self._tree.insert(
                "",
                "end",
                values=(
                    row.get("id", ""),
                    row.get("empleado_id") if row.get("empleado_id") is not None else "",
                    codigo,
                    fh_str,
                    estado,
                ),
                tags=(tag,),
            )

        if not rows:
            err = db_last_error()
            msg = (
                f"MySQL: {err} | {config.MYSQL_HOST}:{config.MYSQL_PORT} — revise .env"
                if err
                else "Panel: sin filas en registro_acceso (BD conectada)."
            )
            self._status.configure(text=msg)
        else:
            self._status.configure(
                text=f"Panel: {len(rows)} filas | Rostros: {self._rostros_cargados}"
            )

        self._root.after(_PANEL_REFRESH_MS, self._tick_panel)

    # ── Acciones de usuario ────────────────────────────────────────────────────

    def _recargar_diccionario(self) -> None:
        """Recarga known_faces/, sincroniza MySQL y actualiza encodings."""
        sincronizados = self._detector.recargar()
        cargados = self._reload_known_faces()

        self._status_set(
            f"Diccionario recargado: {cargados} rostro(s). Sincronizados: {sincronizados}."
        )

    def _status_set(self, text: str) -> None:
        def _go() -> None:
            self._status.configure(text=text)

        try:
            self._root.after(0, _go)
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        self._running = False

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)

        self._root.destroy()

    def run(self) -> None:
        """Inicia el bucle principal de Tkinter."""
        self._root.mainloop()