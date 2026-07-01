"""Administración de usuarios (solo rol administrador)."""

from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from config import RUTA_ICONOS
from models.usuario import Usuario
from services import auth_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import (
    DesplegableProfesional,
    PALETA,
    aplicar_icono_ventana,
    centrar_ventana_sobre_padre,
    crear_imagen_asset,
    PADDING_PANEL_H,
    PADDING_PANEL_INFERIOR,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_titulo,
    kwargs_boton_primario,
    kwargs_boton_secundario,
)

_ROLES_UI: List[Tuple[str, str]] = [
    ("cajero", "Cajero"),
    ("supervisor", "Supervisor"),
    ("administrador", "Administrador"),
]
_ETIQUETA_ROL = {codigo: etiqueta for codigo, etiqueta in _ROLES_UI}

# Orden visual del filtro por rol (icono arriba, etiqueta abajo).
_ROLES_FILTRO: List[Tuple[str, str, str]] = [
    ("administrador", "Administrador", "administrador.png"),
    ("supervisor", "Supervisor", "supervisor.png"),
    ("cajero", "Cajero", "cajero.png"),
]
_ALTO_ICONO_FILTRO = 80


def _fuente_etiqueta_rol() -> ctk.CTkFont:
    """Fuente destacada para el nombre del rol en el selector."""
    return ctk.CTkFont(size=16, weight="bold")


def _configurar_estilo_treeview(estilo: ttk.Style, nombre: str) -> None:
    """Aplica el tema claro compartido a un Treeview."""
    estilo.layout(f"{nombre}.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    estilo.configure(
        f"{nombre}.Treeview",
        background=PALETA["tree_fondo"],
        foreground=PALETA["texto"],
        fieldbackground=PALETA["tree_fondo"],
        rowheight=28,
        borderwidth=0,
        font=("Segoe UI", 11),
    )
    estilo.map(
        f"{nombre}.Treeview",
        background=[("selected", PALETA["tree_seleccion"])],
        foreground=[("selected", PALETA["texto"])],
    )
    estilo.configure(
        f"{nombre}.Treeview.Heading",
        background=PALETA["fondo"],
        foreground=PALETA["texto_suave"],
        relief="flat",
        font=("Segoe UI", 11, "bold"),
    )


class _TarjetaFiltroRol(ctk.CTkFrame):
    """Selector visual de rol: icono grande y etiqueta clicable."""

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
            fg_color="transparent",
            corner_radius=12,
            border_width=0,
            border_color=PALETA["borde"],
        )
        self._codigo_rol = codigo_rol
        self._al_seleccionar = al_seleccionar
        self._seleccionado = False

        contenido = ctk.CTkFrame(self, fg_color="transparent")
        contenido.pack(fill="both", expand=True, padx=8, pady=10)

        if imagen is not None:
            lbl_icono = ctk.CTkLabel(
                contenido,
                image=imagen,
                text="",
                width=_ALTO_ICONO_FILTRO,
                height=_ALTO_ICONO_FILTRO,
            )
        else:
            lbl_icono = ctk.CTkLabel(
                contenido,
                text=etiqueta[0].upper(),
                font=ctk.CTkFont(size=32, weight="bold"),
                text_color=PALETA["acento"],
                width=_ALTO_ICONO_FILTRO,
                height=_ALTO_ICONO_FILTRO,
            )
        lbl_icono.pack(pady=(0, 8))

        lbl_texto = ctk.CTkLabel(
            contenido,
            text=etiqueta,
            font=_fuente_etiqueta_rol(),
            text_color=PALETA["texto"],
        )
        lbl_texto.pack()

        self._widgets_clic = (self, contenido, lbl_texto, lbl_icono)
        for widget in self._widgets_clic:
            widget.configure(cursor="hand2")
            widget.bind("<Button-1>", self._al_clic)
            widget.bind("<Enter>", self._al_entrar)
            widget.bind("<Leave>", self._al_salir)

    def _al_clic(self, _evento=None) -> None:
        """Notifica la selección del rol al contenedor."""
        self._al_seleccionar(self._codigo_rol)

    def _al_entrar(self, _evento=None) -> None:
        """Resalta la tarjeta al pasar el cursor si no está seleccionada."""
        if not self._seleccionado:
            self.configure(fg_color=PALETA["sidebar_hover"], border_width=0)

    def _al_salir(self, _evento=None) -> None:
        """Restaura el aspecto al salir del cursor."""
        self._aplicar_estado_seleccion()

    def marcar_seleccionado(self, activo: bool) -> None:
        """Actualiza el aspecto visual según si el rol está elegido."""
        self._seleccionado = activo
        self._aplicar_estado_seleccion()

    def _aplicar_estado_seleccion(self) -> None:
        if self._seleccionado:
            self.configure(
                fg_color=PALETA["sidebar_activo"],
                border_width=2,
                border_color=PALETA["boton_accion_borde"],
            )
        else:
            self.configure(
                fg_color="transparent",
                border_width=0,
                border_color=PALETA["borde"],
            )


