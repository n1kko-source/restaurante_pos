"""Punto de entrada de la aplicación POS del restaurante."""

from ui.ventana_login import VentanaLogin


def main() -> None:
    """Inicia la aplicación mostrando la pantalla de login."""
    app = VentanaLogin()
    app.mainloop()


if __name__ == "__main__":
    main()
