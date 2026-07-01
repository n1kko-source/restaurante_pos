"""Paleta de colores y utilidades visuales compartidas del sistema POS.

Tema claro profesional usado en todas las ventanas CustomTkinter.
"""

import tkinter
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import customtkinter as ctk

# Paleta Hogareños — naranja dorado del logo (#f59c0c) con complementos cálidos.
PALETA = {
    # Superficies generales
    "fondo": "#f7f4ef",
    "tarjeta": "#ffffff",
    "borde": "#e8dcc8",
    "texto": "#2c2416",
    "texto_suave": "#6b5d4a",
    "acento": "#f59c0c",
    "acento_hover": "#d97706",
    "acento_suave": "#fff7ed",
    "error": "#c62828",
    "exito": "#2e7d32",
    # Barra lateral
    "sidebar": "#fffcf8",
    "sidebar_borde": "#f0e6d6",
    "sidebar_hover": "#fff7ed",
    "sidebar_activo": "#ffedd5",
    "sidebar_texto": "#2c2416",
    "cerrar_sesion": "#b91c1c",
    "cerrar_sesion_hover": "#991b1b",
    # Botones
    "boton_accion": "#ffffff",
    "boton_accion_hover": "#fff7ed",
    "boton_accion_borde": "#e8c478",
    "boton_primario": "#f59c0c",
    "boton_primario_hover": "#d97706",
    "texto_boton": "#2c2416",
    "texto_boton_desactivado": "#5c4a32",
    "texto_boton_primario": "#ffffff",
    "texto_boton_primario_desactivado": "#ffffff",
    "boton_desactivado_fondo": "#ede8df",
    "boton_primario_desactivado": "#d4a056",
    # Campos de entrada
    "entrada_fondo": "#ffffff",
    "entrada_borde": "#e8c478",
    # Treeview
    "tree_fondo": "#ffffff",
    "tree_seleccion": "#ffedd5",
    "seleccion": "#f59c0c",
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

# Márgenes interiores de tarjetas con esquinas redondeadas (evita recorte de bordes).
PADDING_PANEL_H = 20
PADDING_PANEL_INFERIOR = 28
# Respiro a la derecha cuando el desplegable va en sticky="ew" junto al borde de tarjeta.
MARGEN_DESPLEGABLE_DERECHO = 4

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


def kwargs_boton_secundario(**extra):
    """Estilo compartido para botones secundarios con borde y buen contraste."""
    opciones = {
        "fg_color": PALETA["boton_accion"],
        "hover_color": PALETA["boton_accion_hover"],
        "text_color": PALETA["texto_boton"],
        "text_color_disabled": PALETA["texto_boton_desactivado"],
        "border_width": 1,
        "border_color": PALETA["boton_accion_borde"],
        "corner_radius": 10,
    }
    opciones.update(extra)
    return opciones


def kwargs_boton_primario(**extra):
    """Estilo compartido para botones de acción principal (naranja Hogareños)."""
    opciones = {
        "fg_color": PALETA["boton_primario"],
        "hover_color": PALETA["boton_primario_hover"],
        "text_color": PALETA["texto_boton_primario"],
        "text_color_disabled": PALETA["texto_boton_primario_desactivado"],
        "corner_radius": 10,
    }
    opciones.update(extra)
    return opciones


def kwargs_desplegable(**extra):
    """
    Estilo unificado para selectores (CTkComboBox / DesplegableProfesional).
    Campo blanco con borde; la zona de la flecha no usa bloque de color sólido.
    """
    opciones = {
        "fg_color": PALETA["entrada_fondo"],
        "border_color": PALETA["entrada_borde"],
        "border_width": 1,
        "button_color": PALETA["entrada_fondo"],
        "button_hover_color": PALETA["sidebar_hover"],
        "text_color": PALETA["texto"],
        "dropdown_fg_color": PALETA["tarjeta"],
        "dropdown_hover_color": PALETA["sidebar_hover"],
        "dropdown_text_color": PALETA["texto"],
        "corner_radius": 10,
        "state": "readonly",
    }
    opciones.update(extra)
    return opciones


_cache_foto_flecha: Dict[tuple, object] = {}


def limpiar_cache_ui_sesion() -> None:
    """
    Invalida cachés de UI ligados a la ventana raíz destruida (p. ej. al cerrar sesión).
    PhotoImage y CTkFont quedan inválidos si se reutilizan tras destroy().
    """
    _cache_foto_flecha.clear()
    fuente_titulo.cache_clear()
    fuente_subtitulo.cache_clear()
    fuente_normal.cache_clear()
    fuente_pequena.cache_clear()
    fuente_boton.cache_clear()


def _clave_cache_flecha(alto_px: int, master) -> tuple:
    """Clave de caché por tamaño y ventana raíz (PhotoImage es por instancia Tk)."""
    if master is not None:
        try:
            return (alto_px, id(master.winfo_toplevel()))
        except Exception:
            pass
    return (alto_px, 0)


def _procesar_flecha_png(imagen_pil):
    """
    Quita el fondo oscuro del PNG, recorta al contenido visible y deja
    un margen mínimo para que la chevron se vea nítida al escalar.
    """
    if imagen_pil.mode != "RGBA":
        imagen_pil = imagen_pil.convert("RGBA")
    pixels = imagen_pil.load()
    ancho, alto = imagen_pil.size
    for y in range(alto):
        for x in range(ancho):
            rojo, verde, azul, alpha = pixels[x, y]
            if rojo < 45 and verde < 45 and azul < 45:
                pixels[x, y] = (rojo, verde, azul, 0)

    caja = imagen_pil.getbbox()
    if caja is None:
        return imagen_pil

    margen = max(2, int(min(caja[2] - caja[0], caja[3] - caja[1]) * 0.12))
    izq = max(0, caja[0] - margen)
    arr = max(0, caja[1] - margen)
    der = min(ancho, caja[2] + margen)
    abj = min(alto, caja[3] + margen)
    return imagen_pil.crop((izq, arr, der, abj))


def _crear_foto_flecha_tk(alto_px: int, master=None):
    """
    Rasteriza flecha.png como PhotoImage para el canvas del combo.
    Retorna None si no se puede cargar el archivo.
    """
    clave = _clave_cache_flecha(alto_px, master)
    if clave in _cache_foto_flecha:
        return _cache_foto_flecha[clave]

    from config import RUTA_ICONOS

    ruta = RUTA_ICONOS / "flecha.png"
    if not ruta.is_file():
        return None

    try:
        from PIL import Image, ImageTk

        procesada = _procesar_flecha_png(Image.open(ruta))
        ancho_orig, alto_orig = procesada.size
        alto_dest = max(10, alto_px)
        ancho_dest = max(10, int(ancho_orig * (alto_dest / alto_orig)))
        procesada = procesada.resize(
            (ancho_dest, alto_dest),
            Image.Resampling.LANCZOS,
        )
        foto = ImageTk.PhotoImage(procesada, master=master)
        _cache_foto_flecha[clave] = foto
        return foto
    except Exception:
        return None


class DesplegableProfesional(ctk.CTkFrame):
    """
    Selector de solo lectura con borde redondeado, texto y flecha PNG.
    Basado en CTkFrame (como los Entry) para bordes perfectos sin recorte.
    """

    def __init__(self, master, values=None, command=None, **kwargs):
        estilo = kwargs_desplegable()
        estilo.update(kwargs)

        altura = int(estilo.pop("height", 38) or 38)
        ancho = estilo.pop("width", 140)
        fuente_ctrl = estilo.pop("font", None)
        comando = estilo.pop("command", command)
        estado = estilo.pop("state", "readonly")
        fuente_menu = estilo.pop("dropdown_font", None)

        color_texto = estilo.pop("text_color", PALETA["texto"])
        color_fondo = estilo.pop("fg_color", PALETA["entrada_fondo"])
        color_borde = estilo.pop("border_color", PALETA["entrada_borde"])
        grosor_borde = estilo.pop("border_width", 1)
        radio = estilo.pop("corner_radius", 10)
        color_hover_flecha = estilo.pop("button_hover_color", PALETA["sidebar_hover"])
        menu_fg = estilo.pop("dropdown_fg_color", PALETA["tarjeta"])
        menu_hover = estilo.pop("dropdown_hover_color", PALETA["sidebar_hover"])
        menu_texto = estilo.pop("dropdown_text_color", PALETA["texto"])

        # Claves heredadas del CTkComboBox que ya no aplican.
        estilo.pop("button_color", None)
        estilo.pop("text_color_disabled", None)
        estilo.pop("hover", None)

        super().__init__(
            master,
            width=ancho,
            height=altura,
            fg_color=color_fondo,
            border_color=color_borde,
            border_width=grosor_borde,
            corner_radius=radio,
            bg_color="transparent",
        )

        self._values = list(values) if values else []
        self._command = comando
        self._state = estado
        self._font = fuente_ctrl if fuente_ctrl is not None else fuente_normal()
        self._color_texto = color_texto
        self._color_fondo = color_fondo
        self._color_hover_flecha = color_hover_flecha
        self._valor = ""
        self._tam_flecha = max(14, int(altura * 0.38))
        self._foto_flecha = _crear_foto_flecha_tk(self._tam_flecha, master=self)

        ancho_zona_flecha = max(32, altura - 2)
        margen_izq = max(10, radio - 2)
        margen_der = max(8, radio // 2 + 2)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._contenido = ctk.CTkFrame(
            self,
            fg_color="transparent",
            bg_color="transparent",
            corner_radius=0,
        )
        self._contenido.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(margen_izq, margen_der),
            pady=max(1, grosor_borde),
        )
        self._contenido.grid_columnconfigure(0, weight=1)
        self._contenido.grid_columnconfigure(1, weight=0, minsize=ancho_zona_flecha)

        self._label_texto = ctk.CTkLabel(
            self._contenido,
            text="",
            font=self._font,
            text_color=color_texto,
            anchor="w",
            fg_color="transparent",
            bg_color="transparent",
        )
        self._label_texto.grid(row=0, column=0, sticky="ew")

        self._zona_flecha = ctk.CTkFrame(
            self._contenido,
            width=ancho_zona_flecha,
            height=max(20, altura - 6),
            fg_color="transparent",
            bg_color="transparent",
            corner_radius=6,
        )
        self._zona_flecha.grid(row=0, column=1, sticky="e")
        self._zona_flecha.grid_propagate(False)

        self._label_flecha = tkinter.Label(
            self._zona_flecha,
            image=self._foto_flecha,
            bg=self._color_fondo_solido(),
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._label_flecha.pack(expand=True)

        from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import (
            DropdownMenu,
        )

        self._menu = DropdownMenu(
            master=self,
            values=self._values,
            command=self._al_elegir_opcion,
            fg_color=menu_fg,
            hover_color=menu_hover,
            text_color=menu_texto,
            font=fuente_menu if fuente_menu is not None else self._font,
        )

        self._enlazar_interacciones()

        if self._values:
            self.set(self._values[0])

    def _color_fondo_solido(self) -> str:
        """Retorna el color de fondo del control en modo claro/oscuro."""
        return self._apply_appearance_mode(self._color_fondo)

    def _enlazar_interacciones(self) -> None:
        """Enlaza clic y hover en las zonas interactivas del selector."""
        clicables = (
            self,
            self._contenido,
            self._label_texto,
            self._zona_flecha,
            self._label_flecha,
        )
        for widget in clicables:
            widget.bind("<Button-1>", self._al_clic)
        self._zona_flecha.bind("<Enter>", self._al_entrar_flecha)
        self._zona_flecha.bind("<Leave>", self._al_salir_flecha)
        self._label_flecha.bind("<Enter>", self._al_entrar_flecha)
        self._label_flecha.bind("<Leave>", self._al_salir_flecha)

    def _actualizar_fondo_flecha(self) -> None:
        """Iguala el fondo del icono PNG con la zona de la flecha."""
        zona = self._zona_flecha.cget("fg_color")
        if zona in (None, "transparent"):
            fondo = self._color_fondo_solido()
        else:
            fondo = self._apply_appearance_mode(zona)
        self._label_flecha.configure(bg=fondo)

    def _al_clic(self, event=None) -> None:
        """Abre el menú desplegable bajo el control."""
        if self._state == tkinter.DISABLED or not self._values:
            return
        self._menu.open(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())

    def _al_elegir_opcion(self, valor: str) -> None:
        """Actualiza la selección y notifica el callback."""
        self.set(valor)
        if self._command is not None:
            self._command(valor)

    def _al_entrar_flecha(self, event=None) -> None:
        """Resalta suavemente la zona de la flecha al pasar el cursor."""
        if self._state == tkinter.DISABLED:
            return
        self._zona_flecha.configure(fg_color=self._color_hover_flecha)
        self._actualizar_fondo_flecha()

    def _al_salir_flecha(self, event=None) -> None:
        """Restaura la zona de la flecha al salir el cursor."""
        self._zona_flecha.configure(fg_color="transparent")
        self._actualizar_fondo_flecha()

    def get(self) -> str:
        """Retorna el valor seleccionado."""
        return self._valor

    def set(self, valor: str) -> None:
        """Establece el valor visible del selector."""
        if self._values and valor not in self._values:
            valor = self._values[0]
        self._valor = valor
        self._label_texto.configure(text=valor)

    def configure(self, require_redraw=False, **kwargs):
        """Configura valores, fuente, estado y colores del desplegable."""
        if "values" in kwargs:
            self._values = list(kwargs.pop("values"))
            self._menu.configure(values=self._values)
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "font" in kwargs:
            self._font = kwargs.pop("font")
            self._label_texto.configure(font=self._font)
        if "dropdown_font" in kwargs:
            self._menu.configure(font=kwargs.pop("dropdown_font"))
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            color = (
                PALETA["texto_suave"]
                if self._state == tkinter.DISABLED
                else self._color_texto
            )
            self._label_texto.configure(text_color=color)
        if "dropdown_fg_color" in kwargs:
            self._menu.configure(fg_color=kwargs.pop("dropdown_fg_color"))
        if "dropdown_hover_color" in kwargs:
            self._menu.configure(hover_color=kwargs.pop("dropdown_hover_color"))
        if "dropdown_text_color" in kwargs:
            self._menu.configure(text_color=kwargs.pop("dropdown_text_color"))
        if "text_color" in kwargs:
            self._color_texto = kwargs.pop("text_color")
            self._label_texto.configure(text_color=self._color_texto)

        super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name: str):
        """Retorna atributos compatibles con CTkComboBox."""
        if attribute_name == "values":
            return tuple(self._values)
        if attribute_name == "command":
            return self._command
        if attribute_name == "font":
            return self._font
        if attribute_name == "state":
            return self._state
        return super().cget(attribute_name)


