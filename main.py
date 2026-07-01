"""Punto de entrada de la aplicación POS del restaurante."""

from database.db_manager import init_db
from ui.tema import aplicar_tema_global, preparar_icono_aplicacion
from ui.ventana_login import VentanaLogin


def main() -> None:
    """Inicializa la BD y muestra la pantalla de login."""
    aplicar_tema_global()
    preparar_icono_aplicacion()
    init_db()
    app = VentanaLogin()
    app.mainloop()


if __name__ == "__main__":
    main()
