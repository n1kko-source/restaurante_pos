"""Ventana de inicio de sesión con verificación de credenciales."""

from datetime import datetime

import customtkinter as ctk

from database.db_manager import init_db
from services import auth_service
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


class VentanaLogin(ctk.CTk):
    """
    Pantalla de login del POS.
    Muestra fecha y hora en tiempo real y valida credenciales vía auth_service.
    No permite cerrar la aplicación hasta autenticarse correctamente.
    """

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        init_db()

        self.title("Sistema POS — Inicio de sesión")
        self.geometry("440x520")
        self.resizable(False, False)

        # Bloquea el botón X de la ventana hasta autenticarse.
        self.protocol("WM_DELETE_WINDOW", self._bloquear_cierre)

        self._id_reloj = None
        self._construir_ui()
        self._actualizar_reloj()

        self.entry_usuario.focus()
        self.bind("<Return>", self._on_enter)

    def _construir_ui(self) -> None:
        """Construye los widgets de la pantalla de login."""
        marco = ctk.CTkFrame(self, fg_color="transparent")
        marco.pack(expand=True, fill="both", padx=40, pady=30)

        ctk.CTkLabel(
            marco,
            text="Sistema POS",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            marco,
            text="Restaurante Hogareños",
            font=ctk.CTkFont(size=14),
            text_color="gray70",
        ).pack(pady=(0, 24))

        self.label_reloj = ctk.CTkLabel(
            marco,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#4da3ff",
        )
        self.label_reloj.pack(pady=(0, 28))

        ctk.CTkLabel(
            marco,
            text="Usuario",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.entry_usuario = ctk.CTkEntry(
            marco,
            placeholder_text="Nombre de usuario",
            height=38,
        )
        self.entry_usuario.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            marco,
            text="Contraseña",
            font=ctk.CTkFont(size=13),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.entry_password = ctk.CTkEntry(
            marco,
            placeholder_text="Contraseña",
            show="*",
            height=38,
        )
        self.entry_password.pack(fill="x", pady=(0, 8))

        # Reserva espacio fijo para no mover el layout al mostrar errores.
        self.label_error = ctk.CTkLabel(
            marco,
            text=" ",
            font=ctk.CTkFont(size=12),
            text_color="#e74c3c",
            wraplength=340,
            justify="center",
        )
        self.label_error.pack(fill="x", pady=(4, 12))

        self.btn_login = ctk.CTkButton(
            marco,
            text="Iniciar sesión",
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._intentar_login,
        )
        self.btn_login.pack(fill="x", pady=(0, 8))

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
            text_color="#e74c3c",
        )
        self.entry_password.focus()

    def _on_enter(self, event=None) -> None:
        """Inicia sesión al presionar Enter."""
        self._intentar_login()

    def _limpiar_error(self) -> None:
        """Oculta el mensaje de error."""
        self.label_error.configure(text=" ", text_color="#e74c3c")

    def _intentar_login(self) -> None:
        """Valida credenciales y abre la ventana principal si son correctas."""
        self._limpiar_error()

        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get()

        try:
            usuario_auth = auth_service.login(usuario, password)
        except ValueError as error:
            self.label_error.configure(text=str(error), text_color="#e74c3c")
            self.entry_password.delete(0, "end")
            self.entry_password.focus()
            return

        if self._id_reloj is not None:
            self.after_cancel(self._id_reloj)
            self._id_reloj = None

        self.destroy()
        principal = VentanaPrincipal(usuario_auth)
        principal.mainloop()
