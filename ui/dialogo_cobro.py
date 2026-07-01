"""Diálogo modal para confirmar método de pago y descuento antes de facturar."""

from tkinter import messagebox
from typing import Optional, Tuple

import customtkinter as ctk

from config import ETIQUETA_A_METODO_PAGO, METODOS_PAGO
from ui.campos_comprador import agregar_campos_comprador, leer_campos_comprador
from ui.tema import (
    DesplegableProfesional,
    PALETA,
    centrar_ventana,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
    kwargs_boton_primario,
    kwargs_boton_secundario,
)

_ETIQUETAS_PAGO = tuple(etiqueta for _, etiqueta in METODOS_PAGO)


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"${monto:,.0f}".replace(",", ".")


def _parsear_monto_cop(texto: str) -> int:
    """Convierte texto con o sin separadores a entero COP."""
    limpio = texto.strip().replace("$", "").replace(".", "").replace(",", "")
    if not limpio:
        return 0
    return int(limpio)


class DialogoCobro(ctk.CTkToplevel):
    """Ventana modal para elegir pago, descuento y datos opcionales del comprador."""

    def __init__(
        self,
        parent,
        total_pedido: int,
        mesa_numero: int,
        imprimir: bool = True,
    ):
        super().__init__(parent)
        self._total_pedido = total_pedido
        self._resultado: Optional[Tuple[str, int, str, str]] = None
        texto_confirmar = "Facturar e imprimir" if imprimir else "Cerrar sin imprimir"

        self.title(f"Cobro — Mesa {mesa_numero}")
        self.configure(fg_color=PALETA["fondo"])
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.grid_columnconfigure(0, weight=1)

        marco = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        marco.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            marco,
            text="Confirmar cobro",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        ctk.CTkLabel(
            marco,
            text=f"Total del pedido: {_formatear_pesos(total_pedido)}",
            font=fuente_subtitulo(),
            text_color=PALETA["acento"],
        ).grid(row=1, column=0, padx=20, pady=(0, 16), sticky="w")

        ctk.CTkLabel(
            marco,
            text="Método de pago",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=2, column=0, padx=20, sticky="w")
        self._menu_pago = DesplegableProfesional(
            marco,
            values=list(_ETIQUETAS_PAGO),
            height=38,
            font=fuente_normal(),
        )
        self._menu_pago.set("Efectivo")
        self._menu_pago.grid(row=3, column=0, padx=20, pady=(4, 12), sticky="ew")

        ctk.CTkLabel(
            marco,
            text="Descuento (COP, opcional)",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=4, column=0, padx=20, sticky="w")
        self._entrada_descuento = ctk.CTkEntry(
            marco,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            border_color=PALETA["borde"],
            text_color=PALETA["texto"],
            placeholder_text="0",
        )
        self._entrada_descuento.insert(0, "0")
        self._entrada_descuento.grid(row=5, column=0, padx=20, pady=(4, 12), sticky="ew")

        self._entradas_comprador, fila_siguiente = agregar_campos_comprador(marco, fila_inicio=6)

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=fila_siguiente, column=0, sticky="ew", padx=20, pady=(16, 18))
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Cancelar",
            height=42,
            font=fuente_normal(),
            command=self._cancelar,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            botones,
            text=texto_confirmar,
            height=42,
            font=fuente_boton(),
            command=self._confirmar,
            **kwargs_boton_primario(),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        centrar_ventana(self, 440, 520, parent=parent)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Return>", lambda _e: self._confirmar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._entrada_descuento.focus_set()

    @property
    def resultado(self) -> Optional[Tuple[str, int, str, str]]:
        """Retorna (metodo_pago, descuento, comprador_nombre, comprador_id) o None."""
        return self._resultado

    def _cancelar(self) -> None:
        """Cierra el diálogo sin confirmar el cobro."""
        self._resultado = None
        self.destroy()

    def _confirmar(self) -> None:
        """Valida los datos y confirma el cobro."""
        try:
            descuento = _parsear_monto_cop(self._entrada_descuento.get())
        except ValueError:
            messagebox.showerror(
                "Descuento inválido",
                "Ingrese un valor numérico entero en pesos.",
                parent=self,
            )
            return

        if descuento < 0:
            messagebox.showerror(
                "Descuento inválido",
                "El descuento no puede ser negativo.",
                parent=self,
            )
            return
        if descuento > self._total_pedido:
            messagebox.showerror(
                "Descuento inválido",
                f"El descuento no puede superar el total ({_formatear_pesos(self._total_pedido)}).",
                parent=self,
            )
            return

        etiqueta = self._menu_pago.get()
        metodo_pago = ETIQUETA_A_METODO_PAGO.get(etiqueta, "efectivo")
        comprador_nombre, comprador_identificacion = leer_campos_comprador(
            self._entradas_comprador
        )
        self._resultado = (
            metodo_pago,
            descuento,
            comprador_nombre,
            comprador_identificacion,
        )
        self.destroy()


def solicitar_cobro(
    parent,
    total_pedido: int,
    mesa_numero: int,
    imprimir: bool = True,
) -> Optional[Tuple[str, int, str, str]]:
    """
    Abre el diálogo de cobro y retorna datos del cierre o None si cancela.

    Retorna (metodo_pago, descuento, comprador_nombre, comprador_identificacion).
    metodo_pago usa los códigos del schema: efectivo, daviplata, nequi, anotar.
    """
    dialogo = DialogoCobro(parent, total_pedido, mesa_numero, imprimir=imprimir)
    parent.wait_window(dialogo)
    return dialogo.resultado
