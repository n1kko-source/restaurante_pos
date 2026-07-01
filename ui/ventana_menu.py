"""Gestión de productos y categorías del menú."""

from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk

from models.categoria import Categoria
from models.producto import ProductoListado
from services import menu_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import (
    DesplegableProfesional,
    PALETA,
    aplicar_icono_ventana,
    centrar_ventana_sobre_padre,
    PADDING_PANEL_H,
    PADDING_PANEL_INFERIOR,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
    kwargs_boton_primario,
    kwargs_boton_secundario,
)


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"${monto:,.0f}".replace(",", ".")


def _parsear_entero(texto: str) -> int:
    """Convierte texto con o sin separadores a entero."""
    limpio = texto.strip().replace("$", "").replace(".", "").replace(",", "")
    if not limpio:
        return 0
    return int(limpio)


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


class _DialogoTexto(ctk.CTkToplevel):
    """Diálogo modal para ingresar un texto (categoría nueva o renombrar)."""

    def __init__(
        self,
        parent,
        titulo: str,
        etiqueta: str,
        valor_inicial: str = "",
        texto_boton: str = "Guardar",
    ):
        super().__init__(parent)
        self._resultado: Optional[str] = None

        self.title(titulo)
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
            text=etiqueta,
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        self._entrada = ctk.CTkEntry(
            marco,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            border_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self._entrada.insert(0, valor_inicial)
        self._entrada.grid(row=1, column=0, padx=20, pady=(0, 16), sticky="ew")

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 18))
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
            text=texto_boton,
            height=40,
            font=fuente_boton(),
            command=self._confirmar,
            **kwargs_boton_primario(),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Return>", lambda _e: self._confirmar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._entrada.focus_set()
        self._centrar(parent)

    @property
    def resultado(self) -> Optional[str]:
        """Retorna el texto ingresado o None si se canceló."""
        return self._resultado

    def _centrar(self, parent) -> None:
        """Centra el diálogo respecto al padre."""
        centrar_ventana_sobre_padre(self, parent)

    def _cancelar(self) -> None:
        self._resultado = None
        self.destroy()

    def _confirmar(self) -> None:
        texto = self._entrada.get().strip()
        if not texto:
            messagebox.showerror("Dato requerido", "El campo no puede estar vacío.", parent=self)
            return
        self._resultado = texto
        self.destroy()


class _DialogoProducto(ctk.CTkToplevel):
    """Formulario modal para crear o editar un producto del menú."""

    def __init__(
        self,
        parent,
        categorias: List[Categoria],
        producto: Optional[ProductoListado] = None,
    ):
        super().__init__(parent)
        self._categorias = categorias
        self._producto = producto
        self._mapa_etiquetas: Dict[str, int] = {}
        self._resultado: Optional[Tuple[int, str, int, int]] = None

        es_edicion = producto is not None
        self.title("Editar producto" if es_edicion else "Nuevo producto")
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
            text="Editar producto" if es_edicion else "Agregar producto",
            font=fuente_subtitulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 12), sticky="w")

        fila = 1
        for etiqueta, clave in (
            ("Nombre", "nombre"),
            ("Precio (COP)", "precio"),
            ("Stock", "stock"),
        ):
            ctk.CTkLabel(
                marco,
                text=etiqueta,
                font=fuente_pequena(),
                text_color=PALETA["texto_suave"],
            ).grid(row=fila, column=0, padx=20, sticky="w")
            fila += 1
            entrada = ctk.CTkEntry(
                marco,
                height=38,
                font=fuente_normal(),
                fg_color=PALETA["entrada_fondo"],
                border_color=PALETA["borde"],
                text_color=PALETA["texto"],
            )
            entrada.grid(row=fila, column=0, padx=20, pady=(4, 10), sticky="ew")
            setattr(self, f"_entrada_{clave}", entrada)
            fila += 1

        ctk.CTkLabel(
            marco,
            text="Categoría",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=fila, column=0, padx=20, sticky="w")
        fila += 1

        if not categorias:
            valores = ["Sin categorías"]
        else:
            valores = [cat.nombre for cat in categorias]
            self._mapa_etiquetas = {cat.nombre: cat.id for cat in categorias}

        self._menu_categoria = DesplegableProfesional(
            marco,
            values=valores,
            height=38,
            font=fuente_normal(),
        )
        self._menu_categoria.grid(row=fila, column=0, padx=20, pady=(4, 16), sticky="ew")
        fila += 1

        if es_edicion and producto is not None:
            self._entrada_nombre.insert(0, producto.nombre)
            self._entrada_precio.insert(0, str(producto.precio))
            self._entrada_stock.insert(0, str(producto.stock))
            if producto.nombre_categoria in valores:
                self._menu_categoria.set(producto.nombre_categoria)
        elif categorias:
            self._menu_categoria.set(categorias[0].nombre)

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=fila, column=0, sticky="ew", padx=20, pady=(0, 18))
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
    def resultado(self) -> Optional[Tuple[int, str, int, int]]:
        """Retorna (categoria_id, nombre, precio, stock) o None si canceló."""
        return self._resultado

    def _centrar(self, parent) -> None:
        centrar_ventana_sobre_padre(self, parent)

    def _cancelar(self) -> None:
        self._resultado = None
        self.destroy()

    def _confirmar(self) -> None:
        if not self._categorias:
            messagebox.showerror(
                "Sin categorías",
                "Cree al menos una categoría antes de agregar productos.",
                parent=self,
            )
            return

        nombre = self._entrada_nombre.get().strip()
        if not nombre:
            messagebox.showerror("Dato requerido", "Ingrese el nombre del producto.", parent=self)
            return

        try:
            precio = _parsear_entero(self._entrada_precio.get())
            stock = _parsear_entero(self._entrada_stock.get())
        except ValueError:
            messagebox.showerror(
                "Valor inválido",
                "Precio y stock deben ser números enteros.",
                parent=self,
            )
            return

        etiqueta_cat = self._menu_categoria.get()
        categoria_id = self._mapa_etiquetas.get(etiqueta_cat)
        if categoria_id is None:
            messagebox.showerror("Categoría inválida", "Seleccione una categoría.", parent=self)
            return

        self._resultado = (categoria_id, nombre, precio, stock)
        self.destroy()


