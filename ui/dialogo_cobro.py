"""Diálogo modal para confirmar método de pago y descuento antes de facturar."""

from tkinter import messagebox
from typing import Optional, Tuple

import customtkinter as ctk

from ui.tema import (
    PALETA,
    centrar_ventana,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
)

_ETIQUETAS_PAGO = ("Efectivo", "Billetera digital")
_MAPA_METODO_PAGO = {
    "Efectivo": "efectivo",
    "Billetera digital": "billetera_digital",
}


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
    """Ventana modal para elegir pago y descuento antes de imprimir la factura."""

    def __init__(self, parent, total_pedido: int, mesa_numero: int):
        super().__init__(parent)
        self._total_pedido = total_pedido
        self._resultado: Optional[Tuple[str, int]] = None

        self.title(f"Cobro — Mesa {mesa_numero}")
        self.configure(fg_color=PALETA["fondo"])
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        centrar_ventana(self, 420, 340)

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
        self._menu_pago = ctk.CTkOptionMenu(
            marco,
            values=list(_ETIQUETAS_PAGO),
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            button_color=PALETA["boton_primario"],
            button_hover_color=PALETA["boton_primario_hover"],
            text_color=PALETA["texto"],
            dropdown_fg_color=PALETA["tarjeta"],
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
        self._entrada_descuento.grid(row=5, column=0, padx=20, pady=(4, 16), sticky="ew")

        botones = ctk.CTkFrame(marco, fg_color="transparent")
        botones.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 18))
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Cancelar",
            height=42,
            font=fuente_normal(),
            fg_color=PALETA["boton_accion"],
            hover_color=PALETA["boton_accion_hover"],
            text_color=PALETA["texto"],
            border_width=1,
            border_color=PALETA["boton_accion_borde"],
            command=self._cancelar,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            botones,
            text="Facturar e imprimir",
            height=42,
            font=fuente_boton(),
            fg_color=PALETA["boton_primario"],
            hover_color=PALETA["boton_primario_hover"],
            text_color="#ffffff",
            command=self._confirmar,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Return>", lambda _e: self._confirmar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self._entrada_descuento.focus_set()

    @property
    def resultado(self) -> Optional[Tuple[str, int]]:
        """Retorna (metodo_pago, descuento) o None si el usuario canceló."""
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
        metodo_pago = _MAPA_METODO_PAGO.get(etiqueta, "efectivo")
        self._resultado = (metodo_pago, descuento)
        self.destroy()


def solicitar_cobro(
    parent,
    total_pedido: int,
    mesa_numero: int,
) -> Optional[Tuple[str, int]]:
    """
    Abre el diálogo de cobro y retorna (metodo_pago, descuento) o None si cancela.

    metodo_pago usa los valores del schema: 'efectivo' | 'billetera_digital'.
    """
    dialogo = DialogoCobro(parent, total_pedido, mesa_numero)
    parent.wait_window(dialogo)
    return dialogo.resultado
