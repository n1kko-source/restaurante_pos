"""Ventana modal para dividir la cuenta de un pedido entre varias personas."""

from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Union

import customtkinter as ctk

from models.mesa import ESTADO_LIBRE
from models.pedido import PedidoItem
from services import facturacion_service, mesa_service
from services.auth_service import ErrorAcceso
from services.facturacion_service import ASIGNACION_TODOS
from ui.tema import (
    PALETA,
    centrar_ventana,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
)

_MIN_PERSONAS = 2
_MAX_PERSONAS = 8


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"${monto:,.0f}".replace(",", ".")


def _opciones_asignacion(num_personas: int) -> List[str]:
    """Retorna las etiquetas del selector de asignación por ítem."""
    return ["Todos"] + [f"Persona {n}" for n in range(1, num_personas + 1)]


def _valor_desde_etiqueta(etiqueta: str) -> Union[int, str]:
    """Convierte la etiqueta UI en valor para facturacion_service."""
    if etiqueta == "Todos":
        return ASIGNACION_TODOS
    if etiqueta.startswith("Persona "):
        return int(etiqueta.split()[-1])
    raise ValueError(f"Asignación no reconocida: '{etiqueta}'.")


def _etiqueta_desde_valor(valor: Union[int, str]) -> str:
    """Convierte el valor del servicio en etiqueta para la UI."""
    if valor == ASIGNACION_TODOS:
        return "Todos"
    return f"Persona {valor}"