class _DialogoUsuario(ctk.CTkToplevel):
    """Formulario modal para crear o editar un usuario del sistema."""

    def __init__(self, parent, usuario: Optional[Usuario] = None):
        super().__init__(parent)
        self._usuario = usuario
        self._resultado: Optional[Tuple[str, str, str, Optional[str]]] = None

        es_edicion = usuario is not None
        self.title("Editar usuario" if es_edicion else "Nuevo usuario")
        self.configure(fg_color=PALETA["fondo"])
        aplicar_icono_ventana(self)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        marco = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco.pack(padx=20, pady=20, fill="both", expand=True)
        marco.grid_columnconfigure(0, weight=1)

        fila = 0
        for etiqueta, clave in (
            ("Nombre completo", "nombre"),
            ("Nombre de usuario (login)", "usuario"),
        ):
            ctk.CTkLabel(
                marco,
                text=etiqueta,
                font=fuente_pequena(),
                text_color=PALETA["texto_suave"],
            ).grid(row=fila, column=0, padx=20, pady=(18 if fila == 0 else 8, 4), sticky="w")
            entrada = ctk.CTkEntry(
                marco,
                height=38,
                font=fuente_normal(),
                fg_color=PALETA["entrada_fondo"],
                border_color=PALETA["borde"],
                text_color=PALETA["texto"],
            )
            entrada.grid(row=fila + 1, column=0, padx=20, pady=(0, 8), sticky="ew")
            setattr(self, f"_entrada_{clave}", entrada)
            fila += 2

        if not es_edicion:
            ctk.CTkLabel(
                marco,
                text="Contraseña",
                font=fuente_pequena(),
                text_color=PALETA["texto_suave"],
            ).grid(row=fila, column=0, padx=20, pady=(8, 4), sticky="w")
            self._entrada_password = ctk.CTkEntry(
                marco,
                height=38,
                show="*",
                font=fuente_normal(),
                fg_color=PALETA["entrada_fondo"],
                border_color=PALETA["borde"],
                text_color=PALETA["texto"],
            )
            self._entrada_password.grid(row=fila + 1, column=0, padx=20, pady=(0, 8), sticky="ew")
            fila += 2
        else:
            self._entrada_password = None

        ctk.CTkLabel(
            marco,
            text="Rol",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=fila, column=0, padx=20, pady=(8, 4), sticky="w")

        self._combo_rol = DesplegableProfesional(
            marco,
            height=38,
            values=[etiqueta for _, etiqueta in _ROLES_UI],
            font=fuente_normal(),
        )
        self._combo_rol.grid(row=fila + 1, column=0, padx=20, pady=(0, 16), sticky="ew")

        if es_edicion:
            self._entrada_nombre.insert(0, usuario.nombre)
            self._entrada_usuario.insert(0, usuario.usuario)
            self._combo_rol.set(_ETIQUETA_ROL.get(usuario.rol, usuario.rol))
        else:
            self._combo_rol.set("Cajero")

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=fila + 2, column=0, sticky="ew", padx=20, pady=(0, 18))
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Cancelar",
            height=40,
            font=fuente_normal(),
            command=self._cancelar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            botones,
            text="Guardar",
            height=40,
            font=fuente_boton(),
            command=self._confirmar,
            **kwargs_boton_primario(),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Return>", lambda _e: self._confirmar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._entrada_nombre.focus_set()
        self._centrar(parent)

    @property
    def resultado(self) -> Optional[Tuple[str, str, str, Optional[str]]]:
        """Retorna (nombre, usuario, rol, password) o None si se canceló."""
        return self._resultado

    def _centrar(self, parent) -> None:
        """Centra el diálogo respecto al padre."""
        centrar_ventana_sobre_padre(self, parent)

    def _rol_seleccionado(self) -> str:
        """Convierte la etiqueta visible del combo al código de rol."""
        etiqueta = self._combo_rol.get()
        for codigo, texto in _ROLES_UI:
            if texto == etiqueta:
                return codigo
        raise ValueError("Seleccione un rol válido.")

    def _cancelar(self) -> None:
        self._resultado = None
        self.destroy()

    def _confirmar(self) -> None:
        nombre = self._entrada_nombre.get().strip()
        usuario = self._entrada_usuario.get().strip()
        if not nombre:
            messagebox.showerror("Dato requerido", "El nombre no puede estar vacío.", parent=self)
            return
        if not usuario:
            messagebox.showerror(
                "Dato requerido", "El nombre de usuario no puede estar vacío.", parent=self
            )
            return
        try:
            rol = self._rol_seleccionado()
        except ValueError as error:
            messagebox.showerror("Rol inválido", str(error), parent=self)
            return

        password = None
        if self._entrada_password is not None:
            password = self._entrada_password.get()
            if not password:
                messagebox.showerror(
                    "Dato requerido", "La contraseña no puede estar vacía.", parent=self
                )
                return

        self._resultado = (nombre, usuario, rol, password)
        self.destroy()


