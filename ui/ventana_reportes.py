"""Pantalla de reportes: historial de facturas, cola de impresión y exportación."""

import calendar
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

import customtkinter as ctk

from config import PAGINA_TAMANO_DEFAULT, RUTA_EXPORTACION
from reports import exportar_excel, exportar_pdf
from reports.utilidades_reporte import texto_comprador
from services import auth_service, facturacion_service, reporte_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import (
    DesplegableProfesional,
    PALETA,
    MARGEN_DESPLEGABLE_DERECHO,
    PADDING_PANEL_H,
    PADDING_PANEL_INFERIOR,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
    kwargs_boton_primario,
    kwargs_boton_secundario,
)

_MESES_OPCIONES = [
    "01 - enero", "02 - febrero", "03 - marzo", "04 - abril",
    "05 - mayo", "06 - junio", "07 - julio", "08 - agosto",
    "09 - septiembre", "10 - octubre", "11 - noviembre", "12 - diciembre",
]

_ANIO_MINIMO = 2020


def _mes_desde_etiqueta(etiqueta: str) -> int:
    """Extrae el número de mes desde la etiqueta del selector."""
    return int(etiqueta.split(" - ")[0])


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"$ {monto:,.0f}".replace(",", ".")


def _opciones_anios() -> list:
    """Genera años disponibles desde el mínimo configurado hasta el actual."""
    actual = datetime.now().year
    return [str(anio) for anio in range(_ANIO_MINIMO, actual + 1)]


def _opciones_dias(anio: int, mes: int) -> list:
    """Genera etiquetas de día según el calendario del mes seleccionado."""
    _, ultimo_dia = calendar.monthrange(anio, mes)
    return [f"{dia:02d}" for dia in range(1, ultimo_dia + 1)]


def _configurar_estilo_treeview(estilo: ttk.Style, nombre: str) -> None:
    """Aplica el tema claro compartido a un Treeview."""
    estilo.layout(f"{nombre}.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    estilo.configure(
        f"{nombre}.Treeview",
        background=PALETA["tarjeta"],
        foreground=PALETA["texto"],
        fieldbackground=PALETA["tarjeta"],
        borderwidth=0,
        rowheight=28,
        font=("Segoe UI", 10),
    )
    estilo.map(
        f"{nombre}.Treeview",
        background=[("selected", PALETA["acento_suave"])],
        foreground=[("selected", PALETA["texto"])],
    )
    estilo.configure(
        f"{nombre}.Treeview.Heading",
        background=PALETA["fondo"],
        foreground=PALETA["texto"],
        relief="flat",
        font=("Segoe UI", 10, "bold"),
    )


