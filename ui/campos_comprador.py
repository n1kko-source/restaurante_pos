"""Campos opcionales del comprador para facturación en el flujo de mesas."""

from typing import Dict, Tuple

import customtkinter as ctk

from ui.tema import PALETA, fuente_normal, fuente_pequena


def agregar_campos_comprador(
    contenedor,
    fila_inicio: int = 0,
    columnspan: int = 1,
) -> Tuple[Dict[str, ctk.CTkEntry], int]:
    """
    Añade al grid del contenedor las entradas de comprador (opcionales).

    Retorna (mapa clave -> CTkEntry, siguiente fila libre).
    """
    entradas = {}

    ctk.CTkLabel(
        contenedor,
        text="Comprador (nombre o razón social)",
        font=fuente_pequena(),
        text_color=PALETA["texto_suave"],
    ).grid(
        row=fila_inicio,
        column=0,
        columnspan=columnspan,
        padx=20,
        sticky="w",
    )
    entrada_nombre = ctk.CTkEntry(
        contenedor,
        height=38,
        font=fuente_normal(),
        fg_color=PALETA["entrada_fondo"],
        border_color=PALETA["borde"],
        text_color=PALETA["texto"],
        placeholder_text="Opcional — dejar en blanco para no imprimir",
    )
    entrada_nombre.grid(
        row=fila_inicio + 1,
        column=0,
        columnspan=columnspan,
        padx=20,
        pady=(4, 8),
        sticky="ew",
    )
    entradas["comprador_nombre"] = entrada_nombre

    ctk.CTkLabel(
        contenedor,
        text="Comprador (NIT, cédula o código DIAN)",
        font=fuente_pequena(),
        text_color=PALETA["texto_suave"],
    ).grid(
        row=fila_inicio + 2,
        column=0,
        columnspan=columnspan,
        padx=20,
        sticky="w",
    )
    entrada_id = ctk.CTkEntry(
        contenedor,
        height=38,
        font=fuente_normal(),
        fg_color=PALETA["entrada_fondo"],
        border_color=PALETA["borde"],
        text_color=PALETA["texto"],
        placeholder_text="Opcional — dejar en blanco para no imprimir",
    )
    entrada_id.grid(
        row=fila_inicio + 3,
        column=0,
        columnspan=columnspan,
        padx=20,
        pady=(4, 0),
        sticky="ew",
    )
    entradas["comprador_identificacion"] = entrada_id

    return entradas, fila_inicio + 4


def leer_campos_comprador(entradas: Dict[str, ctk.CTkEntry]) -> Tuple[str, str]:
    """Lee y normaliza los textos del comprador desde las entradas."""
    nombre = entradas.get("comprador_nombre")
    identificacion = entradas.get("comprador_identificacion")
    return (
        nombre.get().strip() if nombre is not None else "",
        identificacion.get().strip() if identificacion is not None else "",
    )
