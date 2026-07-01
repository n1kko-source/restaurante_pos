"""Consulta y movimientos de stock."""

from tkinter import messagebox, ttk
from typing import Dict, Optional

import customtkinter as ctk

from models.producto import ProductoListado
from services import inventario_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import (
    PALETA,
    PADDING_PANEL_H,
    PADDING_PANEL_INFERIOR,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_titulo,
    kwargs_boton_primario,
    kwargs_boton_secundario,
)


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


class VentanaInventario(ctk.CTkFrame):
    """Módulo de control de stock por producto."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=PALETA["fondo"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._pagina = 1
        self._total_paginas = 1
        self._productos_cache: Dict[str, ProductoListado] = {}

        self._construir_panel()
        self.refrescar()

    def _construir_panel(self) -> None:
        """Construye el listado paginado de stock."""
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
            text="Control de inventario",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 12), sticky="w")

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=1, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "Inventario")

        columnas = ("id", "nombre", "categoria", "stock", "activo")
        self._tree = ttk.Treeview(
            marco_tree,
            columns=columnas,
            show="headings",
            style="Inventario.Treeview",
            selectmode="browse",
        )
        encabezados = {
            "id": ("ID", 50),
            "nombre": ("Producto", 220),
            "categoria": ("Categoría", 140),
            "stock": ("Stock actual", 100),
            "activo": ("Activo", 70),
        }
        for col, (texto, ancho) in encabezados.items():
            self._tree.heading(col, text=texto)
            anchor = "e" if col in ("id", "stock") else "w"
            if col == "activo":
                anchor = "center"
            self._tree.column(col, width=ancho, stretch=(col == "nombre"), anchor=anchor)

        scroll = ttk.Scrollbar(marco_tree, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tree.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_botones())

        paginacion = ctk.CTkFrame(panel, fg_color="transparent")
        paginacion.grid(row=2, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="ew")
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
        acciones.grid(
            row=3, column=0, padx=PADDING_PANEL_H, pady=(4, PADDING_PANEL_INFERIOR), sticky="ew"
        )
        acciones.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_menos = ctk.CTkButton(
            acciones,
            text="−  Quitar stock",
            height=42,
            font=fuente_boton(),
            command=self._accion_decrementar,
            state="disabled",
            **kwargs_boton_secundario(),
        )
        self._btn_menos.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._btn_mas = ctk.CTkButton(
            acciones,
            text="+  Agregar stock",
            height=42,
            font=fuente_boton(),
            command=self._accion_incrementar,
            state="disabled",
            **kwargs_boton_primario(),
        )
        self._btn_mas.grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            acciones,
            text="Actualizar",
            height=42,
            font=fuente_normal(),
            command=self.refrescar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def refrescar(self) -> None:
        """Recarga la página actual del inventario."""
        try:
            productos, _total, total_paginas = inventario_service.listar_inventario_pagina(
                self._pagina
            )
        except ErrorAcceso as error:
            self._manejar_error(error)
            return

        self._total_paginas = total_paginas
        if self._pagina > total_paginas:
            self._pagina = total_paginas

        self._productos_cache.clear()
        for item in self._tree.get_children():
            self._tree.delete(item)

        for producto in productos:
            iid = str(producto.id)
            self._productos_cache[iid] = producto
            self._tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    producto.id,
                    producto.nombre,
                    producto.nombre_categoria,
                    producto.stock,
                    "Sí" if producto.esta_activo() else "No",
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

    def _producto_seleccionado(self) -> Optional[ProductoListado]:
        """Retorna el producto seleccionado en el Treeview."""
        seleccion = self._tree.selection()
        if not seleccion:
            return None
        return self._productos_cache.get(seleccion[0])

    def _actualizar_botones(self) -> None:
        """Habilita o deshabilita acciones según la selección."""
        hay_seleccion = self._producto_seleccionado() is not None
        estado = "normal" if hay_seleccion else "disabled"
        self._btn_mas.configure(state=estado)
        self._btn_menos.configure(state=estado)

    def _pagina_anterior(self) -> None:
        """Retrocede una página del listado."""
        if self._pagina > 1:
            self._pagina -= 1
            self.refrescar()

    def _pagina_siguiente(self) -> None:
        """Avanza una página del listado."""
        if self._pagina < self._total_paginas:
            self._pagina += 1
            self.refrescar()

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso en un diálogo."""
        titulo = "Acceso denegado" if isinstance(error, ErrorAcceso) else "Inventario"
        messagebox.showerror(titulo, str(error), parent=self.winfo_toplevel())

    def _accion_incrementar(self) -> None:
        """Suma una unidad al stock del producto seleccionado."""
        producto = self._producto_seleccionado()
        if producto is None:
            messagebox.showwarning("Inventario", "Seleccione un producto.", parent=self)
            return

        try:
            actualizado = inventario_service.incrementar_stock(producto.id)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._actualizar_fila(actualizado)

    def _accion_decrementar(self) -> None:
        """Resta una unidad al stock del producto seleccionado."""
        producto = self._producto_seleccionado()
        if producto is None:
            messagebox.showwarning("Inventario", "Seleccione un producto.", parent=self)
            return

        try:
            actualizado = inventario_service.decrementar_stock(producto.id)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._actualizar_fila(actualizado)

    def _actualizar_fila(self, producto: ProductoListado) -> None:
        """Actualiza una fila del Treeview sin recargar toda la página."""
        iid = str(producto.id)
        self._productos_cache[iid] = producto
        if self._tree.exists(iid):
            self._tree.item(
                iid,
                values=(
                    producto.id,
                    producto.nombre,
                    producto.nombre_categoria,
                    producto.stock,
                    "Sí" if producto.esta_activo() else "No",
                ),
            )


@requiere_rol("supervisor", "administrador")
def mostrar_en(contenedor) -> VentanaInventario:
    """
    Incrusta el módulo de inventario en el frame contenedor.
    Primera línea de defensa: decorador @requiere_rol.
    """
    ventana = VentanaInventario(contenedor)
    ventana.grid(row=0, column=0, sticky="nsew")
    contenedor.grid_columnconfigure(0, weight=1)
    contenedor.grid_rowconfigure(0, weight=1)
    return ventana
