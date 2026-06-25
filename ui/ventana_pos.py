"""Punto de venta vinculado a la mesa activa."""

from typing import Callable, Optional

import customtkinter as ctk

from ui.tema import (
    PALETA,
    centrar_ventana,
    fuente_boton,
    fuente_normal,
    fuente_subtitulo,
    fuente_titulo,
)


def abrir_pos(
    parent,
    mesa_id: int,
    pedido_id: int,
    al_cerrar: Optional[Callable[[], None]] = None,
) -> None:
    """
    Abre el POS en una ventana secundaria vinculada a mesa y pedido.
    Stub provisional hasta el sprint de ventana_pos completa.
    """
    ventana = ctk.CTkToplevel(parent)
    ventana.title(f"Punto de venta — Mesa {mesa_id}")
    ventana.configure(fg_color=PALETA["fondo"])
    ventana.transient(parent)
    ventana.grab_set()
    centrar_ventana(ventana, 500, 360)

    tarjeta = ctk.CTkFrame(
        ventana,
        fg_color=PALETA["tarjeta"],
        corner_radius=16,
        border_width=1,
        border_color=PALETA["borde"],
    )
    tarjeta.pack(expand=True, fill="both", padx=24, pady=24)

    marco = ctk.CTkFrame(tarjeta, fg_color="transparent")
    marco.pack(expand=True, fill="both", padx=32, pady=32)

    ctk.CTkLabel(
        marco,
        text="Punto de venta",
        font=fuente_titulo(),
        text_color=PALETA["texto"],
    ).pack(pady=(0, 8))

    ctk.CTkLabel(
        marco,
        text=f"Mesa ID: {mesa_id}  |  Pedido #{pedido_id}",
        font=fuente_subtitulo(),
        text_color=PALETA["texto_suave"],
    ).pack(pady=(0, 16))

    ctk.CTkLabel(
        marco,
        text=(
            "Módulo POS en desarrollo.\n"
            "Aquí se agregarán productos al pedido activo."
        ),
        font=fuente_normal(),
        text_color=PALETA["texto_suave"],
        justify="center",
    ).pack(pady=(0, 24))

    def _cerrar():
        ventana.destroy()
        if al_cerrar is not None:
            al_cerrar()

    ctk.CTkButton(
        marco,
        text="Cerrar y volver al mapa",
        height=44,
        corner_radius=10,
        font=fuente_boton(),
        fg_color=PALETA["boton_primario"],
        hover_color=PALETA["boton_primario_hover"],
        text_color="#ffffff",
        command=_cerrar,
    ).pack(fill="x")

    ventana.protocol("WM_DELETE_WINDOW", _cerrar)