# Color de fondo al rasterizar el PNG para iconos pequeños de la barra de título.
_FONDO_ICONO_VENTANA = (255, 252, 248, 255)
_TAMANOS_ICONO_WINDOWS = (16, 24, 32, 48, 64, 128, 256)
_ruta_icono_cache: Optional[Path] = None


def _generar_icono_desde_png(ruta_destino: Path, ruta_png: Path) -> bool:
    """
    Crea un archivo .ico válido para Windows a partir del logo PNG.
    Aplana la transparencia sobre fondo crema para que se vea bien a 16–32 px.
    """
    try:
        from PIL import Image

        imagen = Image.open(ruta_png)
        if imagen.mode != "RGBA":
            imagen = imagen.convert("RGBA")
        fondo = Image.new("RGBA", imagen.size, _FONDO_ICONO_VENTANA)
        compuesta = Image.alpha_composite(fondo, imagen)
        ruta_destino.parent.mkdir(parents=True, exist_ok=True)
        compuesta.save(
            ruta_destino,
            format="ICO",
            sizes=[(tam, tam) for tam in _TAMANOS_ICONO_WINDOWS],
        )
        return True
    except Exception:
        return False


def _obtener_ruta_icono_ventana():
    """
    Resuelve la ruta del .ico usable en Windows.
    El PNG es la fuente de verdad; se cachea en %TEMP% según la fecha del PNG.
    """
    global _ruta_icono_cache
    import tempfile

    from config import RUTA_ICONO_APP, RUTA_LOGO_PNG

    if not RUTA_LOGO_PNG.is_file():
        if RUTA_ICONO_APP.is_file():
            return RUTA_ICONO_APP
        return None

    cache = Path(tempfile.gettempdir()) / "restaurante_pos_hogarenos.ico"
    try:
        mtime_png = RUTA_LOGO_PNG.stat().st_mtime
        if cache.is_file() and cache.stat().st_mtime >= mtime_png:
            _ruta_icono_cache = cache
            return cache
    except OSError:
        pass

    if _generar_icono_desde_png(cache, RUTA_LOGO_PNG):
        _ruta_icono_cache = cache
        return cache

    if RUTA_ICONO_APP.is_file():
        return RUTA_ICONO_APP
    return None


