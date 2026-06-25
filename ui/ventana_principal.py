"""Shell principal con barra lateral según rol del usuario."""

import customtkinter as ctk

from models.usuario import Usuario

# Opciones del menú lateral: (etiqueta, roles permitidos).
_OPCIONES_MENU = [
    ("Mesas", ("cajero", "supervisor", "administrador")),
    ("Punto de venta", ("cajero", "supervisor", "administrador")),
    ("Menú", ("supervisor", "administrador")),
    ("Inventario", ("supervisor", "administrador")),
    ("Reportes", ("supervisor", "administrador")),
    ("Usuarios", ("administrador",)),
    ("Configuración", ("administrador",)),
]


class VentanaPrincipal(ctk.CTk):
    """
    Ventana principal del POS.
    Muestra barra lateral con opciones filtradas según el rol del usuario autenticado.
    """

    def __init__(self, usuario: Usuario):
        super().__init__()

        self.usuario = usuario

        self.title(f"Sistema POS — {usuario.nombre}")
        self.geometry("1024x640")
        self.minsize(900, 560)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._construir_sidebar()
        self._construir_area_contenido()

    def _construir_sidebar(self) -> None:
        """Construye la barra lateral con opciones según rol."""
        sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(20, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="Sistema POS",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            sidebar,
            text=self.usuario.nombre,
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            wraplength=168,
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 2), sticky="w")

        ctk.CTkLabel(
            sidebar,
            text=f"Rol: {self.usuario.rol}",
            font=ctk.CTkFont(size=11),
            text_color="gray60",
        ).grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")

        fila = 3
        for etiqueta, roles in _OPCIONES_MENU:
            if self.usuario.rol not in roles:
                continue
            ctk.CTkButton(
                sidebar,
                text=etiqueta,
                anchor="w",
                height=36,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
            ).grid(row=fila, column=0, padx=12, pady=2, sticky="ew")
            fila += 1

        ctk.CTkButton(
            sidebar,
            text="Cerrar sesión",
            height=36,
            fg_color="#8b0000",
            hover_color="#a52a2a",
            command=self._cerrar_sesion,
        ).grid(row=21, column=0, padx=12, pady=(8, 20), sticky="ew")

    def _construir_area_contenido(self) -> None:
        """Área central de bienvenida; los módulos se abrirán en sprints posteriores."""
        contenido = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        contenido.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)

        ctk.CTkLabel(
            contenido,
            text=f"Bienvenido, {self.usuario.nombre}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        ctk.CTkLabel(
            contenido,
            text=(
                "Seleccione una opción del menú lateral para comenzar.\n"
                f"Su rol actual es: {self.usuario.rol}."
            ),
            font=ctk.CTkFont(size=14),
            text_color="gray70",
            justify="left",
        ).pack(anchor="w")

    def _cerrar_sesion(self) -> None:
        """Cierra la sesión y regresa a la pantalla de login."""
        from services import auth_service
        from ui.ventana_login import VentanaLogin

        auth_service.cerrar_sesion()
        self.destroy()
        login = VentanaLogin()
        login.mainloop()
