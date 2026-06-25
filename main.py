"""Punto de entrada de la aplicación POS del restaurante."""

from ui.tema import aplicar_tema_global
from ui.ventana_login import VentanaLogin


def main() -> None:
    """Inicia la aplicación mostrando la pantalla de login."""
    aplicar_tema_global()
    app = VentanaLogin()
    app.mainloop()


if __name__ == "__main__":
    main()