def preparar_icono_aplicacion() -> None:
    """Genera el .ico en caché antes de abrir ventanas (evita icono genérico al inicio)."""
    _obtener_ruta_icono_ventana()


def exportar_icono_a_assets() -> bool:
    """Regenera assets/logo_hogarenos.ico desde el PNG (empaquetado y respaldo)."""
    from config import RUTA_ICONO_APP, RUTA_LOGO_PNG

    if not RUTA_LOGO_PNG.is_file():
        return False
    return _generar_icono_desde_png(RUTA_ICONO_APP, RUTA_LOGO_PNG)


def crear_imagen_logo(ancho: int, alto: int):
    """
    Carga el logo Hogareños como CTkImage.
    CustomTkinter 5.2.2 requiere instancias PIL.Image, no rutas en texto.
    Retorna None si el archivo no existe o no se puede leer.
    """
    from config import RUTA_LOGO_PNG

    return crear_imagen_asset(RUTA_LOGO_PNG, ancho, alto)


def crear_imagen_asset(ruta: Path, ancho: int, alto: int):
    """
    Carga un PNG u otro recurso gráfico como CTkImage.
    Retorna None si el archivo no existe o no se puede leer.
    """
    if not ruta.is_file():
        return None
    try:
        from PIL import Image

        imagen_pil = Image.open(ruta)
        return ctk.CTkImage(
            light_image=imagen_pil,
            dark_image=imagen_pil,
            size=(ancho, alto),
        )
    except Exception:
        return None


