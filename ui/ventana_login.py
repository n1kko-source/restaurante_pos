"""Ventana de inicio de sesión con verificación de credenciales."""

from datetime import datetime

import customtkinter as ctk

from database.db_manager import init_db
from services import auth_service
from ui.tema import (
    PALETA,
    aplicar_tema_global,
    centrar_ventana,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
)
from ui.ventana_principal import VentanaPrincipal

# Nombres en español para el reloj (sin depender de locale del SO).
_DIAS = (
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
)
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_ANCHO_VENTANA = 480
_ALTO_VENTANA = 560
_ANCHO_TARJETA = 380


class VentanaLogin(ctk.CTk):
    """
    Pantalla de login del POS.
    Muestra fecha y hora en tiempo real y valida credenciales vía auth_service.
    No permite cerrar la aplicación hasta autenticarse correctamente.
    """

    def __init__(self):
        aplicar_tema_global()
        super().__init__()

        init_db()

        self.title("Sistema POS — Inicio de sesión")
        self.resizable(False, False)
        self.configure(fg_color=PALETA["fondo"])
        centrar_ventana(self, _ANCHO_VENTANA, _ALTO_VENTANA)

        self.protocol("WM_DELETE_WINDOW", self._bloquear_cierre)

        self._id_reloj = None
        self._construir_ui()
        self._actualizar_reloj()

        self.entry_usuario.focus()
        self.bind("<Return>", self._on_enter)

    def _construir_ui(self) -> None:
        """Construye la tarjeta de login centrada en pantalla."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tarjeta = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        tarjeta.grid(row=0, column=0)

        marco = ctk.CTkFrame(tarjeta, fg_color="transparent")
        marco.pack(expand=True, fill="both", padx=36, pady=36)

        ctk.CTkLabel(
            marco,
            text="Sistema POS",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            marco,
            text="Restaurante Hogareños",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).pack(pady=(0, 20))

        self.label_reloj = ctk.CTkLabel(
            marco,
            text="",
            font=fuente_pequena(),
            text_color=PALETA["acento"],
            wraplength=_ANCHO_TARJETA - 72,
            justify="center",
        )
        self.label_reloj.pack(pady=(0, 24))

        ctk.CTkLabel(
            marco,
            text="Usuario",
            font=fuente_normal(),
            text_color=PALETA["texto"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.entry_usuario = ctk.CTkEntry(
            marco,
            placeholder_text="Nombre de usuario",
            height=42,
            corner_radius=10,
            border_color=PALETA["entrada_borde"],
            fg_color=PALETA["entrada_fondo"],
            text_color=PALETA["texto"],
        )
        self.entry_usuario.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            marco,
            text="Contraseña",
            font=fuente_normal(),
            text_color=PALETA["texto"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.entry_password = ctk.CTkEntry(
            marco,
            placeholder_text="Contraseña",
            show="*",
            height=42,
            corner_radius=10,
            border_color=PALETA["entrada_borde"],
            fg_color=PALETA["entrada_fondo"],
            text_color=PALETA["texto"],
        )
        self.entry_password.pack(fill="x", pady=(0, 8))

        self.label_error = ctk.CTkLabel(
            marco,
            text=" ",
            font=fuente_pequena(),
            text_color=PALETA["error"],
            wraplength=_ANCHO_TARJETA - 72,
            justify="center",
        )
        self.label_error.pack(fill="x", pady=(4, 12))

        self.btn_login = ctk.CTkButton(
            marco,
            text="Iniciar sesión",
            height=44,
            corner_radius=10,
            font=fuente_boton(),
            fg_color=PALETA["boton_primario"],
            hover_color=PALETA["boton_primario_hover"],
            text_color="#ffffff",
            command=self._intentar_login,
        )
        self.btn_login.pack(fill="x")

    def _formatear_fecha_hora(self, momento: datetime) -> str:
        """Formatea fecha y hora en español para el reloj digital."""
        dia_semana = _DIAS[momento.weekday()]
        mes = _MESES[momento.month - 1]
        fecha = f"{dia_semana}, {momento.day} de {mes} de {momento.year}"
        hora = momento.strftime("%H:%M:%S")
        return f"{fecha}  —  {hora}"

    def _actualizar_reloj(self) -> None:
        """Actualiza el reloj digital cada segundo."""
        self.label_reloj.configure(text=self._formatear_fecha_hora(datetime.now()))
        self._id_reloj = self.after(1000, self._actualizar_reloj)

    def _bloquear_cierre(self) -> None:
        """Impide cerrar la ventana sin autenticarse."""
        self.label_error.configure(
            text="Debe iniciar sesión para usar el sistema.",
            text_color=PALETA["error"],
        )
        self.entry_password.focus()

    def _on_enter(self, event=None) -> None:
        """Inicia sesión al presionar Enter."""
        self._intentar_login()

    def _limpiar_error(self) -> None:
        """Oculta el mensaje de error."""
        self.label_error.configure(text=" ", text_color=PALETA["error"])

    def _intentar_login(self) -> None:
        """Valida credenciales y abre la ventana principal si son correctas."""
        self._limpiar_error()

        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get()

        try:
            usuario_auth = auth_service.login(usuario, password)
        except ValueError as error:
            self.label_error.configure(text=str(error), text_color=PALETA["error"])
            self.entry_password.delete(0, "end")
            self.entry_password.focus()
            return

        if self._id_reloj is not None:
            self.after_cancel(self._id_reloj)
            self._id_reloj = None

        self.destroy()
        principal = VentanaPrincipal(usuario_auth)
        principal.mainloop()
