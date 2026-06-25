"""Paleta de colores y utilidades visuales compartidas del sistema POS.

Tema claro profesional usado en todas las ventanas CustomTkinter.
"""

from functools import lru_cache

import customtkinter as ctk

# Paleta principal — fondos claros, acentos suaves, tipografía legible.
PALETA = {
    # Superficies generales
    "fondo": "#f0f2f5",
    "tarjeta": "#ffffff",
    "borde": "#dadce0",
    "texto": "#202124",
    "texto_suave": "#5f6368",
    "acento": "#1a73e8",
    "acento_hover": "#1557b0",
    "acento_suave": "#e8f0fe",
    "error": "#d93025",
    "exito": "#1e8e3e",
    # Barra lateral
    "sidebar": "#ffffff",
    "sidebar_borde": "#e8eaed",
    "sidebar_hover": "#f1f3f4",
    "sidebar_activo": "#e8f0fe",
    "sidebar_texto": "#202124",
    "cerrar_sesion": "#d93025",
    "cerrar_sesion_hover": "#b31412",
    # Botones
    "boton_accion": "#ffffff",
    "boton_accion_hover": "#f1f3f4",
    "boton_accion_borde": "#dadce0",
    "boton_primario": "#1a73e8",
    "boton_primario_hover": "#1557b0",
    # Campos de entrada
    "entrada_fondo": "#ffffff",
    "entrada_borde": "#dadce0",
    # Treeview
    "tree_fondo": "#ffffff",
    "tree_seleccion": "#e8f0fe",
    "seleccion": "#1a73e8",
    # Estados de mesa
    "libre_fondo": "#ffffff",
    "libre_borde": "#dadce0",
    "libre_acento": "#9aa0a6",
    "ocupada_fondo": "#e6f4ea",
    "ocupada_borde": "#34a853",
    "ocupada_acento": "#1e8e3e",
    "espera_fondo": "#fef7e0",
    "espera_borde": "#fbbc04",
    "espera_acento": "#e37400",
    "badge_libre": ("#f1f3f4", "#5f6368"),
    "badge_ocupada": ("#ceead6", "#1e8e3e"),
    "badge_espera": ("#feefc3", "#e37400"),
    "resumen_libre": ("#f8f9fa", "#5f6368"),
    "resumen_ocupada": ("#e6f4ea", "#1e8e3e"),
    "resumen_espera": ("#fef7e0", "#e37400"),
}

# Fuentes: se crean bajo demanda (CTkFont requiere ventana raíz activa).


@lru_cache(maxsize=None)
def fuente_titulo() -> ctk.CTkFont:
    """Fuente para títulos principales."""
    return ctk.CTkFont(size=26, weight="bold")


@lru_cache(maxsize=None)
def fuente_subtitulo() -> ctk.CTkFont:
    """Fuente para subtítulos y texto secundario destacado."""
    return ctk.CTkFont(size=14)


@lru_cache(maxsize=None)
def fuente_normal() -> ctk.CTkFont:
    """Fuente para texto de cuerpo y controles."""
    return ctk.CTkFont(size=13)


@lru_cache(maxsize=None)
def fuente_pequena() -> ctk.CTkFont:
    """Fuente para etiquetas auxiliares y metadatos."""
    return ctk.CTkFont(size=11)


@lru_cache(maxsize=None)
def fuente_boton() -> ctk.CTkFont:
    """Fuente para botones de acción principal."""
    return ctk.CTkFont(size=14, weight="bold")


def aplicar_tema_global() -> None:
    """Activa el tema claro en toda la aplicación CustomTkinter."""
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")


def centrar_ventana(ventana, ancho: int, alto: int) -> None:
    """Centra una ventana en la pantalla al abrirse."""
    ventana.update_idletasks()
    pantalla_ancho = ventana.winfo_screenwidth()
    pantalla_alto = ventana.winfo_screenheight()
    x = (pantalla_ancho - ancho) // 2
    y = (pantalla_alto - alto) // 2
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
