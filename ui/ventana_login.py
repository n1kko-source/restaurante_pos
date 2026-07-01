"""Ventana de inicio de sesión con selección de rol y verificación de credenciales."""

from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from config import RUTA_ICONOS
from services import auth_service
from services import hora_service
from ui.tema import (
    PALETA,
    aplicar_tema_global,
    centrar_ventana,
    crear_imagen_asset,
    crear_imagen_logo,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
    kwargs_boton_primario,
)
from ui.ventana_principal import VentanaPrincipal

_ANCHO_VENTANA = 520
_ALTO_VENTANA = 700
_ANCHO_TARJETA = 460
_ALTO_TARJETA = 620
_PADDING_MARCO_H = 24
_ANCHO_INTERIOR = _ANCHO_TARJETA - (2 * _PADDING_MARCO_H)
_ALTO_ICONO_ROL = 84
_ALTO_FILA_ROL = 96
_SEPARACION_ROLES = 8
_ANCHO_MIN_TEXTO_ROL = 210
_ALTO_ZONA_INTERCAMBIO = (3 * _ALTO_FILA_ROL) + (2 * _SEPARACION_ROLES)
_ALTO_LOGO = 80
_PADDING_MARCO_V = 32

# (código rol BD, etiqueta UI, archivo en assets/iconos/)
_ROLES_LOGIN: List[Tuple[str, str, str]] = [
    ("administrador", "Administrador", "administrador.png"),
    ("supervisor", "Supervisor", "supervisor.png"),
    ("cajero", "Cajero", "cajero.png"),
]


def _fuente_etiqueta_rol() -> ctk.CTkFont:
    """Fuente destacada para el nombre del rol en el login."""
    return ctk.CTkFont(size=16, weight="bold")


class _FilaRol(ctk.CTkFrame):
    """Fila clicable con icono y nombre de rol para la pantalla de login."""

    def __init__(
        self,
        master,
        codigo_rol: str,
        etiqueta: str,
        imagen: Optional[ctk.CTkImage],
        al_seleccionar: Callable[[str], None],
    ):
        super().__init__(
            master,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
            width=_ANCHO_INTERIOR,
            height=_ALTO_FILA_ROL,
        )
        self.pack_propagate(False)
        self._codigo_rol = codigo_rol
        self._al_seleccionar = al_seleccionar
        self._seleccionado = False

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=10, pady=8)
        contenido.grid_columnconfigure(0, weight=0)
        contenido.grid_columnconfigure(1, weight=1, minsize=_ANCHO_MIN_TEXTO_ROL)

        if imagen is not None:
            lbl_icono = ctk.CTkLabel(
                contenido,
                image=imagen,
                text="",
                width=_ALTO_ICONO_ROL,
            )
            lbl_icono.grid(row=0, column=0, padx=(0, 14), sticky="w")
        else:
            lbl_icono = ctk.CTkLabel(
                contenido,
                text=etiqueta[0].upper(),
                font=ctk.CTkFont(size=26, weight="bold"),
                text_color=PALETA["acento"],
                width=_ALTO_ICONO_ROL,
            )
            lbl_icono.grid(row=0, column=0, padx=(0, 14), sticky="w")

        lbl_texto = ctk.CTkLabel(
            contenido,
            text=etiqueta,
            font=_fuente_etiqueta_rol(),
            text_color=PALETA["texto"],
            anchor="w",
            justify="left",
        )
        lbl_texto.grid(row=0, column=1, sticky="ew", padx=(0, 4))

        self._widgets_clic = (self, contenido, lbl_texto)
        if imagen is not None:
            self._widgets_clic = self._widgets_clic + (lbl_icono,)

        for widget in self._widgets_clic:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", self._al_clic)
            widget.bind("<Enter>", self._al_entrar)
            widget.bind("<Leave>", self._al_salir)

    def _al_clic(self, _evento=None) -> None:
        """Notifica la selección del rol al contenedor del login."""
        self._al_seleccionar(self._codigo_rol)

    def _al_entrar(self, _evento=None) -> None:
        """Resalta la fila al pasar el cursor si no está seleccionada."""
        if not self._seleccionado:
            self.configure(fg_color=PALETA["sidebar_hover"])

    def _al_salir(self, _evento=None) -> None:
        """Restaura el fondo al salir del cursor."""
        self._aplicar_estado_seleccion()

    def marcar_seleccionado(self, activo: bool) -> None:
        """Actualiza el aspecto visual según si el rol está elegido."""
        self._seleccionado = activo
        self._aplicar_estado_seleccion()

    def _aplicar_estado_seleccion(self) -> None:
        if self._seleccionado:
            self.configure(
                fg_color=PALETA["sidebar_activo"],
                border_color=PALETA["boton_accion_borde"],
            )
        else:
            self.configure(
                fg_color=PALETA["tarjeta"],
                border_color=PALETA["borde"],
            )