class VentanaMenu(ctk.CTkFrame):
    """Módulo de gestión de productos y categorías del menú."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=PALETA["fondo"])
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._pagina_productos = 1
        self._total_paginas_productos = 1
        self._pagina_categorias = 1
        self._total_paginas_categorias = 1
        self._filtro_categoria_id: Optional[int] = None
        self._mapa_filtro: Dict[str, int] = {}
        self._productos_cache: Dict[str, ProductoListado] = {}

        self._construir_panel_productos()
        self._construir_panel_categorias()
        self.refrescar()

    def _construir_panel_productos(self) -> None:
        """Panel principal con listado paginado de productos."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            panel,
            text="Productos del menú",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

        filtro = ctk.CTkFrame(panel, fg_color="transparent")
        filtro.grid(row=1, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="ew")
        filtro.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            filtro,
            text="Filtrar por categoría:",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=(4, 8), sticky="w")

        self._menu_filtro = DesplegableProfesional(
            filtro,
            values=["Todas las categorías"],
            height=36,
            font=fuente_normal(),
            command=self._al_cambiar_filtro,
        )
        self._menu_filtro.grid(row=0, column=1, sticky="ew", padx=(0, 4))

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=2, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "Menu.Productos")

        columnas = ("id", "nombre", "categoria", "precio", "stock", "activo")
        self._tree_productos = ttk.Treeview(
            marco_tree,
            columns=columnas,
            show="headings",
            style="Menu.Productos.Treeview",
            selectmode="browse",
        )
        encabezados = {
            "id": ("ID", 50),
            "nombre": ("Nombre", 180),
            "categoria": ("Categoría", 120),
            "precio": ("Precio", 90),
            "stock": ("Stock", 70),
            "activo": ("Activo", 70),
        }
        for col, (texto, ancho) in encabezados.items():
            self._tree_productos.heading(col, text=texto)
            anchor = "e" if col in ("id", "precio", "stock") else "w"
            if col == "activo":
                anchor = "center"
            self._tree_productos.column(col, width=ancho, stretch=(col == "nombre"), anchor=anchor)

        scroll = ttk.Scrollbar(
            marco_tree, orient="vertical", command=self._tree_productos.yview
        )
        self._tree_productos.configure(yscrollcommand=scroll.set)
        self._tree_productos.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tree_productos.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_botones())
        self._tree_productos.bind("<Double-Button-1>", lambda _e: self._accion_editar())

        paginacion = ctk.CTkFrame(panel, fg_color="transparent")
        paginacion.grid(row=3, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="ew")
        paginacion.grid_columnconfigure(1, weight=1)

        self._btn_prod_ant = ctk.CTkButton(
            paginacion,
            text="Anterior",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_productos_anterior,
            **kwargs_boton_secundario(),
        )
        self._btn_prod_ant.grid(row=0, column=0, padx=(4, 8))

        self._label_pagina_productos = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        )
        self._label_pagina_productos.grid(row=0, column=1)

        self._btn_prod_sig = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_productos_siguiente,
            **kwargs_boton_secundario(),
        )
        self._btn_prod_sig.grid(row=0, column=2, padx=(8, 4))

        acciones = ctk.CTkFrame(panel, fg_color="transparent")
        acciones.grid(row=4, column=0, padx=PADDING_PANEL_H, pady=(4, PADDING_PANEL_INFERIOR), sticky="ew")
        acciones.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_agregar = ctk.CTkButton(
            acciones,
            text="+  Agregar producto",
            height=42,
            font=fuente_boton(),
            command=self._accion_agregar,
            **kwargs_boton_primario(),
        )
        self._btn_agregar.grid(row=0, column=0, sticky="ew", padx=(0, 6))

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

        self._btn_toggle_activo = ctk.CTkButton(
            acciones,
            text="Activar / Desactivar",
            height=42,
            font=fuente_normal(),
            command=self._accion_toggle_activo,
            state="disabled",
            **kwargs_boton_secundario(),
        )
        self._btn_toggle_activo.grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _construir_panel_categorias(self) -> None:
        """Panel lateral para gestionar categorías."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Categorías",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=1, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "Menu.Categorias")

        self._tree_categorias = ttk.Treeview(
            marco_tree,
            columns=("id", "nombre"),
            show="headings",
            style="Menu.Categorias.Treeview",
            selectmode="browse",
        )
        self._tree_categorias.heading("id", text="ID")
        self._tree_categorias.heading("nombre", text="Nombre")
        self._tree_categorias.column("id", width=40, stretch=False, anchor="e")
        self._tree_categorias.column("nombre", width=160, stretch=True, anchor="w")

        scroll = ttk.Scrollbar(
            marco_tree, orient="vertical", command=self._tree_categorias.yview
        )
        self._tree_categorias.configure(yscrollcommand=scroll.set)
        self._tree_categorias.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        paginacion = ctk.CTkFrame(panel, fg_color="transparent")
        paginacion.grid(row=2, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="ew")
        paginacion.grid_columnconfigure(1, weight=1)

        self._btn_cat_ant = ctk.CTkButton(
            paginacion,
            text="Ant.",
            width=64,
            height=30,
            font=fuente_pequena(),
            command=self._pagina_categorias_anterior,
            **kwargs_boton_secundario(),
        )
        self._btn_cat_ant.grid(row=0, column=0, padx=(4, 6))

        self._label_pagina_categorias = ctk.CTkLabel(
            paginacion,
            text="Pág. 1/1",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        )
        self._label_pagina_categorias.grid(row=0, column=1)

        self._btn_cat_sig = ctk.CTkButton(
            paginacion,
            text="Sig.",
            width=64,
            height=30,
            font=fuente_pequena(),
            command=self._pagina_categorias_siguiente,
            **kwargs_boton_secundario(),
        )
        self._btn_cat_sig.grid(row=0, column=2, padx=(6, 4))

        acciones = ctk.CTkFrame(panel, fg_color="transparent")
        acciones.grid(row=3, column=0, padx=PADDING_PANEL_H, pady=(4, PADDING_PANEL_INFERIOR), sticky="ew")
        acciones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            acciones,
            text="+  Nueva",
            height=40,
            font=fuente_normal(),
            command=self._accion_nueva_categoria,
            **kwargs_boton_primario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            acciones,
            text="Renombrar",
            height=40,
            font=fuente_normal(),
            command=self._accion_renombrar_categoria,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def refrescar(self) -> None:
        """Recarga categorías, filtro y productos."""
        try:
            self._cargar_filtro_categorias()
            self._cargar_categorias()
            self._cargar_productos()
        except ErrorAcceso as error:
            self._manejar_error(error)

    def _cargar_filtro_categorias(self) -> None:
        """Actualiza el dropdown de filtro por categoría."""
        categorias = menu_service.listar_categorias_selector()
        valores = ["Todas las categorías"] + [cat.nombre for cat in categorias]
        self._mapa_filtro = {cat.nombre: cat.id for cat in categorias}

        seleccion_actual = self._menu_filtro.get()
        self._menu_filtro.configure(values=valores)
        if seleccion_actual in valores:
            self._menu_filtro.set(seleccion_actual)
        else:
            self._menu_filtro.set("Todas las categorías")
            self._filtro_categoria_id = None

    def _cargar_categorias(self) -> None:
        """Carga la página actual del Treeview de categorías."""
        categorias, _total, total_paginas = menu_service.listar_categorias_pagina(
            self._pagina_categorias
        )
        self._total_paginas_categorias = total_paginas
        if self._pagina_categorias > total_paginas:
            self._pagina_categorias = total_paginas

        for item in self._tree_categorias.get_children():
            self._tree_categorias.delete(item)

        for categoria in categorias:
            self._tree_categorias.insert(
                "",
                "end",
                iid=str(categoria.id),
                values=(categoria.id, categoria.nombre),
            )

        self._label_pagina_categorias.configure(
            text=f"Pág. {self._pagina_categorias}/{self._total_paginas_categorias}"
        )
        self._btn_cat_ant.configure(
            state="normal" if self._pagina_categorias > 1 else "disabled"
        )
        self._btn_cat_sig.configure(
            state="normal"
            if self._pagina_categorias < self._total_paginas_categorias
            else "disabled"
        )

    def _cargar_productos(self) -> None:
        """Carga la página actual del Treeview de productos."""
        productos, _total, total_paginas = menu_service.listar_productos_pagina(
            self._pagina_productos,
            categoria_id=self._filtro_categoria_id,
        )
        self._total_paginas_productos = total_paginas
        if self._pagina_productos > total_paginas:
            self._pagina_productos = total_paginas

        self._productos_cache.clear()
        for item in self._tree_productos.get_children():
            self._tree_productos.delete(item)

        for producto in productos:
            iid = str(producto.id)
            self._productos_cache[iid] = producto
            estado = "Sí" if producto.esta_activo() else "No"
            self._tree_productos.insert(
                "",
                "end",
                iid=iid,
                values=(
                    producto.id,
                    producto.nombre,
                    producto.nombre_categoria,
                    _formatear_pesos(producto.precio),
                    producto.stock,
                    estado,
                ),
            )

        self._label_pagina_productos.configure(
            text=f"Página {self._pagina_productos} de {self._total_paginas_productos}"
        )
        self._btn_prod_ant.configure(
            state="normal" if self._pagina_productos > 1 else "disabled"
        )
        self._btn_prod_sig.configure(
            state="normal"
            if self._pagina_productos < self._total_paginas_productos
            else "disabled"
        )
        self._actualizar_botones()

    def _al_cambiar_filtro(self, etiqueta: str) -> None:
        """Aplica el filtro por categoría y vuelve a la primera página."""
        if etiqueta == "Todas las categorías":
            self._filtro_categoria_id = None
        else:
            self._filtro_categoria_id = self._mapa_filtro.get(etiqueta)
        self._pagina_productos = 1
        try:
            self._cargar_productos()
        except ErrorAcceso as error:
            self._manejar_error(error)

    def _pagina_productos_anterior(self) -> None:
        if self._pagina_productos > 1:
            self._pagina_productos -= 1
            self._cargar_productos()

    def _pagina_productos_siguiente(self) -> None:
        if self._pagina_productos < self._total_paginas_productos:
            self._pagina_productos += 1
            self._cargar_productos()

    def _pagina_categorias_anterior(self) -> None:
        if self._pagina_categorias > 1:
            self._pagina_categorias -= 1
            self._cargar_categorias()

    def _pagina_categorias_siguiente(self) -> None:
        if self._pagina_categorias < self._total_paginas_categorias:
            self._pagina_categorias += 1
            self._cargar_categorias()

    def _producto_seleccionado(self) -> Optional[ProductoListado]:
        """Retorna el producto seleccionado en el Treeview."""
        seleccion = self._tree_productos.selection()
        if not seleccion:
            return None
        return self._productos_cache.get(seleccion[0])

    def _categoria_seleccionada(self) -> Optional[Categoria]:
        """Retorna la categoría seleccionada en el panel lateral."""
        seleccion = self._tree_categorias.selection()
        if not seleccion:
            return None
        valores = self._tree_categorias.item(seleccion[0], "values")
        return Categoria(id=int(valores[0]), nombre=str(valores[1]))

    def _actualizar_botones(self) -> None:
        """Habilita o deshabilita acciones según la selección."""
        producto = self._producto_seleccionado()
        if producto is None:
            self._btn_editar.configure(state="disabled")
            self._btn_toggle_activo.configure(state="disabled", text="Activar / Desactivar")
            return
        self._btn_editar.configure(state="normal")
        self._btn_toggle_activo.configure(state="normal")
        if producto.esta_activo():
            self._btn_toggle_activo.configure(text="Desactivar")
        else:
            self._btn_toggle_activo.configure(text="Activar")

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso."""
        if isinstance(error, ErrorAcceso):
            messagebox.showerror("Acceso denegado", str(error))
        else:
            messagebox.showerror("Error", str(error))

    def _accion_agregar(self) -> None:
        """Abre el formulario para crear un producto."""
        try:
            categorias = menu_service.listar_categorias_selector()
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        if not categorias:
            messagebox.showwarning(
                "Menú",
                "Cree al menos una categoría antes de agregar productos.",
            )
            return

        dialogo = _DialogoProducto(self.winfo_toplevel(), categorias)
        self.wait_window(dialogo)
        datos = dialogo.resultado
        if datos is None:
            return

        categoria_id, nombre, precio, stock = datos
        try:
            menu_service.crear_producto(categoria_id, nombre, precio, stock)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Menú", f"Producto '{nombre}' creado correctamente.")
        self.refrescar()

    def _accion_editar(self) -> None:
        """Abre el formulario para editar el producto seleccionado."""
        producto = self._producto_seleccionado()
        if producto is None:
            messagebox.showwarning("Menú", "Seleccione un producto para editar.")
            return

        try:
            categorias = menu_service.listar_categorias_selector()
            producto = menu_service.obtener_producto(producto.id)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        dialogo = _DialogoProducto(
            self.winfo_toplevel(),
            categorias,
            producto=producto,
        )
        self.wait_window(dialogo)
        datos = dialogo.resultado
        if datos is None:
            return

        categoria_id, nombre, precio, stock = datos
        try:
            menu_service.actualizar_producto(
                producto.id, categoria_id, nombre, precio, stock
            )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Menú", f"Producto '{nombre}' actualizado.")
        self.refrescar()

    def _accion_toggle_activo(self) -> None:
        """Activa o desactiva el producto seleccionado (soft delete)."""
        producto = self._producto_seleccionado()
        if producto is None:
            messagebox.showwarning("Menú", "Seleccione un producto.")
            return

        try:
            if producto.esta_activo():
                menu_service.desactivar_producto(producto.id)
                mensaje = f"Producto '{producto.nombre}' desactivado."
            else:
                menu_service.activar_producto(producto.id)
                mensaje = f"Producto '{producto.nombre}' activado."
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Menú", mensaje)
        self.refrescar()

    def _accion_nueva_categoria(self) -> None:
        """Crea una categoría nueva mediante diálogo."""
        dialogo = _DialogoTexto(
            self.winfo_toplevel(),
            titulo="Nueva categoría",
            etiqueta="Nombre de la categoría",
            texto_boton="Crear",
        )
        self.wait_window(dialogo)
        nombre = dialogo.resultado
        if nombre is None:
            return

        try:
            menu_service.crear_categoria(nombre)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Menú", f"Categoría '{nombre}' creada.")
        self.refrescar()

    def _accion_renombrar_categoria(self) -> None:
        """Renombra la categoría seleccionada."""
        categoria = self._categoria_seleccionada()
        if categoria is None:
            messagebox.showwarning("Menú", "Seleccione una categoría para renombrar.")
            return

        dialogo = _DialogoTexto(
            self.winfo_toplevel(),
            titulo="Renombrar categoría",
            etiqueta="Nuevo nombre",
            valor_inicial=categoria.nombre,
            texto_boton="Guardar",
        )
        self.wait_window(dialogo)
        nombre = dialogo.resultado
        if nombre is None:
            return

        try:
            menu_service.renombrar_categoria(categoria.id, nombre)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        messagebox.showinfo("Menú", f"Categoría renombrada a '{nombre}'.")
        self.refrescar()


@requiere_rol("supervisor", "administrador")
def mostrar_en(contenedor) -> VentanaMenu:
    """
    Incrusta el módulo de menú en el frame contenedor.
    Primera línea de defensa: decorador @requiere_rol.
    """
    ventana = VentanaMenu(contenedor)
    ventana.grid(row=0, column=0, sticky="nsew")
    contenedor.grid_columnconfigure(0, weight=1)
    contenedor.grid_rowconfigure(0, weight=1)
    return ventana