class VentanaReportes(ctk.CTkFrame):
    """Módulo de consulta de facturas, cola de impresión y exportación."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=PALETA["fondo"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        usuario = auth_service.obtener_usuario_actual()
        self._es_administrador = usuario is not None and usuario.rol == "administrador"
        self._ultimo_directorio: Optional[Path] = None

        self._pagina_facturas = 1
        self._total_paginas_facturas = 1
        self._facturas_cache: Dict[str, dict] = {}

        self._pagina_cola = 1
        self._total_paginas_cola = 1
        self._cola_cache: Dict[str, dict] = {}

        self._construir_panel()
        self._actualizar_dias_calendario()
        self._cargar_facturas_dia()
        self._cargar_cola_impresion()

    def _construir_panel(self) -> None:
        """Construye las pestañas principales del módulo."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=0, sticky="nsew", padx=40, pady=24)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Reportes de ventas",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=28, pady=(24, 8), sticky="w")

        self._tabview = ctk.CTkTabview(
            panel,
            fg_color=PALETA["tarjeta"],
            segmented_button_fg_color=PALETA["fondo"],
            segmented_button_selected_color=PALETA["acento"],
            segmented_button_selected_hover_color=PALETA["acento_hover"],
            segmented_button_unselected_color=PALETA["fondo"],
            segmented_button_unselected_hover_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self._tabview.grid(
            row=1, column=0, padx=PADDING_PANEL_H, pady=(0, PADDING_PANEL_INFERIOR), sticky="nsew"
        )

        tab_facturas = self._tabview.add("Facturas del día")
        tab_cola = self._tabview.add("Cola de impresión")
        tab_exportar = self._tabview.add("Exportar reportes")

        tab_facturas.grid_columnconfigure(0, weight=1)
        tab_facturas.grid_rowconfigure(2, weight=1)
        tab_cola.grid_columnconfigure(0, weight=1)
        tab_cola.grid_rowconfigure(2, weight=1)
        tab_exportar.grid_columnconfigure(0, weight=1)

        self._construir_tab_facturas(tab_facturas)
        self._construir_tab_cola(tab_cola)
        self._construir_tab_exportar(tab_exportar)

    def _construir_tab_facturas(self, contenedor: ctk.CTkFrame) -> None:
        """Pestaña de consulta diaria con calendario y listado."""
        ctk.CTkLabel(
            contenedor,
            text="Seleccione año, mes y día para ver el historial de facturas.",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=4, pady=(4, 12), sticky="w")

        calendario = ctk.CTkFrame(contenedor, fg_color="transparent")
        calendario.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        calendario.grid_columnconfigure((1, 3, 5), weight=1)

        ahora = datetime.now()
        anios = _opciones_anios()

        ctk.CTkLabel(
            calendario, text="Año", font=fuente_pequena(), text_color=PALETA["texto_suave"]
        ).grid(row=0, column=0, padx=(4, 8), pady=6, sticky="w")

        self._menu_anio_dia = DesplegableProfesional(
            calendario,
            values=anios,
            height=36,
            font=fuente_normal(),
            command=self._al_cambiar_calendario,
        )
        self._menu_anio_dia.set(str(ahora.year))
        self._menu_anio_dia.grid(
            row=0, column=1, sticky="ew", pady=6, padx=(0, 12)
        )

        ctk.CTkLabel(
            calendario, text="Mes", font=fuente_pequena(), text_color=PALETA["texto_suave"]
        ).grid(row=0, column=2, padx=(4, 8), pady=6, sticky="w")

        self._menu_mes_dia = DesplegableProfesional(
            calendario,
            values=_MESES_OPCIONES,
            height=36,
            font=fuente_normal(),
            command=self._al_cambiar_calendario,
        )
        self._menu_mes_dia.set(_MESES_OPCIONES[ahora.month - 1])
        self._menu_mes_dia.grid(
            row=0, column=3, sticky="ew", pady=6, padx=(0, 12)
        )

        ctk.CTkLabel(
            calendario, text="Día", font=fuente_pequena(), text_color=PALETA["texto_suave"]
        ).grid(row=0, column=4, padx=(4, 8), pady=6, sticky="w")

        self._menu_dia = DesplegableProfesional(
            calendario,
            values=_opciones_dias(ahora.year, ahora.month),
            height=36,
            font=fuente_normal(),
            command=self._al_cambiar_calendario,
        )
        self._menu_dia.set(f"{ahora.day:02d}")
        self._menu_dia.grid(
            row=0, column=5, sticky="ew", pady=6, padx=(0, MARGEN_DESPLEGABLE_DERECHO)
        )

        marco_tree = ctk.CTkFrame(contenedor, fg_color="transparent")
        marco_tree.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)
        contenedor.grid_rowconfigure(2, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "Reportes.Facturas")

        columnas = ("numero", "comprador", "hora", "total")
        self._tree_facturas = ttk.Treeview(
            marco_tree,
            columns=columnas,
            show="headings",
            style="Reportes.Facturas.Treeview",
            selectmode="browse",
        )
        encabezados = {
            "numero": ("Nº factura", 120),
            "comprador": ("Comprador", 200),
            "hora": ("Hora", 80),
            "total": ("Total", 120),
        }
        for col, (texto, ancho) in encabezados.items():
            self._tree_facturas.heading(col, text=texto)
            if col == "total":
                anchor = "e"
            elif col == "hora":
                anchor = "center"
            else:
                anchor = "w"
            self._tree_facturas.column(
                col, width=ancho, stretch=(col == "comprador"), anchor=anchor
            )

        scroll = ttk.Scrollbar(
            marco_tree, orient="vertical", command=self._tree_facturas.yview
        )
        self._tree_facturas.configure(yscrollcommand=scroll.set)
        self._tree_facturas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tree_facturas.bind(
            "<<TreeviewSelect>>", lambda _e: self._actualizar_botones_facturas()
        )

        paginacion = ctk.CTkFrame(contenedor, fg_color="transparent")
        paginacion.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        paginacion.grid_columnconfigure(1, weight=1)

        self._btn_fact_ant = ctk.CTkButton(
            paginacion,
            text="Anterior",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_anterior_facturas,
            **kwargs_boton_secundario(),
        )
        self._btn_fact_ant.grid(row=0, column=0, padx=(4, 8))

        self._label_pagina_facturas = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        )
        self._label_pagina_facturas.grid(row=0, column=1)

        self._btn_fact_sig = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_siguiente_facturas,
            **kwargs_boton_secundario(),
        )
        self._btn_fact_sig.grid(row=0, column=2, padx=(8, 4))

        self._label_resumen_dia = ctk.CTkLabel(
            contenedor,
            text="",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        )
        self._label_resumen_dia.grid(row=4, column=0, padx=4, pady=(0, 8), sticky="w")

        acciones = ctk.CTkFrame(contenedor, fg_color="transparent")
        acciones.grid(row=5, column=0, sticky="ew")
        acciones.grid_columnconfigure((0, 1, 2), weight=1)

        self._btn_imprimir_factura = ctk.CTkButton(
            acciones,
            text="Imprimir factura",
            height=42,
            font=fuente_boton(),
            command=self._imprimir_factura_seleccionada,
            state="disabled",
            **kwargs_boton_primario(),
        )
        self._btn_imprimir_factura.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            acciones,
            text="Exportar PDF del día",
            height=42,
            font=fuente_boton(),
            command=lambda: self._exportar_dia_desde_calendario("pdf"),
            **kwargs_boton_secundario(),
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            acciones,
            text="Exportar Excel del día",
            height=42,
            font=fuente_boton(),
            command=lambda: self._exportar_dia_desde_calendario("xlsx"),
            **kwargs_boton_secundario(),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _construir_tab_cola(self, contenedor: ctk.CTkFrame) -> None:
        """Pestaña de facturas pendientes de impresión."""
        self._label_cola_pendientes = ctk.CTkLabel(
            contenedor,
            text="",
            font=fuente_pequena(),
            text_color=PALETA["acento_hover"],
        )
        self._label_cola_pendientes.grid(row=0, column=0, padx=4, pady=(4, 4), sticky="w")

        ctk.CTkLabel(
            contenedor,
            text=(
                "Facturas que no se pudieron imprimir por fallo de la impresora. "
                "Seleccione una o reimprima todas cuando el equipo esté disponible."
            ),
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
            wraplength=640,
            justify="left",
        ).grid(row=1, column=0, padx=4, pady=(0, 12), sticky="w")

        marco_tree = ctk.CTkFrame(contenedor, fg_color="transparent")
        marco_tree.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        marco_tree.grid_columnconfigure(0, weight=1)
        marco_tree.grid_rowconfigure(0, weight=1)
        contenedor.grid_rowconfigure(2, weight=1)

        estilo = ttk.Style()
        estilo.theme_use("clam")
        _configurar_estilo_treeview(estilo, "Reportes.Cola")

        columnas = ("numero", "fecha", "hora", "total", "error")
        self._tree_cola = ttk.Treeview(
            marco_tree,
            columns=columnas,
            show="headings",
            style="Reportes.Cola.Treeview",
            selectmode="browse",
        )
        encabezados = {
            "numero": ("Nº factura", 150),
            "fecha": ("Fecha", 100),
            "hora": ("Hora", 80),
            "total": ("Total", 110),
            "error": ("Último error", 220),
        }
        for col, (texto, ancho) in encabezados.items():
            self._tree_cola.heading(col, text=texto)
            anchor = "w"
            if col in ("hora", "fecha"):
                anchor = "center"
            elif col == "total":
                anchor = "e"
            self._tree_cola.column(
                col,
                width=ancho,
                stretch=(col == "error"),
                anchor=anchor,
            )

        scroll = ttk.Scrollbar(marco_tree, orient="vertical", command=self._tree_cola.yview)
        self._tree_cola.configure(yscrollcommand=scroll.set)
        self._tree_cola.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        self._tree_cola.bind(
            "<<TreeviewSelect>>", lambda _e: self._actualizar_botones_cola()
        )

        paginacion = ctk.CTkFrame(contenedor, fg_color="transparent")
        paginacion.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        paginacion.grid_columnconfigure(1, weight=1)

        self._btn_cola_ant = ctk.CTkButton(
            paginacion,
            text="Anterior",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_anterior_cola,
            **kwargs_boton_secundario(),
        )
        self._btn_cola_ant.grid(row=0, column=0, padx=(4, 8))

        self._label_pagina_cola = ctk.CTkLabel(
            paginacion,
            text="Página 1 de 1",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        )
        self._label_pagina_cola.grid(row=0, column=1)

        self._btn_cola_sig = ctk.CTkButton(
            paginacion,
            text="Siguiente",
            width=100,
            height=32,
            font=fuente_pequena(),
            command=self._pagina_siguiente_cola,
            **kwargs_boton_secundario(),
        )
        self._btn_cola_sig.grid(row=0, column=2, padx=(8, 4))

        acciones = ctk.CTkFrame(contenedor, fg_color="transparent")
        acciones.grid(row=4, column=0, sticky="ew")
        acciones.grid_columnconfigure((0, 1), weight=1)

        self._btn_reimprimir_cola = ctk.CTkButton(
            acciones,
            text="Reimprimir seleccionada",
            height=42,
            font=fuente_boton(),
            command=self._reimprimir_cola_seleccionada,
            state="disabled",
            **kwargs_boton_primario(),
        )
        self._btn_reimprimir_cola.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            acciones,
            text="Reimprimir todas en cola",
            height=42,
            font=fuente_boton(),
            command=self._reimprimir_toda_cola,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _construir_tab_exportar(self, contenedor: ctk.CTkFrame) -> None:
        """Pestaña de exportación PDF/Excel de reportes consolidados."""
        ctk.CTkLabel(
            contenedor,
            text="Exporte reportes consolidados diarios o mensuales a PDF y Excel.",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=4, pady=(4, 16), sticky="w")

        formulario = ctk.CTkFrame(contenedor, fg_color="transparent")
        formulario.grid(row=1, column=0, sticky="ew")
        formulario.grid_columnconfigure(1, weight=1)

        tipos = ["Diario", "Mensual"] if self._es_administrador else ["Diario"]

        ctk.CTkLabel(
            formulario,
            text="Tipo de reporte",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=(4, 12), pady=8, sticky="w")

        self._menu_tipo = DesplegableProfesional(
            formulario,
            values=tipos,
            height=38,
            font=fuente_normal(),
            command=self._al_cambiar_tipo,
        )
        self._menu_tipo.grid(
            row=0, column=1, sticky="ew", pady=8, padx=(0, MARGEN_DESPLEGABLE_DERECHO)
        )

        self._marco_diario = ctk.CTkFrame(formulario, fg_color="transparent")
        self._marco_diario.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._marco_diario.grid_columnconfigure((1, 3, 5), weight=1)

        ahora = datetime.now()
        anios = _opciones_anios()

        ctk.CTkLabel(
            self._marco_diario,
            text="Año",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=(4, 8), pady=8, sticky="w")

        self._menu_anio_exp = DesplegableProfesional(
            self._marco_diario,
            values=anios,
            height=38,
            font=fuente_normal(),
            command=self._al_cambiar_calendario_exportacion,
        )
        self._menu_anio_exp.set(str(ahora.year))
        self._menu_anio_exp.grid(row=0, column=1, sticky="ew", pady=8, padx=(0, 12))

        ctk.CTkLabel(
            self._marco_diario,
            text="Mes",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=2, padx=(4, 8), pady=8, sticky="w")

        self._menu_mes_exp = DesplegableProfesional(
            self._marco_diario,
            values=_MESES_OPCIONES,
            height=38,
            font=fuente_normal(),
            command=self._al_cambiar_calendario_exportacion,
        )
        self._menu_mes_exp.set(_MESES_OPCIONES[ahora.month - 1])
        self._menu_mes_exp.grid(row=0, column=3, sticky="ew", pady=8, padx=(0, 12))

        ctk.CTkLabel(
            self._marco_diario,
            text="Día",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=4, padx=(4, 8), pady=8, sticky="w")

        self._menu_dia_exp = DesplegableProfesional(
            self._marco_diario,
            values=_opciones_dias(ahora.year, ahora.month),
            height=38,
            font=fuente_normal(),
        )
        self._menu_dia_exp.set(f"{ahora.day:02d}")
        self._menu_dia_exp.grid(
            row=0, column=5, sticky="ew", pady=8, padx=(0, MARGEN_DESPLEGABLE_DERECHO)
        )

        self._marco_mensual = ctk.CTkFrame(formulario, fg_color="transparent")
        self._marco_mensual.grid(row=2, column=0, columnspan=2, sticky="ew")
        self._marco_mensual.grid_columnconfigure(1, weight=1)
        self._marco_mensual.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            self._marco_mensual,
            text="Año",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=(4, 12), pady=8, sticky="w")

        self._menu_anio_mensual = DesplegableProfesional(
            self._marco_mensual,
            values=anios,
            height=38,
            font=fuente_normal(),
        )
        self._menu_anio_mensual.set(str(ahora.year))
        self._menu_anio_mensual.grid(row=0, column=1, sticky="ew", pady=8, padx=(0, 16))

        ctk.CTkLabel(
            self._marco_mensual,
            text="Mes",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=2, padx=(4, 12), pady=8, sticky="w")

        mes_actual = _MESES_OPCIONES[ahora.month - 1]
        self._menu_mes = DesplegableProfesional(
            self._marco_mensual,
            values=_MESES_OPCIONES,
            height=38,
            font=fuente_normal(),
        )
        self._menu_mes.set(mes_actual)
        self._menu_mes.grid(
            row=0, column=3, sticky="ew", pady=8, padx=(0, MARGEN_DESPLEGABLE_DERECHO)
        )

        self._label_ayuda = ctk.CTkLabel(
            contenedor,
            text="",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
            wraplength=520,
            justify="left",
        )
        self._label_ayuda.grid(row=2, column=0, padx=4, pady=(8, 16), sticky="w")

        botones = ctk.CTkFrame(contenedor, fg_color="transparent")
        botones.grid(row=3, column=0, sticky="ew")
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Exportar PDF",
            height=44,
            font=fuente_boton(),
            command=self._exportar_pdf,
            **kwargs_boton_primario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            botones,
            text="Exportar Excel",
            height=44,
            font=fuente_boton(),
            command=self._exportar_excel,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self._al_cambiar_tipo(self._menu_tipo.get())

    # --- Calendario y listado de facturas ---

    def _fecha_seleccionada(self) -> str:
        """Construye la fecha ISO desde los selectores del calendario de facturas."""
        return self._fecha_desde_menus(
            self._menu_anio_dia, self._menu_mes_dia, self._menu_dia
        )

    @staticmethod
    def _fecha_desde_menus(menu_anio, menu_mes, menu_dia) -> str:
        """Construye fecha ISO desde tres desplegables año/mes/día."""
        anio = int(menu_anio.get())
        mes = _mes_desde_etiqueta(menu_mes.get())
        dia = int(menu_dia.get())
        return f"{anio:04d}-{mes:02d}-{dia:02d}"

    def _fecha_exportacion_diaria(self) -> str:
        """Fecha ISO seleccionada en la pestaña de exportación diaria."""
        return self._fecha_desde_menus(
            self._menu_anio_exp, self._menu_mes_exp, self._menu_dia_exp
        )

    def _anio_mes_exportacion_mensual(self) -> tuple:
        """Retorna (año, mes) de la exportación mensual."""
        return int(self._menu_anio_mensual.get()), _mes_desde_etiqueta(
            self._menu_mes.get()
        )

    def _actualizar_dias_menu(self, menu_anio, menu_mes, menu_dia) -> None:
        """Actualiza el desplegable de días según año y mes."""
        anio = int(menu_anio.get())
        mes = _mes_desde_etiqueta(menu_mes.get())
        dias = _opciones_dias(anio, mes)
        dia_actual = menu_dia.get()
        menu_dia.configure(values=dias)
        if dia_actual in dias:
            menu_dia.set(dia_actual)
        else:
            menu_dia.set(dias[-1])

    def _al_cambiar_calendario_exportacion(self, _valor=None) -> None:
        """Actualiza los días disponibles al cambiar año o mes en exportación."""
        self._actualizar_dias_menu(
            self._menu_anio_exp, self._menu_mes_exp, self._menu_dia_exp
        )

    def _al_cambiar_calendario(self, _valor=None) -> None:
        """Recarga el listado al cambiar año, mes o día."""
        self._actualizar_dias_calendario()
        self._pagina_facturas = 1
        self._cargar_facturas_dia()

    def _actualizar_dias_calendario(self) -> None:
        """Actualiza el desplegable de días del calendario de facturas."""
        self._actualizar_dias_menu(
            self._menu_anio_dia, self._menu_mes_dia, self._menu_dia
        )

    def _cargar_facturas_dia(self) -> None:
        """Carga la página actual del Treeview de facturas del día."""
        try:
            fecha = self._fecha_seleccionada()
            resultado = reporte_service.listar_facturas_dia(
                fecha, self._pagina_facturas, PAGINA_TAMANO_DEFAULT
            )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return

        self._total_paginas_facturas = resultado["total_paginas"]
        self._facturas_cache.clear()

        for item in self._tree_facturas.get_children():
            self._tree_facturas.delete(item)

        for factura in resultado["facturas"]:
            iid = str(factura["id"])
            self._facturas_cache[iid] = factura
            self._tree_facturas.insert(
                "",
                "end",
                iid=iid,
                values=(
                    factura["numero"],
                    texto_comprador(factura.get("comprador_nombre", "")),
                    factura["hora"][:5],
                    _formatear_pesos(factura["total_neto"]),
                ),
            )

        self._label_pagina_facturas.configure(
            text=f"Página {resultado['pagina']} de {resultado['total_paginas']}"
        )
        self._btn_fact_ant.configure(
            state="normal" if resultado["pagina"] > 1 else "disabled"
        )
        self._btn_fact_sig.configure(
            state="normal"
            if resultado["pagina"] < resultado["total_paginas"]
            else "disabled"
        )

        if resultado["total"] == 0:
            resumen = f"{fecha}: sin facturas registradas."
        else:
            resumen = (
                f"{fecha}: {resultado['total']} factura(s) en total. "
                f"Página actual: {len(resultado['facturas'])} registro(s)."
            )
        self._label_resumen_dia.configure(text=resumen)
        self._actualizar_botones_facturas()

    def _pagina_anterior_facturas(self) -> None:
        """Retrocede una página en el listado de facturas."""
        if self._pagina_facturas > 1:
            self._pagina_facturas -= 1
            self._cargar_facturas_dia()

    def _pagina_siguiente_facturas(self) -> None:
        """Avanza una página en el listado de facturas."""
        if self._pagina_facturas < self._total_paginas_facturas:
            self._pagina_facturas += 1
            self._cargar_facturas_dia()

    def _factura_seleccionada(self) -> Optional[dict]:
        """Retorna la factura seleccionada en el Treeview diario."""
        seleccion = self._tree_facturas.selection()
        if not seleccion:
            return None
        return self._facturas_cache.get(seleccion[0])

    def _actualizar_botones_facturas(self) -> None:
        """Habilita o deshabilita acciones según la selección."""
        tiene = self._factura_seleccionada() is not None
        self._btn_imprimir_factura.configure(
            state="normal" if tiene else "disabled"
        )

    def _imprimir_factura_seleccionada(self) -> None:
        """Reimprime la factura seleccionada en la impresora térmica."""
        factura = self._factura_seleccionada()
        if factura is None:
            return
        try:
            ok, mensaje = facturacion_service.imprimir_factura(factura["id"])
        except ErrorAcceso as error:
            self._manejar_error(error)
            return

        if ok:
            messagebox.showinfo("Impresión", mensaje, parent=self.winfo_toplevel())
        else:
            messagebox.showwarning(
                "Impresión",
                f"No se pudo imprimir la factura {factura['numero']}:\n{mensaje}",
                parent=self.winfo_toplevel(),
            )
        self._cargar_cola_impresion()

    def _exportar_dia_desde_calendario(self, extension: str) -> None:
        """Exporta el reporte consolidado del día seleccionado en el calendario."""
        self._exportar_reporte(extension, es_diario=True, fecha=self._fecha_seleccionada())

    # --- Cola de impresión ---

    def _cargar_cola_impresion(self) -> None:
        """Carga la página actual del Treeview de cola de impresión."""
        try:
            resultado = reporte_service.listar_cola_impresion(
                self._pagina_cola, PAGINA_TAMANO_DEFAULT
            )
        except ErrorAcceso as error:
            self._manejar_error(error)
            return

        self._total_paginas_cola = resultado["total_paginas"]
        self._cola_cache.clear()

        for item in self._tree_cola.get_children():
            self._tree_cola.delete(item)

        for registro in resultado["registros"]:
            iid = str(registro["factura_id"])
            self._cola_cache[iid] = registro
            error_texto = registro["error_ultimo"]
            if len(error_texto) > 60:
                error_texto = error_texto[:57] + "..."
            self._tree_cola.insert(
                "",
                "end",
                iid=iid,
                values=(
                    registro["numero"],
                    registro["fecha"],
                    registro["hora"][:5],
                    _formatear_pesos(registro["total_neto"]),
                    error_texto,
                ),
            )

        self._label_pagina_cola.configure(
            text=f"Página {resultado['pagina']} de {resultado['total_paginas']}"
        )
        self._btn_cola_ant.configure(
            state="normal" if resultado["pagina"] > 1 else "disabled"
        )
        self._btn_cola_sig.configure(
            state="normal"
            if resultado["pagina"] < resultado["total_paginas"]
            else "disabled"
        )
        self._actualizar_botones_cola()
        if resultado["total"] > 0:
            self._label_cola_pendientes.configure(
                text=f"{resultado['total']} factura(s) pendiente(s) de impresión"
            )
        else:
            self._label_cola_pendientes.configure(text="Sin facturas pendientes")

    def _pagina_anterior_cola(self) -> None:
        """Retrocede una página en la cola de impresión."""
        if self._pagina_cola > 1:
            self._pagina_cola -= 1
            self._cargar_cola_impresion()

    def _pagina_siguiente_cola(self) -> None:
        """Avanza una página en la cola de impresión."""
        if self._pagina_cola < self._total_paginas_cola:
            self._pagina_cola += 1
            self._cargar_cola_impresion()

    def _registro_cola_seleccionado(self) -> Optional[dict]:
        """Retorna el registro de cola seleccionado."""
        seleccion = self._tree_cola.selection()
        if not seleccion:
            return None
        return self._cola_cache.get(seleccion[0])

    def _actualizar_botones_cola(self) -> None:
        """Habilita reimprimir según selección en cola."""
        tiene = self._registro_cola_seleccionado() is not None
        self._btn_reimprimir_cola.configure(
            state="normal" if tiene else "disabled"
        )

    def _reimprimir_cola_seleccionada(self) -> None:
        """Reimprime la factura seleccionada en la cola."""
        registro = self._registro_cola_seleccionado()
        if registro is None:
            return
        self._ejecutar_reimpresion(registro["factura_id"], registro["numero"])

    def _reimprimir_toda_cola(self) -> None:
        """Reimprime todas las facturas pendientes de la cola."""
        try:
            total = reporte_service.contar_cola_impresion()
        except ErrorAcceso as error:
            self._manejar_error(error)
            return

        if total == 0:
            messagebox.showinfo(
                "Cola de impresión",
                "No hay facturas pendientes de impresión.",
                parent=self.winfo_toplevel(),
            )
            return

        if not messagebox.askyesno(
            "Reimprimir cola",
            f"¿Desea reimprimir las {total} factura(s) pendientes?",
            parent=self.winfo_toplevel(),
        ):
            return

        ids_pendientes = []
        pagina = 1
        while True:
            try:
                resultado = reporte_service.listar_cola_impresion(
                    pagina, PAGINA_TAMANO_DEFAULT
                )
            except ErrorAcceso as error:
                self._manejar_error(error)
                return

            for registro in resultado["registros"]:
                ids_pendientes.append(
                    (registro["factura_id"], registro["numero"])
                )

            if pagina >= resultado["total_paginas"]:
                break
            pagina += 1

        exitosas = 0
        fallidas = 0
        for factura_id, numero in ids_pendientes:
            try:
                ok, _ = facturacion_service.imprimir_factura(factura_id)
            except ErrorAcceso as error:
                self._manejar_error(error)
                return
            if ok:
                exitosas += 1
            else:
                fallidas += 1

        messagebox.showinfo(
            "Cola de impresión",
            f"Reimpresión finalizada.\n\n"
            f"Exitosas: {exitosas}\n"
            f"Con error: {fallidas}",
            parent=self.winfo_toplevel(),
        )
        self._pagina_cola = 1
        self._cargar_cola_impresion()

    def _ejecutar_reimpresion(self, factura_id: int, numero: str) -> None:
        """Reimprime una factura y refresca la cola."""
        try:
            ok, mensaje = facturacion_service.imprimir_factura(factura_id)
        except ErrorAcceso as error:
            self._manejar_error(error)
            return

        if ok:
            messagebox.showinfo(
                "Impresión",
                f"Factura {numero} impresa correctamente.",
                parent=self.winfo_toplevel(),
            )
        else:
            messagebox.showwarning(
                "Impresión",
                f"No se pudo imprimir {numero}:\n{mensaje}",
                parent=self.winfo_toplevel(),
            )
        self._cargar_cola_impresion()

    # --- Exportación (pestaña existente) ---

    def _al_cambiar_tipo(self, tipo: str) -> None:
        """Muestra u oculta selectores según el tipo de reporte."""
        es_diario = tipo == "Diario"
        if es_diario:
            self._marco_diario.grid()
            self._marco_mensual.grid_remove()
            self._label_ayuda.configure(
                text=(
                    "Consolida las ventas pagadas del día seleccionado. "
                    "Exporte el archivo a PDF o Excel en su equipo."
                ),
            )
        else:
            self._marco_diario.grid_remove()
            self._marco_mensual.grid()
            self._label_ayuda.configure(
                text=(
                    "Consolida las ventas del mes e incluye los cierres diarios. "
                    "Solo disponible para administrador. Exporte a PDF o Excel."
                ),
            )

    def _es_diario(self) -> bool:
        """Retorna True si el tipo seleccionado es diario."""
        return self._menu_tipo.get() == "Diario"

    def _exportar_reporte(
        self,
        extension: str,
        es_diario: bool,
        fecha: Optional[str] = None,
        anio: Optional[int] = None,
        mes: Optional[int] = None,
    ) -> None:
        """Genera y guarda un reporte diario o mensual en PDF o Excel."""
        extension = extension.lstrip(".")
        try:
            if es_diario:
                if not fecha:
                    raise ValueError("Fecha no especificada para el reporte diario.")
                reporte = reporte_service.reporte_diario(fecha)
                nombre = f"reporte_diario_{fecha}.{extension}"
            else:
                if anio is None or mes is None:
                    raise ValueError("Año y mes requeridos para el reporte mensual.")
                reporte = reporte_service.reporte_mensual(anio, mes)
                nombre = f"reporte_mensual_{anio}-{mes:02d}.{extension}"

            ruta_destino = self._solicitar_ruta_guardado(extension, nombre)
            if ruta_destino is None:
                return

            if es_diario:
                if extension == "pdf":
                    ruta = exportar_pdf.exportar_reporte_diario_pdf(
                        reporte, ruta_destino=ruta_destino
                    )
                else:
                    ruta = exportar_excel.exportar_reporte_diario_excel(
                        reporte, ruta_destino=ruta_destino
                    )
            elif extension == "pdf":
                ruta = exportar_pdf.exportar_reporte_mensual_pdf(
                    reporte, ruta_destino=ruta_destino
                )
            else:
                ruta = exportar_excel.exportar_reporte_mensual_excel(
                    reporte, ruta_destino=ruta_destino
                )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return
        except Exception as error:
            messagebox.showerror(
                "Error de exportación",
                f"No se pudo generar el archivo:\n{error}",
                parent=self.winfo_toplevel(),
            )
            return

        formato = "PDF" if extension == "pdf" else "Excel"
        if es_diario:
            resumen = (
                f"Reporte diario exportado correctamente.\n\n"
                f"Archivo: {ruta}\n"
                f"Formato: {formato}"
            )
        else:
            resumen = (
                f"Reporte mensual exportado correctamente.\n\n"
                f"Archivo: {ruta}\n"
                f"Formato: {formato}"
            )
        messagebox.showinfo("Exportación exitosa", resumen, parent=self.winfo_toplevel())

    def _directorio_inicial_dialogo(self) -> str:
        """Retorna la carpeta inicial para el diálogo Guardar como."""
        if self._ultimo_directorio is not None and self._ultimo_directorio.is_dir():
            return str(self._ultimo_directorio)
        RUTA_EXPORTACION.mkdir(parents=True, exist_ok=True)
        return str(RUTA_EXPORTACION)

    def _solicitar_ruta_guardado(
        self, extension: str, nombre_sugerido: str
    ) -> Optional[Path]:
        """
        Abre el diálogo del sistema para elegir ubicación y nombre del archivo.
        Retorna None si el usuario cancela.
        """
        extension = extension.lstrip(".")
        if extension == "pdf":
            titulo = "Guardar reporte como PDF"
            tipos = [("Documento PDF", "*.pdf"), ("Todos los archivos", "*.*")]
        else:
            titulo = "Guardar reporte como Excel"
            tipos = [("Libro de Excel", "*.xlsx"), ("Todos los archivos", "*.*")]

        ruta = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title=titulo,
            initialdir=self._directorio_inicial_dialogo(),
            initialfile=nombre_sugerido,
            defaultextension=f".{extension}",
            filetypes=tipos,
        )
        if not ruta:
            return None

        destino = Path(ruta)
        if destino.suffix.lower() != f".{extension}":
            destino = destino.with_suffix(f".{extension}")

        self._ultimo_directorio = destino.parent
        return destino

    def _manejar_error(self, error: Exception) -> None:
        """Muestra errores de negocio o acceso."""
        titulo = "Acceso denegado" if isinstance(error, ErrorAcceso) else "Reportes"
        messagebox.showerror(titulo, str(error), parent=self.winfo_toplevel())

    def _exportar_pdf(self) -> None:
        """Genera y guarda el reporte en PDF desde la pestaña de exportación."""
        if self._es_diario():
            self._exportar_reporte(
                "pdf", es_diario=True, fecha=self._fecha_exportacion_diaria()
            )
        else:
            anio, mes = self._anio_mes_exportacion_mensual()
            self._exportar_reporte("pdf", es_diario=False, anio=anio, mes=mes)

    def _exportar_excel(self) -> None:
        """Genera y guarda el reporte en Excel desde la pestaña de exportación."""
        if self._es_diario():
            self._exportar_reporte(
                "xlsx", es_diario=True, fecha=self._fecha_exportacion_diaria()
            )
        else:
            anio, mes = self._anio_mes_exportacion_mensual()
            self._exportar_reporte("xlsx", es_diario=False, anio=anio, mes=mes)


@requiere_rol("supervisor", "administrador")
def mostrar_en(contenedor) -> VentanaReportes:
    """
    Incrusta el módulo de reportes en el frame contenedor.
    Primera línea de defensa: decorador @requiere_rol.
    """
    ventana = VentanaReportes(contenedor)
    ventana.grid(row=0, column=0, sticky="nsew")
    contenedor.grid_columnconfigure(0, weight=1)
    contenedor.grid_rowconfigure(0, weight=1)
    return ventana