class VentanaLogin(ctk.CTk):
    """
    Pantalla de login del POS.
    Primero el usuario elige rol; luego ingresa credenciales.
    La ventana puede cerrarse con la X sin iniciar sesión (no hay sesión activa).
    """

    def __init__(self):
        aplicar_tema_global()
        super().__init__()

        self.title("Sistema POS — Inicio de sesión")
        self.resizable(False, False)
        self.configure(fg_color=PALETA["fondo"])
        centrar_ventana(self, _ANCHO_VENTANA, _ALTO_VENTANA)

        self.protocol("WM_DELETE_WINDOW", self._cerrar_aplicacion)

        self._id_reloj: Optional[str] = None
        self._rol_seleccionado: Optional[str] = None
        self._filas_rol: Dict[str, _FilaRol] = {}
        self._imagenes_rol: Dict[str, ctk.CTkImage] = {}

        self._construir_ui()
        self._actualizar_reloj()

        self.bind("<Return>", self._on_enter)

    def _construir_ui(self) -> None:
        """Construye la tarjeta de login con selector de rol y formulario."""
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._tarjeta = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=20,
            border_width=1,
            border_color=PALETA["borde"],
            width=_ANCHO_TARJETA,
            height=_ALTO_TARJETA,
        )
        self._tarjeta.grid(row=0, column=0)
        self._tarjeta.grid_propagate(False)

        marco = ctk.CTkFrame(self._tarjeta, fg_color="transparent")
        marco.pack(expand=True, fill="both", padx=_PADDING_MARCO_H, pady=_PADDING_MARCO_V)

        self._imagen_logo = crear_imagen_logo(_ALTO_LOGO, _ALTO_LOGO)
        if self._imagen_logo is not None:
            ctk.CTkLabel(marco, image=self._imagen_logo, text="").pack(pady=(0, 8))

        ctk.CTkLabel(
            marco,
            text="Sistema POS",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            marco,
            text="Restaurante Hogareños",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).pack(pady=(0, 12))

        self.label_reloj = ctk.CTkLabel(
            marco,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=PALETA["acento"],
            wraplength=_ANCHO_INTERIOR,
            justify="center",
        )
        self.label_reloj.pack(pady=(0, 18))

        self._zona_intercambio = ctk.CTkFrame(
            marco,
            fg_color="transparent",
            width=_ANCHO_INTERIOR,
            height=_ALTO_ZONA_INTERCAMBIO,
        )
        self._zona_intercambio.pack(fill="x")
        self._zona_intercambio.pack_propagate(False)

        self._marco_roles = ctk.CTkFrame(
            self._zona_intercambio,
            fg_color="transparent",
            width=_ANCHO_INTERIOR,
        )
        self._marco_roles.pack(fill="both", expand=True)

        for codigo, etiqueta, archivo in _ROLES_LOGIN:
            imagen = crear_imagen_asset(
                RUTA_ICONOS / archivo,
                _ALTO_ICONO_ROL,
                _ALTO_ICONO_ROL,
            )
            if imagen is not None:
                self._imagenes_rol[codigo] = imagen

            fila = _FilaRol(
                self._marco_roles,
                codigo,
                etiqueta,
                imagen,
                self._al_seleccionar_rol,
            )
            fila.pack(fill="x", pady=(0, _SEPARACION_ROLES), ipadx=0)
            self._filas_rol[codigo] = fila

        self._marco_credenciales = ctk.CTkFrame(
            self._zona_intercambio,
            fg_color="transparent",
            width=_ANCHO_INTERIOR,
        )

        self._label_rol_activo = ctk.CTkLabel(
            self._marco_credenciales,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETA["acento"],
            anchor="w",
        )
        self._label_rol_activo.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(
            self._marco_credenciales,
            text="← Elegir otro rol",
            height=28,
            font=fuente_pequena(),
            fg_color="transparent",
            hover_color=PALETA["sidebar_hover"],
            text_color=PALETA["texto_suave"],
            anchor="w",
            command=self._volver_a_roles,
        ).pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            self._marco_credenciales,
            text="Usuario",
            font=fuente_normal(),
            text_color=PALETA["texto"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.entry_usuario = ctk.CTkEntry(
            self._marco_credenciales,
            placeholder_text="Nombre de usuario",
            height=42,
            corner_radius=10,
            border_color=PALETA["entrada_borde"],
            fg_color=PALETA["entrada_fondo"],
            text_color=PALETA["texto"],
        )
        self.entry_usuario.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(
            self._marco_credenciales,
            text="Contraseña",
            font=fuente_normal(),
            text_color=PALETA["texto"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.entry_password = ctk.CTkEntry(
            self._marco_credenciales,
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
            self._marco_credenciales,
            text=" ",
            font=fuente_pequena(),
            text_color=PALETA["error"],
            wraplength=_ANCHO_INTERIOR,
            justify="center",
        )
        self.label_error.pack(fill="x", pady=(4, 0))

        ctk.CTkFrame(marco, fg_color="transparent", height=12).pack()

        self.btn_login = ctk.CTkButton(
            marco,
            text="Iniciar sesión",
            height=42,
            font=fuente_boton(),
            command=self._intentar_login,
            **kwargs_boton_primario(corner_radius=12),
        )
        self.btn_login.pack(fill="x")

    def _etiqueta_rol(self, codigo: str) -> str:
        """Retorna la etiqueta legible de un código de rol."""
        for cod, etiqueta, _arch in _ROLES_LOGIN:
            if cod == codigo:
                return etiqueta
        return codigo

    def _al_seleccionar_rol(self, codigo: str) -> None:
        """Muestra el formulario de credenciales tras elegir un rol."""
        self._limpiar_error()
        self._rol_seleccionado = codigo

        for cod, fila in self._filas_rol.items():
            fila.marcar_seleccionado(cod == codigo)

        self._label_rol_activo.configure(
            text=f"Acceso como {self._etiqueta_rol(codigo)}"
        )

        if not self._marco_credenciales.winfo_ismapped():
            self._marco_roles.pack_forget()
            self._marco_credenciales.pack(fill="both", expand=True, padx=0, pady=(4, 0))
        else:
            self.entry_usuario.delete(0, "end")
            self.entry_password.delete(0, "end")

        self.entry_usuario.focus_set()

    def _volver_a_roles(self) -> None:
        """Regresa al listado de roles sin cerrar la ventana."""
        self._limpiar_error()
        self._rol_seleccionado = None
        self.entry_usuario.delete(0, "end")
        self.entry_password.delete(0, "end")

        for fila in self._filas_rol.values():
            fila.marcar_seleccionado(False)

        self._marco_credenciales.pack_forget()
        self._marco_roles.pack(fill="both", expand=True)

    def _actualizar_reloj(self) -> None:
        """Actualiza el reloj digital cada segundo."""
        self.label_reloj.configure(
            text=hora_service.formatear_legible(hora_service.obtener_datetime_actual())
        )
        self._id_reloj = self.after(1000, self._actualizar_reloj)

    def _detener_reloj(self) -> None:
        """Cancela la actualización periódica del reloj."""
        if self._id_reloj is not None:
            self.after_cancel(self._id_reloj)
            self._id_reloj = None

    def _cerrar_aplicacion(self) -> None:
        """Cierra la aplicación sin crear sesión."""
        self._detener_reloj()
        self.destroy()

    def _on_enter(self, _evento=None) -> None:
        """Inicia sesión al presionar Enter."""
        self._intentar_login()

    def _limpiar_error(self) -> None:
        """Oculta el mensaje de error."""
        self.label_error.configure(text=" ", text_color=PALETA["error"])

    def _intentar_login(self) -> None:
        """Valida rol y credenciales; abre la ventana principal si son correctas."""
        self._limpiar_error()

        if not self._rol_seleccionado:
            messagebox.showinfo(
                "Seleccione un rol",
                "Elija Administrador, Supervisor o Cajero para continuar.",
                parent=self,
            )
            return

        usuario = self.entry_usuario.get().strip()
        password = self.entry_password.get()

        try:
            usuario_auth = auth_service.login(usuario, password)
        except ValueError as error:
            self.label_error.configure(text=str(error), text_color=PALETA["error"])
            self.entry_password.delete(0, "end")
            self.entry_password.focus()
            return

        if usuario_auth.rol != self._rol_seleccionado:
            auth_service.cerrar_sesion()
            rol_real = self._etiqueta_rol(usuario_auth.rol)
            rol_elegido = self._etiqueta_rol(self._rol_seleccionado)
            self.label_error.configure(
                text=(
                    f"Este usuario tiene rol {rol_real}, no {rol_elegido}. "
                    "Verifique su selección."
                ),
                text_color=PALETA["error"],
            )
            self.entry_password.delete(0, "end")
            self.entry_password.focus()
            return

        self._detener_reloj()

        from ui.tema import limpiar_cache_ui_sesion

        limpiar_cache_ui_sesion()
        self.destroy()
        principal = VentanaPrincipal(usuario_auth)
        mensaje_alerta = auth_service.consumir_alerta_inventario()
        if mensaje_alerta:
            principal.after(
                150,
                lambda: messagebox.showwarning(
                    "Revisión de inventario",
                    mensaje_alerta,
                    parent=principal,
                ),
            )
        principal.mainloop()
