"""Pantalla de reportes con exportación PDF y Excel."""

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from config import RUTA_EXPORTACION
from reports import exportar_excel, exportar_pdf
from services import auth_service, reporte_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import (
    PALETA,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
)

_MESES_OPCIONES = [
    "01 - enero", "02 - febrero", "03 - marzo", "04 - abril",
    "05 - mayo", "06 - junio", "07 - julio", "08 - agosto",
    "09 - septiembre", "10 - octubre", "11 - noviembre", "12 - diciembre",
]


def _mes_desde_etiqueta(etiqueta: str) -> int:
    """Extrae el número de mes desde la etiqueta del selector."""
    return int(etiqueta.split(" - ")[0])


class VentanaReportes(ctk.CTkFrame):
    """Módulo de exportación de reportes diarios y mensuales."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=PALETA["fondo"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        usuario = auth_service.obtener_usuario_actual()
        self._es_administrador = usuario is not None and usuario.rol == "administrador"
        self._ultimo_directorio: Optional[Path] = None

        self._construir_panel()

    def _construir_panel(self) -> None:
        """Construye el formulario de selección y exportación."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=0, sticky="nsew", padx=40, pady=24)
        panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            panel,
            text="Reportes de ventas",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=28, pady=(24, 6), sticky="w")

        ctk.CTkLabel(
            panel,
            text="Exporte reportes diarios o mensuales a PDF y Excel.",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, padx=28, pady=(0, 20), sticky="w")

        formulario = ctk.CTkFrame(panel, fg_color="transparent")
        formulario.grid(row=2, column=0, padx=28, pady=(0, 12), sticky="ew")
        formulario.grid_columnconfigure(1, weight=1)

        tipos = ["Diario", "Mensual"] if self._es_administrador else ["Diario"]

        ctk.CTkLabel(
            formulario,
            text="Tipo de reporte",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=(4, 12), pady=8, sticky="w")

        self._menu_tipo = ctk.CTkOptionMenu(
            formulario,
            values=tipos,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            button_color=PALETA["boton_primario"],
            button_hover_color=PALETA["boton_primario_hover"],
            text_color=PALETA["texto"],
            dropdown_fg_color=PALETA["tarjeta"],
            command=self._al_cambiar_tipo,
        )
        self._menu_tipo.grid(row=0, column=1, sticky="ew", pady=8)

        self._marco_diario = ctk.CTkFrame(formulario, fg_color="transparent")
        self._marco_diario.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._marco_diario.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._marco_diario,
            text="Fecha (AAAA-MM-DD)",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=(4, 12), pady=8, sticky="w")

        self._entrada_fecha = ctk.CTkEntry(
            self._marco_diario,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            border_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self._entrada_fecha.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._entrada_fecha.grid(row=0, column=1, sticky="ew", pady=8)

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

        self._entrada_anio = ctk.CTkEntry(
            self._marco_mensual,
            width=100,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            border_color=PALETA["borde"],
            text_color=PALETA["texto"],
        )
        self._entrada_anio.insert(0, str(datetime.now().year))
        self._entrada_anio.grid(row=0, column=1, sticky="w", pady=8, padx=(0, 16))

        ctk.CTkLabel(
            self._marco_mensual,
            text="Mes",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=2, padx=(4, 12), pady=8, sticky="w")

        mes_actual = _MESES_OPCIONES[datetime.now().month - 1]
        self._menu_mes = ctk.CTkOptionMenu(
            self._marco_mensual,
            values=_MESES_OPCIONES,
            height=38,
            font=fuente_normal(),
            fg_color=PALETA["entrada_fondo"],
            button_color=PALETA["boton_primario"],
            button_hover_color=PALETA["boton_primario_hover"],
            text_color=PALETA["texto"],
            dropdown_fg_color=PALETA["tarjeta"],
        )
        self._menu_mes.set(mes_actual)
        self._menu_mes.grid(row=0, column=3, sticky="ew", pady=8)

        self._label_ayuda = ctk.CTkLabel(
            panel,
            text="",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
            wraplength=520,
            justify="left",
        )
        self._label_ayuda.grid(row=3, column=0, padx=28, pady=(4, 20), sticky="w")

        botones = ctk.CTkFrame(panel, fg_color="transparent")
        botones.grid(row=4, column=0, padx=28, pady=(0, 28), sticky="ew")
        botones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            botones,
            text="Exportar PDF",
            height=44,
            font=fuente_boton(),
            fg_color=PALETA["boton_primario"],
            hover_color=PALETA["boton_primario_hover"],
            text_color="#ffffff",
            command=self._exportar_pdf,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            botones,
            text="Exportar Excel",
            height=44,
            font=fuente_boton(),
            fg_color=PALETA["boton_accion"],
            hover_color=PALETA["boton_accion_hover"],
            text_color=PALETA["texto"],
            border_width=1,
            border_color=PALETA["boton_accion_borde"],
            command=self._exportar_excel,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self._al_cambiar_tipo(self._menu_tipo.get())

    def _al_cambiar_tipo(self, tipo: str) -> None:
        """Muestra u oculta selectores según el tipo de reporte."""
        es_diario = tipo == "Diario"
        if es_diario:
            self._marco_diario.grid()
            self._marco_mensual.grid_remove()
            self._label_ayuda.configure(
                text=(
                    "Consolida las ventas pagadas del día seleccionado y registra "
                    "el cierre diario si aún no existe. Al exportar podrá elegir "
                    "dónde guardar el archivo en su equipo."
                ),
            )
        else:
            self._marco_diario.grid_remove()
            self._marco_mensual.grid()
            self._label_ayuda.configure(
                text=(
                    "Consolida las ventas del mes e incluye los cierres diarios "
                    "registrados. Solo disponible para administrador. Al exportar "
                    "podrá elegir dónde guardar el archivo en su equipo."
                ),
            )

    def _es_diario(self) -> bool:
        """Retorna True si el tipo seleccionado es diario."""
        return self._menu_tipo.get() == "Diario"

    def _obtener_reporte(self) -> dict:
        """Obtiene el consolidado según los parámetros del formulario."""
        if self._es_diario():
            fecha = self._entrada_fecha.get().strip()
            return reporte_service.reporte_diario(fecha)

        anio_texto = self._entrada_anio.get().strip()
        try:
            anio = int(anio_texto)
        except ValueError:
            raise ValueError("El año debe ser un número entero válido.")
        mes = _mes_desde_etiqueta(self._menu_mes.get())
        return reporte_service.reporte_mensual(anio, mes)

    def _nombre_sugerido(self, extension: str) -> str:
        """Retorna el nombre de archivo sugerido según el tipo de reporte."""
        extension = extension.lstrip(".")
        if self._es_diario():
            fecha = self._entrada_fecha.get().strip()
            return f"reporte_diario_{fecha}.{extension}"
        anio = self._entrada_anio.get().strip()
        mes = _mes_desde_etiqueta(self._menu_mes.get())
        return f"reporte_mensual_{anio}-{mes:02d}.{extension}"

    def _directorio_inicial_dialogo(self) -> str:
        """Retorna la carpeta inicial para el diálogo Guardar como."""
        if self._ultimo_directorio is not None and self._ultimo_directorio.is_dir():
            return str(self._ultimo_directorio)
        RUTA_EXPORTACION.mkdir(parents=True, exist_ok=True)
        return str(RUTA_EXPORTACION)

    def _solicitar_ruta_guardado(self, extension: str) -> Optional[Path]:
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
            initialfile=self._nombre_sugerido(extension),
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

    def _mensaje_exito(self, formato: str, ruta) -> None:
        """Confirma visualmente la exportación exitosa."""
        if self._es_diario():
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

    def _exportar_pdf(self) -> None:
        """Genera y guarda el reporte en PDF."""
        try:
            reporte = self._obtener_reporte()
            ruta_destino = self._solicitar_ruta_guardado("pdf")
            if ruta_destino is None:
                return
            if self._es_diario():
                ruta = exportar_pdf.exportar_reporte_diario_pdf(
                    reporte, ruta_destino=ruta_destino
                )
            else:
                ruta = exportar_pdf.exportar_reporte_mensual_pdf(
                    reporte, ruta_destino=ruta_destino
                )
        except (ValueError, ErrorAcceso) as error:
            self._manejar_error(error)
            return
        except Exception as error:
            messagebox.showerror(
                "Error de exportación",
                f"No se pudo generar el PDF:\n{error}",
                parent=self.winfo_toplevel(),
            )
            return

        self._mensaje_exito("PDF", ruta)

    def _exportar_excel(self) -> None:
        """Genera y guarda el reporte en Excel."""
        try:
            reporte = self._obtener_reporte()
            ruta_destino = self._solicitar_ruta_guardado("xlsx")
            if ruta_destino is None:
                return
            if self._es_diario():
                ruta = exportar_excel.exportar_reporte_diario_excel(
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
                f"No se pudo generar el Excel:\n{error}",
                parent=self.winfo_toplevel(),
            )
            return

        self._mensaje_exito("Excel", ruta)


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
