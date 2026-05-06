"""Punto de entrada del sistema de control de acceso facial."""

from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde el directorio de main.py (independiente del cwd del terminal)
load_dotenv(Path(__file__).resolve().parent / ".env")

from src.gui import MainWindow


def main() -> None:
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
