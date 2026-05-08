"""Interfaz principal (Tkinter): video en vivo con marcos en rostros y panel MySQL."""

from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import Any

import cv2
import face_recognition
from PIL import Image, ImageTk

import config
from src.database import (
    db_last_error,
    fetch_recent_access_rows,
    insert_access_log,
    validate_employee_permission,
)
from src.detector import best_match_employee_id, build_known_encodings_from_db

# Escala para acelerar deteccion (face_recognition sobre frame reducido)
_FACE_SCALE = 0.25
_VIDEO_WIDTH = 1152
_PANEL_REFRESH_MS = 2_500
_RELOAD_KNOWN_FACES_EVERY_FRAMES = 180
_ACCESS_LOG_COOLDOWN_SEC = 4.0
_WIN_MIN = (1000, 640)
_WIN_INITIAL = "1280x780"


class MainWindow:
    """Ventana principal de la aplicacion."""

    def __init__(self, camera_index: int = 0) -> None:
        self._camera_index = camera_index
        self._root = tk.Tk()
        self._root.title("Sistema FACIAL PRO")
        self._root.minsize(*_WIN_MIN)
        self._root.geometry(_WIN_INITIAL)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._running = True
        self._frame_lock = threading.Lock()
        self._latest_display: Any = None  # numpy BGR frame listo para mostrar
        self._capture_thread: threading.Thread | None = None

        self._build_layout()
        self._start_capture_thread()

        self._root.after(33, self._tick_video)
        self._root.after(_PANEL_REFRESH_MS, self._tick_panel)

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
        self._tree = ttk.Treeview(
            panel,
            columns=cols,
            show="headings",
            height=28,
        )
        headings = {
            "id": "ID",
            "empleado_id": "Emp.",
            "codigo": "Codigo",
            "fecha_hora": "Fecha / hora",
            "estado": "Estado",
        }
        widths = (52, 60, 110, 155, 110)
        for c, w in zip(cols, widths):
            self._tree.heading(c, text=headings[c])
            self._tree.column(c, width=w, stretch=True)

        scroll = ttk.Scrollbar(panel, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)

        self._status = ttk.Label(main, text="Listo.")
        self._status.grid(row=1, column=0, sticky="ew", pady=(8, 0))

    def _start_capture_thread(self) -> None:
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

    def _capture_loop(self) -> None:
        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self._status_set("No se pudo abrir la camara.")
            return

        frame_n = 0
        known_ids: list[int] = []
        known_encs: list = []
        last_log_mono: dict[str, float] = {}

        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    continue

                frame_n += 1
                if (
                    frame_n % _RELOAD_KNOWN_FACES_EVERY_FRAMES == 1
                    or not known_encs
                ):
                    known_ids, known_encs = build_known_encodings_from_db()

                h, w = frame.shape[:2]
                small = cv2.resize(frame, (0, 0), fx=_FACE_SCALE, fy=_FACE_SCALE)
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locations = face_recognition.face_locations(rgb, model="hog")
                encodings = face_recognition.face_encodings(rgb, locations)
                inv = 1.0 / _FACE_SCALE
                now_m = time.monotonic()

                for (top, right, bottom, left), enc in zip(locations, encodings):
                    t, r, b, l = (
                        int(top * inv),
                        int(right * inv),
                        int(bottom * inv),
                        int(left * inv),
                    )
                    matched_id = best_match_employee_id(
                        enc, known_ids, known_encs, tolerance=0.6
                    )
                    if matched_id is not None:
                        permitted = validate_employee_permission(matched_id)
                        if permitted:
                            color = (0, 255, 0)
                            estado = "permitido"
                            log_key = f"ok_{matched_id}"
                            emp_for_log: int | None = matched_id
                        else:
                            color = (0, 0, 255)
                            estado = "denegado"
                            log_key = f"deny_{matched_id}"
                            # Sin fila en empleados: no usar FK a id inexistente
                            emp_for_log = None
                    else:
                        color = (0, 215, 255)
                        estado = "no_identificado"
                        log_key = "unknown"
                        emp_for_log = None

                    cv2.rectangle(frame, (l, t), (r, b), color, 2)

                    prev = last_log_mono.get(log_key, 0.0)
                    if now_m - prev >= _ACCESS_LOG_COOLDOWN_SEC:
                        last_log_mono[log_key] = now_m
                        insert_access_log(emp_for_log, estado)

                display = cv2.resize(frame, (_VIDEO_WIDTH, int(h * _VIDEO_WIDTH / w)))
                with self._frame_lock:
                    self._latest_display = display
        finally:
            cap.release()

    def _status_set(self, text: str) -> None:
        def go() -> None:
            self._status.configure(text=text)

        try:
            self._root.after(0, go)
        except tk.TclError:
            pass

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
            if fh is not None and hasattr(fh, "strftime"):
                fh_str = fh.strftime("%Y-%m-%d %H:%M:%S")
            else:
                fh_str = str(fh) if fh is not None else ""
            codigo = row.get("codigo_empleado") or ""
            self._tree.insert(
                "",
                "end",
                values=(
                    row.get("id", ""),
                    row.get("empleado_id") if row.get("empleado_id") is not None else "",
                    codigo,
                    fh_str,
                    row.get("estado", ""),
                ),
            )
        if not rows:
            err = db_last_error()
            if err:
                self._status.configure(
                    text=f"MySQL: {err} | Host {config.MYSQL_HOST}:{config.MYSQL_PORT} "
                    f"(levante Docker o revise .env)"
                )
            else:
                self._status.configure(
                    text="Panel: sin filas en registro_acceso (BD conectada)."
                )
        else:
            self._status.configure(text=f"Panel actualizado: {len(rows)} filas.")
        self._root.after(_PANEL_REFRESH_MS, self._tick_panel)

    def _on_close(self) -> None:
        self._running = False
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)
        self._root.destroy()

    def run(self) -> None:
        """Inicia el bucle principal de la interfaz."""
        self._root.mainloop()
