"""Punto de venta vinculado a la mesa activa."""

from tkinter import messagebox, ttk
from typing import Callable, Dict, Optional

import customtkinter as ctk

from services import pedido_service
from services.auth_service import ErrorAcceso, requiere_rol
from services.pedido_service import ProductoCatalogo
from ui.tema import (
    PALETA,
    PADDING_PANEL_H,
    PADDING_PANEL_INFERIOR,
    centrar_ventana,
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


class _DialogoCantidad(ctk.CTkToplevel):
    """Diálogo modal para ingresar una cantidad entera positiva."""

    def __init__(self, parent, titulo: str, valor_inicial: int = 1):
        super().__init__(parent)
        self.title(titulo)
        self.configure(fg_color=PALETA["fondo"])
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._resultado: Optional[int] = None
        self._valor_min = 1

        marco = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco.pack(padx=20, pady=20, fill="both", expand=True)
        marco.grid_columnconfigure(0, weight=1)

        if " — " in titulo:
            etiqueta_producto = titulo.split(" — ", 1)[1]
        else:
            etiqueta_producto = titulo

        ctk.CTkLabel(
            marco,
            text="Cantidad",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        ctk.CTkLabel(
            marco,
            text=etiqueta_producto,
            font=fuente_subtitulo(),
            text_color=PALETA["texto"],
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        fila_cantidad = ctk.CTkFrame(marco, fg_color="transparent")
        fila_cantidad.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        fila_cantidad.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            fila_cantidad,
            text="−",
            width=48,
            height=42,
            font=fuente_boton(),
            command=self._restar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, padx=(0, 8))

        self._entrada = ctk.CTkEntry(
            fila_cantidad,
            height=42,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            border_color=PALETA["entrada_borde"],
            text_color=PALETA["texto"],
            justify="center",
        )
        self._entrada.grid(row=0, column=1, sticky="ew")
        self._entrada.insert(0, str(max(valor_inicial, self._valor_min)))
        self._entrada.select_range(0, "end")
        self._entrada.focus_set()
        self._entrada.bind("<Return>", lambda _e: self._confirmar())

        ctk.CTkButton(
            fila_cantidad,
            text="+",
            width=48,
            height=42,
            font=fuente_boton(),
            command=self._sumar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=2, padx=(8, 0))

        fila_botones = ctk.CTkFrame(marco, fg_color="transparent")
        fila_botones.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        fila_botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            fila_botones,
            text="Cancelar",
            height=42,
            font=fuente_normal(),
            command=self._cancelar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            fila_botones,
            text="Aceptar",
            height=42,
            font=fuente_boton(),
            command=self._confirmar,
            **kwargs_boton_primario(),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _e: self._cancelar())
        centrar_ventana(self, 400, 300, parent=parent)
        self.wait_window()

    def _leer_cantidad(self) -> int:
        """Lee la cantidad del campo o retorna el mínimo si no es válida."""
        texto = self._entrada.get().strip()
        if texto.isdigit():
            return max(self._valor_min, int(texto))
        return self._valor_min

    def _establecer_cantidad(self, valor: int) -> None:
        """Actualiza el campo con una cantidad entera válida."""
        valor = max(self._valor_min, valor)
        self._entrada.delete(0, "end")
        self._entrada.insert(0, str(valor))

    def _sumar(self) -> None:
        """Incrementa la cantidad en una unidad."""
        self._establecer_cantidad(self._leer_cantidad() + 1)

    def _restar(self) -> None:
        """Decrementa la cantidad sin bajar del mínimo."""
        self._establecer_cantidad(self._leer_cantidad() - 1)

    def _confirmar(self) -> None:
        """Valida la entrada y cierra con el valor ingresado."""
        texto = self._entrada.get().strip()
        if not texto.isdigit():
            messagebox.showwarning("Cantidad", "Ingrese un número entero positivo.")
            return
        valor = int(texto)
        if valor <= 0:
            messagebox.showwarning("Cantidad", "La cantidad debe ser mayor a cero.")
            return
        self._resultado = valor
        self.destroy()

    def _cancelar(self) -> None:
        """Cierra sin resultado."""
        self.destroy()

    def resultado(self) -> Optional[int]:
        """Retorna la cantidad ingresada o None si se canceló."""
        return self._resultado


class VentanaPOS:
    """Ventana de punto de venta con catálogo y gestión del pedido activo."""

    def __init__(
        self,
        parent,
        mesa_id: int,
        pedido_id: int,
        al_cerrar: Optional[Callable[[], None]] = None,
    ):
        self._parent = parent
        self._mesa_id = mesa_id
        self._pedido_id = pedido_id
        self._al_cerrar = al_cerrar
        self._mesa_numero = mesa_id
        self._mapa_productos: Dict[str, ProductoCatalogo] = {}
        self._timer_busqueda: Optional[str] = None

        try:
            mesa, _pedido = pedido_service.validar_acceso_pos(mesa_id, pedido_id)
            self._mesa_numero = mesa.numero
        except ValueError as error:
            messagebox.showerror("Punto de venta", str(error))
            if al_cerrar is not None:
                al_cerrar()
            return

        self._ventana = ctk.CTkToplevel(parent)
        self._ventana.title(f"Punto de venta — Mesa {self._mesa_numero}")
        self._ventana.configure(fg_color=PALETA["fondo"])
        self._ventana.transient(parent)
        self._ventana.grab_set()

        self._ventana.grid_columnconfigure(0, weight=1)
        self._ventana.grid_rowconfigure(1, weight=1)

        self._construir_encabezado()
        self._construir_cuerpo()
        self._construir_pie()

        centrar_ventana(self._ventana, 1040, 640, parent=parent)

        self._ventana.protocol("WM_DELETE_WINDOW", self._cerrar)
        self._cargar_catalogo()
        self._refrescar_pedido()

    def _construir_encabezado(self) -> None:
        """Barra superior con mesa y número de pedido."""
        encabezado = ctk.CTkFrame(
            self._ventana,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        encabezado.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Punto de venta",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(14, 0), sticky="w")

        ctk.CTkLabel(
            encabezado,
            text=f"Mesa {self._mesa_numero}  ·  Pedido #{self._pedido_id}",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, padx=20, pady=(4, 14), sticky="w")

    def _construir_cuerpo(self) -> None:
        """Panel izquierdo (catálogo) y derecho (pedido activo)."""
        cuerpo = ctk.CTkFrame(self._ventana, fg_color="transparent")
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=2)
        cuerpo.grid_rowconfigure(0, weight=1)

        self._construir_panel_catalogo(cuerpo)
        self._construir_panel_pedido(cuerpo)

    def _construir_panel_catalogo(self, parent) -> None:
        """Catálogo de productos agrupado por categoría con búsqueda."""
        panel = ctk.CTkFrame(
            parent,
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
            text="Catálogo de productos",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

        marco_busqueda = ctk.CTkFrame(panel, fg_color="transparent")
        marco_busqueda.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="ew")
        marco_busqueda.grid_columnconfigure(0, weight=1)

        self._entrada_busqueda = ctk.CTkEntry(
            marco_busqueda,
            placeholder_text="Buscar por nombre de producto...",
            height=40,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            border_color=PALETA["entrada_borde"],
        )
        self._entrada_busqueda.grid(row=0, column=0, sticky="ew")
        self._entrada_busqueda.bind("<KeyRelease>", self._al_escribir_busqueda)

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "POS.Catalogo")

        self._tree_catalogo = ttk.Treeview(
            marco_tree,
            columns=("precio",),
            show="tree headings",
            style="POS.Catalogo.Treeview",
            selectmode="browse",
        )
        self._tree_catalogo.heading("#0", text="Producto", anchor="w")
        self._tree_catalogo.heading("precio", text="Precio")
        self._tree_catalogo.column("#0", width=280, stretch=True, anchor="w")
        self._tree_catalogo.column("precio", width=100, stretch=False, anchor="e")

        scroll_cat = ttk.Scrollbar(
            marco_tree, orient="vertical", command=self._tree_catalogo.yview
        )
        self._tree_catalogo.configure(yscrollcommand=scroll_cat.set)
        self._tree_catalogo.grid(row=0, column=0, sticky="nsew")
        scroll_cat.grid(row=0, column=1, sticky="ns")

        self._tree_catalogo.bind("<Double-Button-1>", lambda _e: self._accion_agregar())
        self._tree_catalogo.bind("<Return>", lambda _e: self._accion_agregar())

        ctk.CTkButton(
            panel,
            text="+  Agregar ítem",
            height=44,
            font=fuente_boton(),
            command=self._accion_agregar,
            **kwargs_boton_primario(),
        ).grid(
            row=3,
            column=0,
            padx=PADDING_PANEL_H,
            pady=(0, PADDING_PANEL_INFERIOR),
            sticky="ew",
        )

    def _construir_panel_pedido(self, parent) -> None:
        """Lista del pedido activo con subtotales y acciones."""
        panel = ctk.CTkFrame(
            parent,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            panel,
            text="Pedido activo",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 8), sticky="w")

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "POS.Pedido")

        self._tree_pedido = ttk.Treeview(
            marco_tree,
            columns=("producto", "cantidad", "precio", "subtotal"),
            show="headings",
            style="POS.Pedido.Treeview",
            selectmode="browse",
        )
        self._tree_pedido.heading("producto", text="Producto")
        self._tree_pedido.heading("cantidad", text="Cant.")
        self._tree_pedido.heading("precio", text="P. unit.")
        self._tree_pedido.heading("subtotal", text="Subtotal")
        self._tree_pedido.column("producto", width=160, stretch=True, anchor="w")
        self._tree_pedido.column("cantidad", width=50, stretch=False, anchor="center")
        self._tree_pedido.column("precio", width=90, stretch=False, anchor="e")
        self._tree_pedido.column("subtotal", width=100, stretch=False, anchor="e")

        scroll_ped = ttk.Scrollbar(
            marco_tree, orient="vertical", command=self._tree_pedido.yview
        )
        self._tree_pedido.configure(yscrollcommand=scroll_ped.set)
        self._tree_pedido.grid(row=0, column=0, sticky="nsew")
        scroll_ped.grid(row=0, column=1, sticky="ns")

        marco_total = ctk.CTkFrame(panel, fg_color="transparent")
        marco_total.grid(row=3, column=0, padx=20, pady=(4, 8), sticky="ew")
        marco_total.grid_columnconfigure(0, weight=1)

        ctk.CTkFrame(
            marco_total, height=1, fg_color=PALETA["borde"], corner_radius=0
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            marco_total,
            text="Total",
            font=ctk.CTkFont(size=14),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, sticky="w")

        self._label_total = ctk.CTkLabel(
            marco_total,
            text="$0",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=PALETA["texto"],
        )
        self._label_total.grid(row=1, column=1, sticky="e")

        marco_botones = ctk.CTkFrame(panel, fg_color="transparent")
        marco_botones.grid(
            row=4, column=0, padx=PADDING_PANEL_H, pady=(0, PADDING_PANEL_INFERIOR), sticky="ew"
        )
        marco_botones.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            marco_botones,
            text="Cambiar cantidad",
            height=40,
            font=fuente_normal(),
            command=self._accion_cambiar_cantidad,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkButton(
            marco_botones,
            text="Eliminar ítem",
            height=40,
            font=fuente_normal(),
            fg_color=PALETA["boton_accion"],
            hover_color="#fce8e6",
            text_color=PALETA["error"],
            text_color_disabled=PALETA["texto_boton_desactivado"],
            border_width=1,
            border_color=PALETA["borde"],
            corner_radius=10,
            command=self._accion_eliminar,
        ).grid(row=1, column=0, sticky="ew")

    def _construir_pie(self) -> None:
        """Botón para cerrar y volver al mapa de mesas."""
        ctk.CTkButton(
            self._ventana,
            text="Cerrar y volver al mapa",
            height=44,
            font=fuente_boton(),
            command=self._cerrar,
            **kwargs_boton_secundario(),
        ).grid(row=2, column=0, padx=PADDING_PANEL_H, pady=(8, PADDING_PANEL_INFERIOR), sticky="ew")

    def _al_escribir_busqueda(self, _evento=None) -> None:
        """Filtra el catálogo con un pequeño retardo para no saturar la UI."""
        if self._timer_busqueda is not None:
            self._ventana.after_cancel(self._timer_busqueda)
        self._timer_busqueda = self._ventana.after(200, self._cargar_catalogo)

    def _cargar_catalogo(self) -> None:
        """Recarga el Treeview del catálogo según el texto de búsqueda."""
        self._timer_busqueda = None
        termino = self._entrada_busqueda.get().strip()
        agrupado = pedido_service.obtener_catalogo_agrupado(termino)

        for fila in self._tree_catalogo.get_children():
            self._tree_catalogo.delete(fila)
        self._mapa_productos.clear()

        if not agrupado:
            self._tree_catalogo.insert(
                "",
                "end",
                iid="__vacio__",
                text="Sin productos que coincidan",
                values=("",),
                tags=("vacio",),
            )
            return

        for categoria, productos in sorted(agrupado.items()):
            iid_cat = f"cat_{categoria}"
            self._tree_catalogo.insert(
                "",
                "end",
                iid=iid_cat,
                text=categoria,
                values=("",),
                tags=("categoria",),
                open=True,
            )
            for producto in productos:
                iid_prod = f"prod_{producto.id}"
                self._mapa_productos[iid_prod] = producto
                self._tree_catalogo.insert(
                    iid_cat,
                    "end",
                    iid=iid_prod,
                    text=producto.nombre,
                    values=(_formatear_pesos(producto.precio),),
                    tags=("producto",),
                )

    def _refrescar_pedido(self) -> None:
        """Recarga los ítems del pedido y el total acumulado."""
        for fila in self._tree_pedido.get_children():
            self._tree_pedido.delete(fila)

        try:
            items = pedido_service.obtener_items_pedido(self._pedido_id)
        except ValueError as error:
            messagebox.showerror("Pedido", str(error))
            return

        total = 0
        for item in items:
            total += item.subtotal
            self._tree_pedido.insert(
                "",
                "end",
                iid=str(item.id),
                values=(
                    item.nombre_producto,
                    item.cantidad,
                    _formatear_pesos(item.precio_unitario),
                    _formatear_pesos(item.subtotal),
                ),
            )

        self._label_total.configure(text=_formatear_pesos(total))

    def _producto_seleccionado(self) -> Optional[ProductoCatalogo]:
        """Retorna el producto seleccionado en el catálogo, o None."""
        seleccion = self._tree_catalogo.selection()
        if not seleccion:
            return None
        iid = seleccion[0]
        if iid.startswith("prod_"):
            return self._mapa_productos.get(iid)
        return None

    def _item_seleccionado(self) -> Optional[int]:
        """Retorna el id del ítem seleccionado en el pedido, o None."""
        seleccion = self._tree_pedido.selection()
        if not seleccion:
            return None
        return int(seleccion[0])

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso en un diálogo."""
        if isinstance(error, ErrorAcceso):
            messagebox.showerror("Acceso denegado", str(error))
        else:
            messagebox.showerror("Error", str(error))

    def _accion_agregar(self) -> None:
        """Agrega el producto seleccionado al pedido activo."""
        producto = self._producto_seleccionado()
        if producto is None:
            messagebox.showinfo(
                "Agregar ítem",
                "Seleccione un producto del catálogo.",
            )
            return

        dialogo = _DialogoCantidad(
            self._ventana,
            f"Cantidad — {producto.nombre}",
            valor_inicial=1,
        )
        cantidad = dialogo.resultado()
        if cantidad is None:
            return

        try:
            pedido_service.agregar_item(
                self._pedido_id,
                producto.id,
                cantidad,
            )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._refrescar_pedido()

    def _accion_eliminar(self) -> None:
        """Elimina el ítem seleccionado del pedido."""
        item_id = self._item_seleccionado()
        if item_id is None:
            messagebox.showinfo(
                "Eliminar ítem",
                "Seleccione un ítem del pedido.",
            )
            return

        if not messagebox.askyesno(
            "Eliminar ítem",
            "¿Confirma que desea eliminar el ítem seleccionado?",
        ):
            return

        try:
            pedido_service.eliminar_item(self._pedido_id, item_id)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._refrescar_pedido()

    def _accion_cambiar_cantidad(self) -> None:
        """Permite modificar la cantidad del ítem seleccionado."""
        item_id = self._item_seleccionado()
        if item_id is None:
            messagebox.showinfo(
                "Cambiar cantidad",
                "Seleccione un ítem del pedido.",
            )
            return

        valores = self._tree_pedido.item(str(item_id), "values")
        cantidad_actual = int(valores[1]) if valores else 1
        nombre = valores[0] if valores else ""

        dialogo = _DialogoCantidad(
            self._ventana,
            f"Nueva cantidad — {nombre}",
            valor_inicial=cantidad_actual,
        )
        nueva_cantidad = dialogo.resultado()
        if nueva_cantidad is None:
            return

        try:
            pedido_service.cambiar_cantidad_item(
                self._pedido_id,
                item_id,
                nueva_cantidad,
            )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._refrescar_pedido()

    def _cerrar(self) -> None:
        """Cierra la ventana y notifica al llamador."""
        self._ventana.destroy()
        if self._al_cerrar is not None:
            self._al_cerrar()


@requiere_rol("cajero", "supervisor", "administrador")
def abrir_pos(
    parent,
    mesa_id: int,
    pedido_id: int,
    al_cerrar: Optional[Callable[[], None]] = None,
) -> None:
    """
    Abre el POS en una ventana secundaria vinculada a mesa y pedido activos.

    Solo accesible cuando la mesa está ocupada con un pedido abierto.
    """
    try:
        VentanaPOS(parent, mesa_id, pedido_id, al_cerrar=al_cerrar)
    except ErrorAcceso as error:
        messagebox.showerror("Acceso denegado", str(error))