class VentanaDividirCuenta(ctk.CTkToplevel):
    """Diálogo para asignar ítems y dividir el pedido en varias facturas."""

    def __init__(
        self,
        parent,
        mesa_id: int,
        mesa_numero: int,
        pedido_id: int,
        items: List[PedidoItem],
        al_finalizar: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self._mesa_id = mesa_id
        self._mesa_numero = mesa_numero
        self._pedido_id = pedido_id
        self._items = items
        self._al_finalizar = al_finalizar

        self._num_personas = _MIN_PERSONAS
        self._asignaciones: Dict[int, Union[int, str]] = {
            item.id: ASIGNACION_TODOS for item in items
        }
        self._selectores: Dict[int, ctk.CTkOptionMenu] = {}
        self._labels_resumen: Dict[int, ctk.CTkLabel] = {}

        self.title(f"Dividir cuenta — Mesa {mesa_numero}")
        self.configure(fg_color=PALETA["fondo"])
        self.transient(parent)
        self.grab_set()
        self.minsize(680, 520)
        centrar_ventana(self, 760, 580)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_encabezado()
        self._construir_cuerpo()
        self._construir_pie()

        self._actualizar_selectores_items()
        self._actualizar_resumen()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _construir_encabezado(self) -> None:
        """Título y datos de mesa / pedido."""
        marco = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        marco.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            marco,
            text="Dividir cuenta",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(14, 0), sticky="w")

        ctk.CTkLabel(
            marco,
            text=(
                f"Mesa {self._mesa_numero}  ·  Pedido #{self._pedido_id}  ·  "
                f"{len(self._items)} ítem(s)"
            ),
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, padx=20, pady=(4, 14), sticky="w")

    def _construir_cuerpo(self) -> None:
        """Panel de configuración, ítems y vista previa de totales."""
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.grid(row=1, column=0, sticky="nsew", padx=16, pady=8)
        cuerpo.grid_columnconfigure(0, weight=3)
        cuerpo.grid_columnconfigure(1, weight=2)
        cuerpo.grid_rowconfigure(0, weight=1)

        panel_izq = ctk.CTkFrame(
            cuerpo,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel_izq.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        panel_izq.grid_columnconfigure(0, weight=1)
        panel_izq.grid_rowconfigure(2, weight=1)

        config = ctk.CTkFrame(panel_izq, fg_color="transparent")
        config.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        config.grid_columnconfigure((0, 1), weight=1)

        marco_personas = ctk.CTkFrame(config, fg_color="transparent")
        marco_personas.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(
            marco_personas,
            text="Número de personas",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).pack(anchor="w")
        self._menu_personas = ctk.CTkOptionMenu(
            marco_personas,
            values=[str(n) for n in range(_MIN_PERSONAS, _MAX_PERSONAS + 1)],
            command=self._al_cambiar_personas,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            button_color=PALETA["boton_primario"],
            button_hover_color=PALETA["boton_primario_hover"],
            text_color=PALETA["texto"],
            dropdown_fg_color=PALETA["tarjeta"],
        )
        self._menu_personas.set(str(_MIN_PERSONAS))
        self._menu_personas.pack(fill="x", pady=(4, 0))

        marco_pago = ctk.CTkFrame(config, fg_color="transparent")
        marco_pago.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(
            marco_pago,
            text="Método de pago",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).pack(anchor="w")
        self._menu_pago = ctk.CTkOptionMenu(
            marco_pago,
            values=["Efectivo", "Billetera digital"],
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            button_color=PALETA["boton_primario"],
            button_hover_color=PALETA["boton_primario_hover"],
            text_color=PALETA["texto"],
            dropdown_fg_color=PALETA["tarjeta"],
        )
        self._menu_pago.set("Efectivo")
        self._menu_pago.pack(fill="x", pady=(4, 0))

        ctk.CTkLabel(
            panel_izq,
            text="Asigne cada ítem a una persona o a Todos para repartir en partes iguales",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
            wraplength=420,
            justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        self._scroll_items = ctk.CTkScrollableFrame(
            panel_izq,
            fg_color=PALETA["fondo"],
            corner_radius=10,
        )
        self._scroll_items.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self._scroll_items.grid_columnconfigure(0, weight=1)

        panel_der = ctk.CTkFrame(
            cuerpo,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel_der.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        panel_der.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel_der,
            text="Vista previa por persona",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 12), sticky="w")

        self._marco_resumen = ctk.CTkFrame(panel_der, fg_color="transparent")
        self._marco_resumen.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 8))
        self._marco_resumen.grid_columnconfigure(0, weight=1)

        self._label_total_general = ctk.CTkLabel(
            panel_der,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PALETA["texto"],
        )
        self._label_total_general.grid(row=2, column=0, padx=20, pady=(8, 20), sticky="ew")

    def _construir_pie(self) -> None:
        """Botones cancelar y confirmar."""
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        pie.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            pie,
            text="Cancelar",
            height=44,
            corner_radius=10,
            font=fuente_normal(),
            fg_color=PALETA["boton_accion"],
            hover_color=PALETA["boton_accion_hover"],
            text_color=PALETA["texto"],
            border_width=1,
            border_color=PALETA["boton_accion_borde"],
            command=self._cerrar,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            pie,
            text="Confirmar división e imprimir",
            height=44,
            corner_radius=10,
            font=fuente_boton(),
            fg_color=PALETA["boton_primario"],
            hover_color=PALETA["boton_primario_hover"],
            text_color="#ffffff",
            command=self._confirmar,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _al_cambiar_personas(self, valor: str) -> None:
        """Actualiza el número de personas y reajusta asignaciones inválidas."""
        self._num_personas = int(valor)
        for item_id, asignacion in list(self._asignaciones.items()):
            if asignacion != ASIGNACION_TODOS and asignacion > self._num_personas:
                self._asignaciones[item_id] = ASIGNACION_TODOS
        self._actualizar_selectores_items()
        self._actualizar_resumen()

    def _al_cambiar_asignacion(self, item_id: int, etiqueta: str) -> None:
        """Guarda la asignación de un ítem y refresca totales."""
        self._asignaciones[item_id] = _valor_desde_etiqueta(etiqueta)
        self._actualizar_resumen()

    def _actualizar_selectores_items(self) -> None:
        """Reconstruye las filas de ítems con sus selectores de persona."""
        for widget in self._scroll_items.winfo_children():
            widget.destroy()
        self._selectores.clear()

        opciones = _opciones_asignacion(self._num_personas)
        for indice, item in enumerate(self._items):
            fila = ctk.CTkFrame(
                self._scroll_items,
                fg_color=PALETA["tarjeta"],
                corner_radius=8,
                border_width=1,
                border_color=PALETA["borde"],
            )
            fila.grid(row=indice, column=0, sticky="ew", pady=4)
            fila.grid_columnconfigure(0, weight=1)

            texto_item = f"{item.cantidad}x {item.nombre_producto}"
            ctk.CTkLabel(
                fila,
                text=texto_item,
                font=fuente_normal(),
                text_color=PALETA["texto"],
                anchor="w",
            ).grid(row=0, column=0, padx=12, pady=(10, 0), sticky="w")

            ctk.CTkLabel(
                fila,
                text=_formatear_pesos(item.subtotal),
                font=fuente_pequena(),
                text_color=PALETA["texto_suave"],
            ).grid(row=1, column=0, padx=12, pady=(0, 4), sticky="w")

            etiqueta_actual = _etiqueta_desde_valor(self._asignaciones[item.id])
            menu = ctk.CTkOptionMenu(
                fila,
                values=opciones,
                command=lambda val, iid=item.id: self._al_cambiar_asignacion(iid, val),
                width=160,
                height=34,
                font=fuente_pequena(),
                fg_color=PALETA["entrada_fondo"],
                button_color=PALETA["acento"],
                button_hover_color=PALETA["acento_hover"],
                text_color=PALETA["texto"],
                dropdown_fg_color=PALETA["tarjeta"],
            )
            menu.set(etiqueta_actual)
            menu.grid(row=0, column=1, rowspan=2, padx=12, pady=10)
            self._selectores[item.id] = menu

    def _actualizar_resumen(self) -> None:
        """Muestra el total calculado por persona según las asignaciones actuales."""
        for widget in self._marco_resumen.winfo_children():
            widget.destroy()
        self._labels_resumen.clear()

        try:
            totales = facturacion_service.preview_totales_division(
                self._pedido_id,
                self._num_personas,
                self._asignaciones,
            )
        except ValueError as error:
            self._label_total_general.configure(text=str(error))
            return

        total_general = 0
        for persona in range(1, self._num_personas + 1):
            monto = totales.get(persona, 0)
            total_general += monto

            tarjeta = ctk.CTkFrame(
                self._marco_resumen,
                fg_color=PALETA["fondo"],
                corner_radius=8,
            )
            tarjeta.pack(fill="x", pady=4)
            tarjeta.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                tarjeta,
                text=f"Persona {persona}",
                font=fuente_normal(),
                text_color=PALETA["texto_suave"],
            ).grid(row=0, column=0, padx=12, pady=10, sticky="w")

            lbl_total = ctk.CTkLabel(
                tarjeta,
                text=_formatear_pesos(monto) if monto > 0 else "—",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=PALETA["acento"] if monto > 0 else PALETA["texto_suave"],
            )
            lbl_total.grid(row=0, column=1, padx=12, pady=10, sticky="e")
            self._labels_resumen[persona] = lbl_total

        self._label_total_general.configure(
            text=f"Total pedido: {_formatear_pesos(total_general)}"
        )

    def _metodo_pago_seleccionado(self) -> str:
        """Convierte la etiqueta UI del método de pago al valor del schema."""
        mapa = {
            "Efectivo": "efectivo",
            "Billetera digital": "billetera_digital",
        }
        return mapa.get(self._menu_pago.get(), "efectivo")

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso."""
        if isinstance(error, ErrorAcceso):
            messagebox.showerror("Acceso denegado", str(error), parent=self)
        else:
            messagebox.showerror("Error", str(error), parent=self)

    def _confirmar(self) -> None:
        """Ejecuta la división, imprime facturas y libera la mesa."""
        try:
            facturas, resultados = facturacion_service.dividir_e_imprimir_cuenta(
                self._pedido_id,
                self._num_personas,
                self._asignaciones,
                metodo_pago=self._metodo_pago_seleccionado(),
            )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        lineas = [f"Se generaron {len(facturas)} factura(s):\n"]
        for factura in facturas:
            ok = next(
                (r[1] for r in resultados if r[0] == factura.id),
                False,
            )
            estado = "impresa" if ok else "sin impresión"
            lineas.append(
                f"· {factura.numero} — {_formatear_pesos(factura.total_neto())} ({estado})"
            )

        if any(not r[1] for r in resultados):
            messagebox.showwarning(
                "División completada",
                "\n".join(lineas)
                + "\n\nAlgunas facturas no se imprimieron. "
                "Puede reimprimirlas desde el módulo de reportes.",
                parent=self,
            )
        else:
            messagebox.showinfo(
                "División completada",
                "\n".join(lineas),
                parent=self,
            )

        try:
            mesa_service.cerrar_pedido(self._pedido_id)
            mesa_service.cambiar_estado_mesa(self._mesa_id, ESTADO_LIBRE)
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self.destroy()
        if self._al_finalizar is not None:
            self._al_finalizar()

    def _cerrar(self) -> None:
        """Cierra el diálogo sin aplicar cambios."""
        self.destroy()


def abrir_dividir_cuenta(
    parent,
    mesa_id: int,
    mesa_numero: int,
    pedido_id: int,
    items: List[PedidoItem],
    al_finalizar: Optional[Callable[[], None]] = None,
) -> None:
    """
    Abre el diálogo modal de división de cuenta para un pedido activo.

    Tras confirmar, genera facturas parciales, intenta imprimirlas y libera la mesa.
    """
    VentanaDividirCuenta(
        parent,
        mesa_id=mesa_id,
        mesa_numero=mesa_numero,
        pedido_id=pedido_id,
        items=items,
        al_finalizar=al_finalizar,
    )
