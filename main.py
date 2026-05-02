"""Punto de entrada del sistema de control de acceso facial."""

from pathlib import Path

from dotenv import load_dotenv

# Cargar .env junto a main.py aunque el cwd del terminal sea otro directorio
_env = Path(__file__).resolve().parent / ".env"
load_dotenv(_env)

from src.gui import MainWindow


def main() -> None:
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
