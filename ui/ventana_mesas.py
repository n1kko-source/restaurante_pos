"""Mapa visual del salón y punto de entrada al POS."""

from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from models.mesa import (
    ESTADO_ESPERANDO_PAGO,
    ESTADO_LIBRE,
    ESTADO_OCUPADA,
    Mesa,
)
from models.pedido import Pedido
from services import mesa_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import PALETA

# Distribución L invertida: 4 filas × 3 columnas (celda [3,0] vacía).
_POSICIONES_MESA = {
    1: (0, 0), 2: (0, 1), 3: (0, 2),
    4: (1, 0), 5: (1, 1), 6: (1, 2),
    7: (2, 0), 8: (2, 1), 9: (2, 2),
    10: (3, 1), 11: (3, 2),
}

_ESTILOS_MESA = {
    ESTADO_LIBRE: {
        "fondo": PALETA["libre_fondo"],
        "borde": PALETA["libre_borde"],
        "acento": PALETA["libre_acento"],
        "subtitulo": "libre",
    },
    ESTADO_OCUPADA: {
        "fondo": PALETA["ocupada_fondo"],
        "borde": PALETA["ocupada_borde"],
        "acento": PALETA["ocupada_acento"],
        "subtitulo": "",
    },
    ESTADO_ESPERANDO_PAGO: {
        "fondo": PALETA["espera_fondo"],
        "borde": PALETA["espera_borde"],
        "acento": PALETA["espera_acento"],
        "subtitulo": "facturar",
    },
}


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"${monto:,.0f}".replace(",", ".")


def _vincular_click(widget, callback) -> None:
    """Propaga el clic del ratón a todos los hijos del widget."""
    widget.bind("<Button-1>", lambda _e: callback())
    for hijo in widget.winfo_children():
        _vincular_click(hijo, callback)


class TarjetaMesa(ctk.CTkFrame):
    """Tarjeta visual de una mesa en el mapa del salón."""

    def __init__(self, parent, numero: int, on_seleccionar: Callable[[int], None]):
        super().__init__(
            parent,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        self.numero = numero
        self._on_seleccionar = on_seleccionar
        self._seleccionada = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 0))
        encabezado.grid_columnconfigure(0, weight=1)

        self.label_numero = ctk.CTkLabel(
            encabezado,
            text=str(numero),
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=PALETA["texto"],
            anchor="w",
        )
        self.label_numero.grid(row=0, column=0, sticky="w")

        self.indicador = ctk.CTkLabel(
            encabezado,
            text="\u25cf",
            font=ctk.CTkFont(size=10),
            text_color=PALETA["libre_acento"],
            width=14,
        )
        self.indicador.grid(row=0, column=1, sticky="e")

        self.label_detalle = ctk.CTkLabel(
            self,
            text="libre",
            font=ctk.CTkFont(size=12),
            text_color=PALETA["texto_suave"],
            anchor="w",
        )
        self.label_detalle.grid(row=1, column=0, sticky="sw", padx=14, pady=(2, 14))

        _vincular_click(self, lambda: self._on_seleccionar(numero))

    def actualizar(
        self,
        mesa: Mesa,
        num_items: int,
        total: int,
        seleccionada: bool,
    ) -> None:
        """Refresca colores, textos y borde de selección de la tarjeta."""
        estilo = _ESTILOS_MESA.get(mesa.estado, _ESTILOS_MESA[ESTADO_LIBRE])
        self._seleccionada = seleccionada

        self.configure(
            fg_color=estilo["fondo"],
            border_color=PALETA["seleccion"] if seleccionada else estilo["borde"],
            border_width=3 if seleccionada else 1,
        )
        self.indicador.configure(text_color=estilo["acento"])

        if mesa.estado == ESTADO_LIBRE:
            self.label_detalle.configure(text="libre", text_color=PALETA["texto_suave"])
        elif mesa.estado == ESTADO_OCUPADA:
            texto_items = "1 ítem" if num_items == 1 else f"{num_items} ítems"
            self.label_detalle.configure(
                text=f"{texto_items}\n{_formatear_pesos(total)}",
                text_color=estilo["acento"],
            )
        else:
            self.label_detalle.configure(
                text=f"facturar\n{_formatear_pesos(total)}",
                text_color=estilo["acento"],
            )


