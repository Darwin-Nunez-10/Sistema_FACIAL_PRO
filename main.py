"""Punto de entrada del sistema de control de acceso facial."""

from dotenv import load_dotenv

load_dotenv()

from src.gui import MainWindow


def main() -> None:
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
