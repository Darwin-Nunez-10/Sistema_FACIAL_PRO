"""Interfaz principal (Tkinter): video en vivo con reconocimiento facial y panel MySQL."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageTk

import config
from src.database import db_last_error, fetch_recent_access_rows
from src.detector import FaceDetector
from src.notifications import alertar_desconocido
from src.utils import escalar_bbox

# ── Constantes de visualizacion ────────────────────────────────────────────────
_FACE_SCALE       = 0.25           # factor de reduccion para acelerar deteccion
_VIDEO_WIDTH      = 1152           # ancho del video mostrado en la GUI
_PANEL_REFRESH_MS = 2_500          # intervalo de refresco del panel MySQL
_WIN_MIN          = (1000, 640)
_WIN_INITIAL      = "1280x780"

_COLOR_PERMITIDO       = (0, 255,   0)   # verde  — empleado reconocido
_COLOR_NO_IDENTIFICADO = (0,   0, 255)   # rojo   — desconocido


class MainWindow:
    """Ventana principal del sistema FACIAL PRO."""

    def __init__(self, camera_index: int = 0) -> None:
        self._camera_index = camera_index

        self._root = tk.Tk()
        self._root.title("Sistema FACIAL PRO")
        self._root.minsize(*_WIN_MIN)
        self._root.geometry(_WIN_INITIAL)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._running      = True
        self._frame_lock   = threading.Lock()
        self._latest_display: np.ndarray | None = None

        # Motor de reconocimiento (carga known_faces/ al arrancar)
        self._detector = FaceDetector()

        self._build_layout()
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True
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

        # Panel izquierdo: video
        video_frame = ttk.LabelFrame(paned, text="Video en vivo", padding=4)
        video_frame.rowconfigure(0, weight=1)
        video_frame.columnconfigure(0, weight=1)
        self._video_label = ttk.Label(video_frame)
        self._video_label.grid(row=0, column=0, sticky="nsew")

        # Panel derecho: registros MySQL
        panel = ttk.LabelFrame(paned, text="Ultimos registros (MySQL)", padding=4)

        paned.add(video_frame, weight=3)
        paned.add(panel, weight=2)

        cols = ("id", "empleado_id", "codigo", "fecha_hora", "estado")
        self._tree = ttk.Treeview(panel, columns=cols, show="headings", height=28)
        headings = {
            "id":          "ID",
            "empleado_id": "Emp.",
            "codigo":      "Codigo",
            "fecha_hora":  "Fecha / hora",
            "estado":      "Estado",
        }
        widths = (52, 60, 110, 155, 120)
        for c, w in zip(cols, widths):
            self._tree.heading(c, text=headings[c])
            self._tree.column(c, width=w, stretch=True)

        # Colores por estado
        self._tree.tag_configure("permitido",       background="#d4edda")  # verde suave
        self._tree.tag_configure("no_identificado", background="#f8d7da")  # rojo suave

        scroll = ttk.Scrollbar(panel, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        panel.rowconfigure(0, weight=1)
        panel.columnconfigure(0, weight=1)

        # Barra de estado + boton recargar
        barra = ttk.Frame(main)
        barra.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        barra.columnconfigure(0, weight=1)

        self._status = ttk.Label(barra, text=f"Rostros cargados: {self._detector.rostros_cargados()}")
        self._status.grid(row=0, column=0, sticky="w")

        btn = ttk.Button(barra, text="Recargar diccionario", command=self._recargar_diccionario)
        btn.grid(row=0, column=1, padx=(8, 0))

    # ── Bucle de captura (hilo separado) ───────────────────────────────────────

    def _capture_loop(self) -> None:
        cap = cv2.VideoCapture(self._camera_index)
        if not cap.isOpened():
            self._status_set("ERROR: No se pudo abrir la camara.")
            return

        try:
            while self._running:
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue

                h, w = frame.shape[:2]

                # Reducir para acelerar face_recognition
                small   = cv2.resize(frame, (0, 0), fx=_FACE_SCALE, fy=_FACE_SCALE)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

                # Deteccion + reconocimiento + INSERT en MySQL
                resultados = self._detector.procesar_frame(rgb_small)

                for r in resultados:
                    # Escalar bbox al frame completo
                    top, right, bottom, left = escalar_bbox(r["bbox"], _FACE_SCALE)
                    estado = r["estado"]
                    nombre = r["nombre"]
                    color  = _COLOR_PERMITIDO if estado == "permitido" else _COLOR_NO_IDENTIFICADO

                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                    cv2.putText(
                        frame, nombre,
                        (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2,
                    )

                    # Alerta si es desconocido
                    if estado == "no_identificado":
                        alertar_desconocido(frame, datetime.now())

                # Escalar para mostrar en la GUI
                display = cv2.resize(frame, (_VIDEO_WIDTH, int(h * _VIDEO_WIDTH / w)))
                with self._frame_lock:
                    self._latest_display = display

        finally:
            cap.release()

    # ── Ticks de la UI (hilo principal) ───────────────────────────────────────

    def _tick_video(self) -> None:
        if not self._running:
            return
        with self._frame_lock:
            frame = self._latest_display
        if frame is not None:
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
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
            fh_str = fh.strftime("%Y-%m-%d %H:%M:%S") if hasattr(fh, "strftime") else str(fh or "")
            codigo = row.get("codigo_empleado") or ""
            estado = row.get("estado", "")
            tag    = estado if estado in ("permitido", "no_identificado") else ""
            self._tree.insert(
                "", "end",
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
                text=f"Panel: {len(rows)} filas | Rostros: {self._detector.rostros_cargados()}"
            )
        self._root.after(_PANEL_REFRESH_MS, self._tick_panel)

    # ── Acciones de usuario ────────────────────────────────────────────────────

    def _recargar_diccionario(self) -> None:
        """Boton 'Recargar diccionario' — util al agregar fotos sin reiniciar."""
        n = self._detector.recargar()
        self._status_set(f"Diccionario recargado: {n} rostro(s).")

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