def aplicar_icono_ventana(ventana) -> None:
    """
    Aplica el logo Hogareños en la barra de título y en ventanas hijas.
    En la ventana raíz (CTk) también registra el icono por defecto del proceso.
    """
    ruta = _obtener_ruta_icono_ventana()
    if ruta is None:
        return

    bitmap = str(ruta.resolve())

    def _aplicar() -> None:
        if not ventana.winfo_exists():
            return
        try:
            if isinstance(ventana, ctk.CTk):
                ventana.iconbitmap(default=bitmap)
        except Exception:
            pass
        try:
            ventana.wm_iconbitmap(bitmap)
            ventana._ref_icono_hogarenos = bitmap
            return
        except Exception:
            pass
        try:
            ventana.iconbitmap(bitmap=bitmap)
            ventana._ref_icono_hogarenos = bitmap
            return
        except Exception:
            pass
        try:
            from PIL import Image, ImageTk

            from config import RUTA_LOGO_PNG

            if RUTA_LOGO_PNG.is_file():
                imagen = Image.open(RUTA_LOGO_PNG)
                imagen = imagen.resize((32, 32), Image.Resampling.LANCZOS)
                foto = ImageTk.PhotoImage(imagen, master=ventana)
                ventana.iconphoto(True, foto)
                ventana._ref_icono_hogarenos_foto = foto
        except Exception:
            pass

    _aplicar()
    ventana.after_idle(_aplicar)
    ventana.after(80, _aplicar)
    ventana.after(250, _aplicar)


def centrar_ventana(ventana, ancho: int, alto: int, parent=None) -> None:
    """Centra una ventana en pantalla o sobre su padre y aplica el icono Hogareños."""
    ventana.geometry(f"{ancho}x{alto}")
    ventana.update_idletasks()

    if parent is not None:
        try:
            parent.update_idletasks()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - ancho) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - alto) // 2)
            ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
        except tkinter.TclError:
            parent = None

    if parent is None:
        pantalla_ancho = ventana.winfo_screenwidth()
        pantalla_alto = ventana.winfo_screenheight()
        x = max(0, (pantalla_ancho - ancho) // 2)
        y = max(0, (pantalla_alto - alto) // 2)
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

    aplicar_icono_ventana(ventana)


def centrar_ventana_sobre_padre(ventana, parent) -> None:
    """Centra una ventana modal según su tamaño actual respecto al padre."""
    ventana.update_idletasks()
    try:
        parent.update_idletasks()
        ancho = ventana.winfo_width()
        alto = ventana.winfo_height()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - ancho) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - alto) // 2)
        ventana.geometry(f"+{x}+{y}")
    except tkinter.TclError:
        pass
    aplicar_icono_ventana(ventana)
