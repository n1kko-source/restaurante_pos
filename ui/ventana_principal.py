"""Shell principal con barra lateral según rol del usuario."""

import customtkinter as ctk

from models.usuario import Usuario
from ui.tema import (
    PALETA,
    aplicar_tema_global,
    centrar_ventana,
    crear_imagen_logo,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
)

# Opciones del menú lateral: (etiqueta, roles permitidos).
_OPCIONES_MENU = [
    ("Mesas", ("cajero", "supervisor", "administrador")),
    ("Menú", ("supervisor", "administrador")),
    ("Inventario", ("supervisor", "administrador")),
    ("Reportes", ("supervisor", "administrador")),
    ("Usuarios", ("administrador",)),
    ("Configuración", ("administrador",)),
]

_ANCHO_VENTANA = 1240
_ALTO_VENTANA = 700


class VentanaPrincipal(ctk.CTk):
    """
    Ventana principal del POS.
    Muestra barra lateral con opciones filtradas según el rol del usuario autenticado.
    """

    def __init__(self, usuario: Usuario):
        aplicar_tema_global()
        super().__init__()

        self.usuario = usuario
        self._opcion_activa = None
        self._botones_menu = {}

        self.title(f"Sistema POS — {usuario.nombre}")
        self.minsize(1020, 580)
        self.configure(fg_color=PALETA["fondo"])
        centrar_ventana(self, _ANCHO_VENTANA, _ALTO_VENTANA)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._modulo_actual = None
        self._contenedor_modulo = None

        self._construir_sidebar()
        self._construir_area_contenido()

    def _construir_sidebar(self) -> None:
        """Construye la barra lateral con opciones según rol."""
        sidebar = ctk.CTkFrame(
            self,
            width=220,
            corner_radius=0,
            fg_color=PALETA["sidebar"],
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(20, weight=1)

        ctk.CTkFrame(
            sidebar,
            width=1,
            fg_color=PALETA["sidebar_borde"],
            corner_radius=0,
        ).grid(row=0, column=1, rowspan=22, sticky="ns")

        sidebar.grid_columnconfigure(0, weight=1)

        encabezado = ctk.CTkFrame(sidebar, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=14, pady=(20, 16))
        encabezado.grid_columnconfigure(0, weight=1)

        self._imagen_logo_sidebar = crear_imagen_logo(48, 48)
        fila_encabezado = 0
        if self._imagen_logo_sidebar is not None:
            ctk.CTkLabel(
                encabezado,
                image=self._imagen_logo_sidebar,
                text="",
            ).grid(row=fila_encabezado, column=0, pady=(0, 6))
            fila_encabezado += 1

        ctk.CTkLabel(
            encabezado,
            text="Sistema POS",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETA["texto"],
            anchor="center",
            justify="center",
        ).grid(row=fila_encabezado, column=0, pady=(0, 4))

        ctk.CTkLabel(
            encabezado,
            text=self.usuario.nombre,
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
            wraplength=180,
            anchor="center",
            justify="center",
        ).grid(row=fila_encabezado + 1, column=0, pady=(0, 2))

        ctk.CTkLabel(
            encabezado,
            text=f"Rol: {self.usuario.rol}",
            font=ctk.CTkFont(size=11),
            text_color=PALETA["texto_suave"],
            anchor="center",
            justify="center",
        ).grid(row=fila_encabezado + 2, column=0, pady=(0, 4))

        fila = 1
        for etiqueta, roles in _OPCIONES_MENU:
            if self.usuario.rol not in roles:
                continue
            comando = self._comando_menu(etiqueta)
            boton = ctk.CTkButton(
                sidebar,
                text=etiqueta,
                anchor="w",
                height=40,
                corner_radius=10,
                font=fuente_normal(),
                fg_color="transparent",
                text_color=PALETA["sidebar_texto"],
                hover_color=PALETA["sidebar_hover"],
                command=lambda e=etiqueta, c=comando: self._al_elegir_menu(e, c),
            )
            boton.grid(row=fila, column=0, padx=14, pady=3, sticky="ew")
            self._botones_menu[etiqueta] = boton
            fila += 1

        ctk.CTkButton(
            sidebar,
            text="Cerrar sesión",
            height=40,
            corner_radius=10,
            font=fuente_normal(),
            fg_color=PALETA["cerrar_sesion"],
            hover_color=PALETA["cerrar_sesion_hover"],
            text_color="#ffffff",
            command=self._cerrar_sesion,
        ).grid(row=21, column=0, padx=14, pady=(8, 24), sticky="ew")

    def _al_elegir_menu(self, etiqueta: str, comando) -> None:
        """Resalta la opción activa y ejecuta su acción."""
        self._marcar_opcion_activa(etiqueta)
        if comando is not None:
            comando()

    def _marcar_opcion_activa(self, etiqueta: str) -> None:
        """Actualiza el estilo visual del ítem de menú seleccionado."""
        self._opcion_activa = etiqueta
        for nombre, boton in self._botones_menu.items():
            if nombre == etiqueta:
                boton.configure(
                    fg_color=PALETA["sidebar_activo"],
                    text_color=PALETA["acento"],
                )
            else:
                boton.configure(
                    fg_color="transparent",
                    text_color=PALETA["sidebar_texto"],
                )

    def _construir_area_contenido(self) -> None:
        """Área central donde se cargan los módulos del sistema."""
        self._contenedor_modulo = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=PALETA["fondo"],
        )
        self._contenedor_modulo.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._contenedor_modulo.grid_columnconfigure(0, weight=1)
        self._contenedor_modulo.grid_rowconfigure(0, weight=1)
        self._mostrar_bienvenida()

    def _comando_menu(self, etiqueta: str):
        """Retorna el callback del menú lateral según la opción."""
        comandos = {
            "Mesas": self._abrir_mesas,
            "Menú": self._abrir_menu,
            "Inventario": self._abrir_inventario,
            "Reportes": self._abrir_reportes,
            "Usuarios": self._abrir_usuarios,
            "Configuración": self._abrir_configuracion,
        }
        return comandos.get(etiqueta)

    def _limpiar_modulo(self) -> None:
        """Destruye el módulo activo en el área de contenido."""
        if self._modulo_actual is not None:
            self._modulo_actual.destroy()
            self._modulo_actual = None

    def _mostrar_bienvenida(self) -> None:
        """Muestra la pantalla de bienvenida en el área central."""
        self._limpiar_modulo()
        self._marcar_opcion_activa("")

        contenedor = ctk.CTkFrame(self._contenedor_modulo, fg_color=PALETA["fondo"])
        contenedor.grid(row=0, column=0, sticky="nsew")
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)
        self._modulo_actual = contenedor

        tarjeta = ctk.CTkFrame(
            contenedor,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        tarjeta.grid(row=0, column=0)
        tarjeta.grid_propagate(True)

        marco = ctk.CTkFrame(tarjeta, fg_color="transparent")
        marco.pack(padx=48, pady=40)

        ctk.CTkLabel(
            marco,
            text=f"Bienvenido, {self.usuario.nombre}",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).pack(pady=(0, 10))

        ctk.CTkLabel(
            marco,
            text=(
                "Seleccione una opción del menú lateral para comenzar.\n"
                f"Su rol actual es: {self.usuario.rol}."
            ),
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
            justify="center",
        ).pack()

    def _abrir_mesas(self) -> None:
        """Abre el mapa visual del salón."""
        from tkinter import messagebox

        from services.auth_service import ErrorAcceso
        from ui.ventana_mesas import mostrar_en

        self._limpiar_modulo()
        try:
            self._modulo_actual = mostrar_en(self._contenedor_modulo)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            self._mostrar_bienvenida()

    def _abrir_menu(self) -> None:
        """Abre la gestión de productos y categorías del menú."""
        from tkinter import messagebox

        from services.auth_service import ErrorAcceso
        from ui.ventana_menu import mostrar_en

        self._limpiar_modulo()
        try:
            self._modulo_actual = mostrar_en(self._contenedor_modulo)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            self._mostrar_bienvenida()

    def _abrir_inventario(self) -> None:
        """Abre el control de stock por producto."""
        from tkinter import messagebox

        from services.auth_service import ErrorAcceso
        from ui.ventana_inventario import mostrar_en

        self._limpiar_modulo()
        try:
            self._modulo_actual = mostrar_en(self._contenedor_modulo)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            self._mostrar_bienvenida()

    def _abrir_reportes(self) -> None:
        """Abre la exportación de reportes diarios y mensuales."""
        from tkinter import messagebox

        from services.auth_service import ErrorAcceso
        from ui.ventana_reportes import mostrar_en

        self._limpiar_modulo()
        try:
            self._modulo_actual = mostrar_en(self._contenedor_modulo)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            self._mostrar_bienvenida()

    def _abrir_usuarios(self) -> None:
        """Abre la administración de usuarios del sistema."""
        from tkinter import messagebox

        from services.auth_service import ErrorAcceso
        from ui.ventana_usuarios import mostrar_en

        self._limpiar_modulo()
        try:
            self._modulo_actual = mostrar_en(self._contenedor_modulo)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            self._mostrar_bienvenida()

    def _abrir_configuracion(self) -> None:
        """Abre la configuración de fecha y hora del sistema."""
        from tkinter import messagebox

        from services.auth_service import ErrorAcceso
        from ui.ventana_configuracion import mostrar_en

        self._limpiar_modulo()
        try:
            self._modulo_actual = mostrar_en(self._contenedor_modulo)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            self._mostrar_bienvenida()

    def _cerrar_sesion(self) -> None:
        """Cierra la sesión y regresa a la pantalla de login."""
        from services import auth_service
        from ui.tema import limpiar_cache_ui_sesion
        from ui.ventana_login import VentanaLogin

        auth_service.cerrar_sesion()
        limpiar_cache_ui_sesion()
        self.destroy()
        login = VentanaLogin()
        login.mainloop()