class _DialogoPassword(ctk.CTkToplevel):
    """Diálogo para establecer una contraseña nueva."""

    def __init__(self, parent, nombre_usuario: str):
        super().__init__(parent)
        self._resultado: Optional[str] = None

        self.title("Cambiar contraseña")
        self.configure(fg_color=PALETA["fondo"])
        aplicar_icono_ventana(self)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        marco = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco.pack(padx=20, pady=20, fill="both", expand=True)
        marco.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            marco,
            text=f"Nueva contraseña para: {nombre_usuario}",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
            wraplength=320,
        ).grid(row=0, column=0, padx=20, pady=(18, 12), sticky="w")

        for fila, (etiqueta, attr) in enumerate(
            (("Contraseña nueva", "_entrada_pass"), ("Confirmar contraseña", "_entrada_conf")),
            start=1,
        ):
            ctk.CTkLabel(
                marco,
                text=etiqueta,
                font=fuente_pequena(),
                text_color=PALETA["texto_suave"],
            ).grid(row=fila * 2 - 1, column=0, padx=20, pady=(8, 4), sticky="w")
            entrada = ctk.CTkEntry(
                marco,
                height=38,
                show="*",
                font=fuente_normal(),
                fg_color=PALETA["entrada_fondo"],
                border_color=PALETA["borde"],
                text_color=PALETA["texto"],
            )
            entrada.grid(row=fila * 2, column=0, padx=20, pady=(0, 8), sticky="ew")
            setattr(self, attr, entrada)

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=5, column=0, sticky="ew", padx=20, pady=(8, 18))
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Cancelar",
            height=40,
            font=fuente_normal(),
            command=self._cancelar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            botones,
            text="Guardar",
            height=40,
            font=fuente_boton(),
            command=self._confirmar,
            **kwargs_boton_primario(),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Return>", lambda _e: self._confirmar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._entrada_pass.focus_set()
        self._centrar(parent)

    @property
    def resultado(self) -> Optional[str]:
        """Retorna la contraseña nueva o None si se canceló."""
        return self._resultado

    def _centrar(self, parent) -> None:
        """Centra el diálogo respecto al padre."""
        centrar_ventana_sobre_padre(self, parent)

    def _cancelar(self) -> None:
        self._resultado = None
        self.destroy()

    def _confirmar(self) -> None:
        password = self._entrada_pass.get()
        confirmacion = self._entrada_conf.get()
        if not password:
            messagebox.showerror(
                "Dato requerido", "La contraseña no puede estar vacía.", parent=self
            )
            return
        if password != confirmacion:
            messagebox.showerror(
                "Contraseñas distintas",
                "La confirmación no coincide con la contraseña nueva.",
                parent=self,
            )
            return
        self._resultado = password
        self.destroy()