class VentanaMesas(ctk.CTkFrame):
    """
    Mapa visual del salón con panel lateral de detalle.
    Se incrusta en el área de contenido de VentanaPrincipal.
    """

    def __init__(
        self,
        parent,
        on_abrir_pos: Optional[Callable[[int, int], None]] = None,
    ):
        super().__init__(parent, fg_color=PALETA["fondo"], corner_radius=0)

        self._on_abrir_pos = on_abrir_pos
        self._mesa_seleccionada: Optional[Mesa] = None
        self._tarjetas: Dict[int, TarjetaMesa] = {}
        self._mesas: Dict[int, Mesa] = {}
        self._info_pedidos: Dict[int, Dict] = {}

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._construir_mapa()
        self._construir_panel()
        self.refrescar()

    def _construir_mapa(self) -> None:
        """Construye resumen, cuadrícula L invertida y leyenda."""
        columna_mapa = ctk.CTkFrame(self, fg_color="transparent")
        columna_mapa.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        columna_mapa.grid_columnconfigure(0, weight=1)
        columna_mapa.grid_rowconfigure(1, weight=1)

        self._construir_resumen(columna_mapa)

        marco_mapa = ctk.CTkFrame(
            columna_mapa,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco_mapa.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        marco_mapa.grid_columnconfigure(0, weight=1)
        marco_mapa.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            marco_mapa,
            text="Salón",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 6), sticky="w")

        contenedor = ctk.CTkFrame(marco_mapa, fg_color="transparent")
        contenedor.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        contenedor.grid_columnconfigure((0, 1, 2), weight=1, uniform="col")
        contenedor.grid_rowconfigure((0, 1, 2, 3), weight=1, uniform="fila")

        for numero in range(1, 12):
            fila, columna = _POSICIONES_MESA[numero]
            tarjeta = TarjetaMesa(
                contenedor,
                numero,
                on_seleccionar=self._al_seleccionar_por_numero,
            )
            tarjeta.grid(row=fila, column=columna, padx=6, pady=6, sticky="nsew")
            self._tarjetas[numero] = tarjeta

        leyenda = ctk.CTkFrame(marco_mapa, fg_color="transparent")
        leyenda.grid(row=2, column=0, padx=20, pady=(4, 16), sticky="w")

        for estado, texto, color in (
            (ESTADO_LIBRE, "Libre", PALETA["libre_acento"]),
            (ESTADO_OCUPADA, "Con pedido abierto", PALETA["ocupada_acento"]),
            (ESTADO_ESPERANDO_PAGO, "Esperando factura", PALETA["espera_acento"]),
        ):
            item = ctk.CTkFrame(leyenda, fg_color="transparent")
            item.pack(side="left", padx=(0, 18))
            ctk.CTkLabel(
                item,
                text="\u25cf",
                text_color=color,
                font=ctk.CTkFont(size=11),
            ).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(
                item,
                text=texto,
                font=ctk.CTkFont(size=11),
                text_color=PALETA["texto_suave"],
            ).pack(side="left")

    def _construir_resumen(self, parent) -> None:
        """Barra superior con conteo de mesas por estado."""
        marco = ctk.CTkFrame(parent, fg_color="transparent")
        marco.grid(row=0, column=0, sticky="ew")
        marco.grid_columnconfigure((0, 1, 2), weight=1, uniform="resumen")

        self._labels_resumen = {}
        datos = (
            ("libres", "Libres", PALETA["resumen_libre"]),
            ("pedido", "Con pedido", PALETA["resumen_ocupada"]),
            ("espera", "Esperan factura", PALETA["resumen_espera"]),
        )
        for indice, (clave, titulo, (fondo, color_num)) in enumerate(datos):
            tarjeta = ctk.CTkFrame(
                marco,
                fg_color=fondo,
                corner_radius=12,
                border_width=1,
                border_color=PALETA["borde"],
            )
            tarjeta.grid(row=0, column=indice, sticky="ew", padx=4)

            lbl_num = ctk.CTkLabel(
                tarjeta,
                text="0",
                font=ctk.CTkFont(size=28, weight="bold"),
                text_color=color_num,
            )
            lbl_num.pack(pady=(12, 0))
            ctk.CTkLabel(
                tarjeta,
                text=titulo,
                font=ctk.CTkFont(size=12),
                text_color=PALETA["texto_suave"],
            ).pack(pady=(0, 12))
            self._labels_resumen[clave] = lbl_num

    def _construir_panel(self) -> None:
        """Panel lateral de detalle con ítems y acciones."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            panel,
            text="Detalle de mesa",
            font=ctk.CTkFont(size=13),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=20, pady=(18, 0), sticky="w")

        encabezado = ctk.CTkFrame(panel, fg_color="transparent")
        encabezado.grid(row=1, column=0, padx=20, pady=(10, 14), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        self.label_mesa = ctk.CTkLabel(
            encabezado,
            text="Seleccione una mesa",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=PALETA["texto"],
            anchor="w",
        )
        self.label_mesa.grid(row=0, column=0, sticky="w")

        self.badge_estado = ctk.CTkLabel(
            encabezado,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=14,
            height=28,
            padx=12,
        )
        self.badge_estado.grid(row=1, column=0, sticky="w", pady=(8, 0))

        ctk.CTkFrame(
            panel, height=1, fg_color=PALETA["borde"], corner_radius=0
        ).grid(row=2, column=0, sticky="ew", padx=20)

        marco_tree = ctk.CTkFrame(panel, fg_color="transparent")
        marco_tree.grid(row=4, column=0, padx=16, pady=(12, 0), sticky="nsew")
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        estilo.layout("Mesas.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        estilo.configure(
            "Mesas.Treeview",
            background=PALETA["tree_fondo"],
            foreground=PALETA["texto"],
            fieldbackground=PALETA["tree_fondo"],
            rowheight=30,
            borderwidth=0,
            font=("Segoe UI", 11),
        )
        estilo.map(
            "Mesas.Treeview",
            background=[("selected", PALETA["tree_seleccion"])],
            foreground=[("selected", PALETA["texto"])],
        )

        self.tree_items = ttk.Treeview(
            marco_tree,
            columns=("linea",),
            show="headings",
            style="Mesas.Treeview",
            selectmode="browse",
        )
        self.tree_items.heading("linea", text="")
        self.tree_items.column("linea", width=280, stretch=True, anchor="w")

        scroll = ttk.Scrollbar(marco_tree, orient="vertical", command=self.tree_items.yview)
        self.tree_items.configure(yscrollcommand=scroll.set)
        self.tree_items.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        marco_total = ctk.CTkFrame(panel, fg_color="transparent")
        marco_total.grid(row=5, column=0, padx=20, pady=(8, 0), sticky="ew")
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

        self.label_total = ctk.CTkLabel(
            marco_total,
            text="—",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=PALETA["texto"],
        )
        self.label_total.grid(row=1, column=1, sticky="e")

        self.marco_acciones = ctk.CTkFrame(panel, fg_color="transparent")
        self.marco_acciones.grid(row=6, column=0, padx=20, pady=(16, 20), sticky="ew")
        self.marco_acciones.grid_columnconfigure(0, weight=1)

        self.label_vacio = ctk.CTkLabel(
            panel,
            text="Haga clic en una mesa del mapa\npara ver su pedido y acciones.",
            font=ctk.CTkFont(size=12),
            text_color=PALETA["texto_suave"],
            justify="center",
        )
        self.label_vacio.grid(row=3, column=0, padx=20, pady=20)

    def _cargar_info_pedidos(self, mesas: List[Mesa]) -> None:
        """Precarga ítems y totales de mesas con pedido activo."""
        self._info_pedidos = {}
        for mesa in mesas:
            if mesa.estado == ESTADO_LIBRE:
                continue
            pedido = mesa_service.obtener_pedido_activo(mesa.id)
            if pedido is None:
                continue
            try:
                items = mesa_service.obtener_items_pedido(pedido.id)
            except ValueError:
                items = []
            total = sum(item.subtotal for item in items)
            self._info_pedidos[mesa.id] = {
                "pedido": pedido,
                "items": items,
                "total": total,
                "num_items": len(items),
            }

    def refrescar(self) -> None:
        """Recarga el estado de todas las mesas y actualiza la interfaz."""
        mesas = mesa_service.obtener_todas_mesas()
        self._mesas = {mesa.numero: mesa for mesa in mesas}
        self._cargar_info_pedidos(mesas)

        conteos = {ESTADO_LIBRE: 0, ESTADO_OCUPADA: 0, ESTADO_ESPERANDO_PAGO: 0}
        for mesa in mesas:
            conteos[mesa.estado] = conteos.get(mesa.estado, 0) + 1

        self._labels_resumen["libres"].configure(text=str(conteos[ESTADO_LIBRE]))
        self._labels_resumen["pedido"].configure(text=str(conteos[ESTADO_OCUPADA]))
        self._labels_resumen["espera"].configure(text=str(conteos[ESTADO_ESPERANDO_PAGO]))

        if self._mesa_seleccionada is not None:
            mesa_actual = self._mesas.get(self._mesa_seleccionada.numero)
            self._mesa_seleccionada = mesa_actual

        for numero, tarjeta in self._tarjetas.items():
            mesa = self._mesas.get(numero)
            if mesa is None:
                continue
            info = self._info_pedidos.get(mesa.id, {})
            tarjeta.actualizar(
                mesa=mesa,
                num_items=info.get("num_items", 0),
                total=info.get("total", 0),
                seleccionada=(
                    self._mesa_seleccionada is not None
                    and self._mesa_seleccionada.numero == numero
                ),
            )

        self._actualizar_panel()

    def _al_seleccionar_por_numero(self, numero: int) -> None:
        """Selecciona una mesa por su número visible en el mapa."""
        mesa = self._mesas.get(numero)
        if mesa is None:
            return
        self._mesa_seleccionada = mesa
        self.refrescar()

    def _configurar_badge(self, mesa: Mesa) -> None:
        """Actualiza la etiqueta de estado tipo pill del panel lateral."""
        mapa_badge = {
            ESTADO_LIBRE: (PALETA["badge_libre"], "Libre"),
            ESTADO_OCUPADA: (PALETA["badge_ocupada"], "Con pedido abierto"),
            ESTADO_ESPERANDO_PAGO: (PALETA["badge_espera"], "Esperando factura"),
        }
        (fondo, texto_color), texto = mapa_badge.get(
            mesa.estado, (PALETA["badge_libre"], mesa.etiqueta_estado())
        )
        self.badge_estado.configure(
            text=texto,
            fg_color=fondo,
            text_color=texto_color,
        )

    def _crear_boton_accion(
        self,
        parent,
        fila: int,
        texto: str,
        comando: Callable[[], None],
        primario: bool = False,
    ) -> None:
        """Crea un botón de acción con estilo del mockup."""
        if primario:
            ctk.CTkButton(
                parent,
                text=texto,
                height=44,
                corner_radius=10,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=PALETA["boton_primario"],
                hover_color=PALETA["boton_primario_hover"],
                text_color="#ffffff",
                command=comando,
            ).grid(row=fila, column=0, sticky="ew", pady=5)
        else:
            ctk.CTkButton(
                parent,
                text=texto,
                height=44,
                corner_radius=10,
                font=ctk.CTkFont(size=13),
                fg_color=PALETA["boton_accion"],
                hover_color="#f1f3f4",
                text_color=PALETA["texto"],
                border_width=1,
                border_color=PALETA["boton_accion_borde"],
                command=comando,
            ).grid(row=fila, column=0, sticky="ew", pady=5)

    def _actualizar_panel(self) -> None:
        """Actualiza etiquetas, ítems y botones de acción del panel lateral."""
        for widget in self.marco_acciones.winfo_children():
            widget.destroy()

        for fila in self.tree_items.get_children():
            self.tree_items.delete(fila)

        if self._mesa_seleccionada is None:
            self.label_mesa.configure(text="Seleccione una mesa")
            self.badge_estado.configure(text="", fg_color="transparent")
            self.label_total.configure(text="—")
            self.label_vacio.grid()
            self.tree_items.grid_remove()
            return

        self.label_vacio.grid_remove()
        self.tree_items.grid()

        mesa = self._mesa_seleccionada
        self.label_mesa.configure(text=f"Mesa {mesa.numero}")
        self._configurar_badge(mesa)

        info = self._info_pedidos.get(mesa.id, {})
        items = info.get("items", [])
        total = info.get("total", 0)
        pedido = info.get("pedido")

        for item in items:
            linea = f"{item.cantidad}x {item.nombre_producto}"
            self.tree_items.insert(
                "",
                "end",
                values=(f"{linea}  {_formatear_pesos(item.subtotal)}",),
            )

        if mesa.estado == ESTADO_LIBRE:
            self.label_total.configure(text="—")
        else:
            self.label_total.configure(text=_formatear_pesos(total))

        self._construir_botones_accion(mesa, pedido)

    def _construir_botones_accion(
        self, mesa: Mesa, pedido: Optional[Pedido]
    ) -> None:
        """Crea los botones de acción según el estado actual de la mesa."""
        if mesa.estado == ESTADO_LIBRE:
            self._crear_boton_accion(
                self.marco_acciones,
                0,
                "+  Abrir pedido nuevo",
                self._accion_abrir_pedido,
                primario=True,
            )
        elif mesa.estado == ESTADO_OCUPADA:
            self._crear_boton_accion(
                self.marco_acciones, 0, "Generar factura", self._accion_generar_factura
            )
            self._crear_boton_accion(
                self.marco_acciones, 1, "Dividir cuenta", self._accion_dividir_cuenta
            )
            self._crear_boton_accion(
                self.marco_acciones, 2, "+  Agregar ítem", self._accion_agregar_item
            )
        elif mesa.estado == ESTADO_ESPERANDO_PAGO:
            self._crear_boton_accion(
                self.marco_acciones,
                0,
                "Imprimir factura",
                self._accion_imprimir_factura,
                primario=True,
            )
            self._crear_boton_accion(
                self.marco_acciones, 1, "Dividir cuenta", self._accion_dividir_cuenta
            )

    def _requiere_mesa_seleccionada(self) -> Optional[Mesa]:
        """Retorna la mesa seleccionada o muestra aviso si no hay ninguna."""
        if self._mesa_seleccionada is None:
            messagebox.showwarning("Mesas", "Seleccione una mesa primero.")
            return None
        return self._mesa_seleccionada

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso en un diálogo."""
        if isinstance(error, ErrorAcceso):
            messagebox.showerror("Acceso denegado", str(error))
        else:
            messagebox.showerror("Error", str(error))

    def _invocar_pos(self, mesa_id: int, pedido_id: int) -> None:
        """Abre el POS vinculado al pedido; usa callback o ventana_pos.abrir."""
        if self._on_abrir_pos is not None:
            self._on_abrir_pos(mesa_id, pedido_id)
            return
        from ui.ventana_pos import abrir_pos

        abrir_pos(
            self.winfo_toplevel(),
            mesa_id,
            pedido_id,
            al_cerrar=self.refrescar,
        )

    def _accion_abrir_pedido(self) -> None:
        """Abre un pedido nuevo y navega al POS."""
        mesa = self._requiere_mesa_seleccionada()
        if mesa is None:
            return
        try:
            pedido = mesa_service.abrir_pedido(mesa.id)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return
        self.refrescar()
        self._invocar_pos(mesa.id, pedido.id)

    def _accion_agregar_item(self) -> None:
        """Regresa al POS con el pedido activo de la mesa."""
        mesa = self._requiere_mesa_seleccionada()
        if mesa is None:
            return
        pedido = mesa_service.obtener_pedido_activo(mesa.id)
        if pedido is None:
            messagebox.showwarning(
                "Mesas",
                f"La mesa {mesa.numero} no tiene un pedido activo.",
            )
            return
        self._invocar_pos(mesa.id, pedido.id)

    def _accion_generar_factura(self) -> None:
        """Marca la mesa como esperando factura."""
        mesa = self._requiere_mesa_seleccionada()
        if mesa is None:
            return
        pedido = mesa_service.obtener_pedido_activo(mesa.id)
        if pedido is None:
            messagebox.showwarning(
                "Mesas",
                f"La mesa {mesa.numero} no tiene un pedido activo.",
            )
            return
        try:
            items = mesa_service.obtener_items_pedido(pedido.id)
        except ValueError as error:
            self._manejar_error(error)
            return
        if not items:
            messagebox.showwarning(
                "Generar factura",
                "El pedido no tiene ítems. Agregue productos antes de facturar.",
            )
            return
        try:
            mesa_service.cambiar_estado_mesa(mesa.id, ESTADO_ESPERANDO_PAGO)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return
        self.refrescar()

    def _accion_dividir_cuenta(self) -> None:
        """Placeholder hasta implementar facturacion_service (división de cuenta)."""
        mesa = self._requiere_mesa_seleccionada()
        if mesa is None:
            return
        pedido = mesa_service.obtener_pedido_activo(mesa.id)
        if pedido is None:
            messagebox.showwarning(
                "Dividir cuenta",
                f"La mesa {mesa.numero} no tiene un pedido activo.",
            )
            return
        messagebox.showinfo(
            "Dividir cuenta",
            "El módulo de división de cuenta se implementará con "
            "facturacion_service en el siguiente sprint.",
        )

    def _accion_imprimir_factura(self) -> None:
        """
        Envía la factura a impresora (stub) y libera la mesa.
        Cierra el pedido activo y restablece el estado a libre.
        """
        mesa = self._requiere_mesa_seleccionada()
        if mesa is None:
            return
        pedido = mesa_service.obtener_pedido_activo(mesa.id)
        if pedido is None:
            messagebox.showwarning(
                "Imprimir factura",
                f"La mesa {mesa.numero} no tiene un pedido activo.",
            )
            return

        messagebox.showinfo(
            "Impresión",
            f"Factura del pedido #{pedido.id} enviada a impresora.\n"
            "(Simulado — integración Colpos pendiente.)",
        )

        try:
            mesa_service.cerrar_pedido(pedido.id)
            mesa_service.cambiar_estado_mesa(mesa.id, ESTADO_LIBRE)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return
        self.refrescar()


@requiere_rol("cajero", "supervisor", "administrador")
def mostrar_en(
    contenedor,
    on_abrir_pos: Optional[Callable[[int, int], None]] = None,
) -> VentanaMesas:
    """
    Incrusta el mapa de mesas en el frame contenedor.
    Primera línea de defensa: decorador @requiere_rol.
    """
    ventana = VentanaMesas(contenedor, on_abrir_pos=on_abrir_pos)
    ventana.grid(row=0, column=0, sticky="nsew")
    return ventana