class VentanaUsuarios(ctk.CTkFrame):
    """Módulo de administración de usuarios del sistema."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=PALETA["fondo"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._pagina = 1
        self._total_paginas = 1
        self._rol_filtro: Optional[str] = None
        self._usuarios_cache: Dict[str, Usuario] = {}
        self._tarjetas_rol: Dict[str, _TarjetaFiltroRol] = {}
        self._imagenes_rol: List[ctk.CTkImage] = []

        self._construir_panel()
        self._seleccionar_rol("administrador")

    def _construir_panel(self) -> None:
        """Construye el listado paginado de usuarios con filtro por rol."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Gestión de usuarios",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 12), sticky="w")

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=1, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "Usuarios")

        columnas = ("id", "nombre", "usuario", "rol")
        self._tree = ttk.Treeview(
            marco_tree,
            columns=columnas,
            show="headings",
            style="Usuarios.Treeview",
            selectmode="browse",
        )
        encabezados = {
            "id": ("ID", 50),
            "nombre": ("Nombre", 200),
            "usuario": ("Usuario (login)", 160),
            "rol": ("Rol", 140),
        }
        for col, (texto, ancho) in encabezados.items():
            self._tree.heading(col, text=texto)
            anchor = "e" if col == "id" else "w"
            if col == "rol":
                anchor = "center"
            self._tree.column(col, width=ancho, stretch=(col == "nombre"), anchor=anchor)

        scroll = ttk.Scrollbar(marco_tree, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_botones())

        marco_roles = ctk.CTkFrame(panel, fg_color="transparent")
        marco_roles.grid(row=2, column=0, padx=PADDING_PANEL_H, pady=(4, 12), sticky="ew")
        marco_roles.grid_columnconfigure((0, 1, 2), weight=1)

        for columna, (codigo, etiqueta, archivo) in enumerate(_ROLES_FILTRO):
            ruta_icono = RUTA_ICONOS / archivo
            imagen = crear_imagen_asset(ruta_icono, _ALTO_ICONO_FILTRO, _ALTO_ICONO_FILTRO)
            if imagen is not None:
                self._imagenes_rol.append(imagen)
            tarjeta = _TarjetaFiltroRol(
                marco_roles,
                codigo_rol=codigo,
                etiqueta=etiqueta,
                imagen=imagen,
                al_seleccionar=self._seleccionar_rol,
            )
            tarjeta.grid(row=0, column=columna, sticky="nsew", padx=6)
            self._tarjetas_rol[codigo] = tarjeta

        paginacion = ctk.CTkFrame(panel, fg_color="transparent")
        paginacion.grid(row=3, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="ew")
        paginacion.grid_columnconfigure(1, weight=1)

        self._btn_ant = ctk.CTkButton(
            paginacion,
            text="Anterior",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_anterior,
            **kwargs_boton_secundario(),
        )
        self._btn_ant.grid(row=0, column=0, padx=(4, 8))

        self._label_pagina = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        )
        self._label_pagina.grid(row=0, column=1)

        self._btn_sig = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_siguiente,
            **kwargs_boton_secundario(),
        )
        self._btn_sig.grid(row=0, column=2, padx=(8, 4))

        acciones = ctk.CTkFrame(panel, fg_color="transparent")
        acciones.grid(row=4, column=0, padx=PADDING_PANEL_H, pady=(4, PADDING_PANEL_INFERIOR), sticky="ew")
        acciones.grid_columnconfigure((0, 1, 2, 3), weight=1)

        ctk.CTkButton(
            acciones,
            text="+  Nuevo usuario",
            height=42,
            font=fuente_boton(),
            command=self._accion_nuevo,
            **kwargs_boton_primario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._btn_editar = ctk.CTkButton(
            acciones,
            text="Editar",
            height=42,
            font=fuente_normal(),
            command=self._accion_editar,
            state="disabled",
            **kwargs_boton_secundario(),
        )
        self._btn_editar.grid(row=0, column=1, sticky="ew", padx=6)

        self._btn_password = ctk.CTkButton(
            acciones,
            text="Cambiar contraseña",
            height=42,
            font=fuente_normal(),
            command=self._accion_password,
            state="disabled",
            **kwargs_boton_secundario(),
        )
        self._btn_password.grid(row=0, column=2, sticky="ew", padx=6)

        self._btn_eliminar = ctk.CTkButton(
            acciones,
            text="Eliminar",
            height=42,
            font=fuente_normal(),
            fg_color=PALETA["cerrar_sesion"],
            hover_color=PALETA["cerrar_sesion_hover"],
            text_color="#ffffff",
            text_color_disabled="#ffffff",
            command=self._accion_eliminar,
            state="disabled",
        )
        self._btn_eliminar.grid(row=0, column=3, sticky="ew", padx=(6, 0))

    def _seleccionar_rol(self, codigo_rol: str) -> None:
        """Filtra el listado por el rol elegido y reinicia la paginación."""
        self._rol_filtro = codigo_rol
        self._pagina = 1
        for codigo, tarjeta in self._tarjetas_rol.items():
            tarjeta.marcar_seleccionado(codigo == codigo_rol)
        self.refrescar()

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso en un diálogo."""
        if isinstance(error, ErrorAcceso):
            messagebox.showerror("Acceso denegado", str(error))
        else:
            messagebox.showerror("Usuarios", str(error))

    def _usuario_seleccionado(self) -> Optional[Usuario]:
        """Retorna el usuario seleccionado en el Treeview."""
        seleccion = self._tree.selection()
        if not seleccion:
            return None
        return self._usuarios_cache.get(seleccion[0])

    def _actualizar_botones(self) -> None:
        """Habilita acciones según haya fila seleccionada."""
        hay_seleccion = self._usuario_seleccionado() is not None
        estado = "normal" if hay_seleccion else "disabled"
        self._btn_editar.configure(state=estado)
        self._btn_password.configure(state=estado)
        self._btn_eliminar.configure(state=estado)

    def refrescar(self) -> None:
        """Recarga la página actual desde el servicio, filtrada por rol."""
        if self._rol_filtro is None:
            return

        try:
            usuarios, _total, total_paginas = auth_service.listar_usuarios_pagina(
                self._pagina,
                rol=self._rol_filtro,
            )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._total_paginas = total_paginas
        if self._pagina > total_paginas:
            self._pagina = total_paginas
            self.refrescar()
            return

        self._usuarios_cache.clear()
        for item in self._tree.get_children():
            self._tree.delete(item)

        for usuario in usuarios:
            iid = str(usuario.id)
            self._usuarios_cache[iid] = usuario
            self._tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    usuario.id,
                    usuario.nombre,
                    usuario.usuario,
                    _ETIQUETA_ROL.get(usuario.rol, usuario.rol),
                ),
            )

        self._label_pagina.configure(
            text=f"Página {self._pagina} de {self._total_paginas}"
        )
        self._btn_ant.configure(state="normal" if self._pagina > 1 else "disabled")
        self._btn_sig.configure(
            state="normal" if self._pagina < self._total_paginas else "disabled"
        )
        self._actualizar_botones()

    def _pagina_anterior(self) -> None:
        if self._pagina > 1:
            self._pagina -= 1
            self.refrescar()

    def _pagina_siguiente(self) -> None:
        if self._pagina < self._total_paginas:
            self._pagina += 1
            self.refrescar()

    def _accion_nuevo(self) -> None:
        """Abre el formulario para registrar un usuario nuevo."""
        dialogo = _DialogoUsuario(self.winfo_toplevel())
        self.wait_window(dialogo)
        datos = dialogo.resultado
        if datos is None:
            return

        nombre, usuario, rol, password = datos
        try:
            auth_service.crear_usuario(nombre, usuario, password, rol)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Usuarios", f"Usuario '{usuario}' creado correctamente.")
        self.refrescar()

    def _accion_editar(self) -> None:
        """Abre el formulario para editar el usuario seleccionado."""
        usuario = self._usuario_seleccionado()
        if usuario is None:
            messagebox.showwarning("Usuarios", "Seleccione un usuario para editar.")
            return

        dialogo = _DialogoUsuario(self.winfo_toplevel(), usuario=usuario)
        self.wait_window(dialogo)
        datos = dialogo.resultado
        if datos is None:
            return

        nombre, login, rol, _password = datos
        try:
            auth_service.actualizar_usuario(usuario.id, nombre, login, rol)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Usuarios", f"Usuario '{login}' actualizado.")
        self.refrescar()

    def _accion_password(self) -> None:
        """Cambia la contraseña del usuario seleccionado."""
        usuario = self._usuario_seleccionado()
        if usuario is None:
            messagebox.showwarning("Usuarios", "Seleccione un usuario.")
            return

        dialogo = _DialogoPassword(self.winfo_toplevel(), usuario.nombre)
        self.wait_window(dialogo)
        password = dialogo.resultado
        if password is None:
            return

        try:
            auth_service.cambiar_password(usuario.id, password)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo(
            "Usuarios", f"Contraseña de '{usuario.usuario}' actualizada."
        )

    def _accion_eliminar(self) -> None:
        """Elimina el usuario seleccionado tras confirmación."""
        usuario = self._usuario_seleccionado()
        if usuario is None:
            messagebox.showwarning("Usuarios", "Seleccione un usuario para eliminar.")
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Eliminar al usuario '{usuario.usuario}' ({usuario.nombre})?\n\n"
            "Esta acción no se puede deshacer.",
        )
        if not confirmar:
            return

        try:
            auth_service.eliminar_usuario(usuario.id)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Usuarios", f"Usuario '{usuario.usuario}' eliminado.")
        self.refrescar()


@requiere_rol("administrador")
def mostrar_en(contenedor) -> VentanaUsuarios:
    """
    Incrusta el módulo de usuarios en el frame contenedor.
    Primera línea de defensa: decorador @requiere_rol.
    """
    ventana = VentanaUsuarios(contenedor)
    ventana.grid(row=0, column=0, sticky="nsew")
    contenedor.grid_columnconfigure(0, weight=1)
    contenedor.grid_rowconfigure(0, weight=1)
    return ventana
