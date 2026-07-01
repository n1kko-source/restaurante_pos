"""Configuración del sistema: fecha, hora, impresora y plantilla de factura."""

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from services import hora_service, impresora_service, plantilla_factura_service
from services.auth_service import ErrorAcceso, requiere_rol
from ui.tema import (
    PALETA,
    PADDING_PANEL_H,
    PADDING_PANEL_INFERIOR,
    DesplegableProfesional,
    crear_imagen_asset,
    fuente_boton,
    fuente_normal,
    fuente_pequena,
    fuente_subtitulo,
    fuente_titulo,
    kwargs_boton_primario,
    kwargs_boton_secundario,
)


class VentanaConfiguracion(ctk.CTkFrame):
    """Módulo de configuración de fecha, hora e impresora del sistema."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=PALETA["fondo"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._id_reloj = None
        self._id_debounce_preview = None
        self._imagen_logo_preview = None
        self._imagen_logo_recibo_preview = None
        self._texto_preview_cache = ""
        self._logo_preview_cache = None
        self._preview_ancho_cache = None
        self._logo_recibo_colocado = False
        self._construir_panel()
        self._actualizar_reloj()

    def _construir_panel(self) -> None:
        """Construye la tarjeta de configuración del sistema."""
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETA["tarjeta"],
            corner_radius=16,
            border_width=1,
            border_color=PALETA["borde"],
        )
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Configuración del sistema",
            font=fuente_titulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=24, pady=(24, 12), sticky="w")

        scroll = ctk.CTkScrollableFrame(
            panel,
            fg_color="transparent",
            scrollbar_button_color=PALETA["borde"],
            scrollbar_button_hover_color=PALETA["acento"],
        )
        scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        self._construir_seccion_hora(scroll)
        self._construir_separador(scroll, fila=10)
        self._construir_seccion_impresora(scroll, fila_inicio=11)
        self._construir_separador(scroll, fila=15)
        self._construir_seccion_plantilla(scroll, fila_inicio=16)

    def _construir_seccion_hora(self, contenedor: ctk.CTkScrollableFrame) -> None:
        """Apartado de fecha y hora del equipo."""
        ctk.CTkLabel(
            contenedor,
            text="Fecha y hora del equipo",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=0, column=0, padx=16, pady=(8, 16), sticky="w")

        marco_reloj = ctk.CTkFrame(
            contenedor,
            fg_color=PALETA["fondo"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco_reloj.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")

        self._label_reloj = ctk.CTkLabel(
            marco_reloj,
            text="",
            font=fuente_normal(),
            text_color=PALETA["acento"],
            wraplength=520,
            justify="center",
        )
        self._label_reloj.pack(padx=24, pady=20)

        ctk.CTkLabel(
            contenedor,
            text=(
                "El sistema funciona 100% offline y usa el reloj interno de Windows "
                "(batería CMOS del equipo).\n\n"
                "Todas las facturas, pedidos y reportes registran la fecha y hora "
                "detectada en el momento de la operación.\n\n"
                "Si nota desincronización, abra el panel de fecha y hora de Windows "
                "para corregirla. Los cambios aplican a todo el sistema operativo."
            ),
            font=fuente_normal(),
            text_color=PALETA["texto_suave"],
            justify="left",
            wraplength=560,
        ).grid(row=2, column=0, padx=16, pady=(0, 20), sticky="w")

        acciones_hora = ctk.CTkFrame(contenedor, fg_color="transparent")
        acciones_hora.grid(row=3, column=0, padx=PADDING_PANEL_H, pady=(0, 8), sticky="ew")
        acciones_hora.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            acciones_hora,
            text="Abrir ajuste de fecha y hora de Windows",
            height=44,
            font=fuente_boton(),
            command=self._abrir_ajuste_windows,
            **kwargs_boton_primario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            acciones_hora,
            text="Actualizar reloj",
            height=44,
            font=fuente_normal(),
            command=self._actualizar_reloj_manual,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _construir_seccion_impresora(
        self,
        contenedor: ctk.CTkScrollableFrame,
        fila_inicio: int,
    ) -> None:
        """Apartado de selección de impresora térmica Colpos."""
        config = impresora_service.obtener_config_impresora()
        puertos = impresora_service.opciones_puerto_com()
        baudrates = impresora_service.baudrates_disponibles()
        anchos = impresora_service.anchos_papel_disponibles()
        dispositivos_usb = impresora_service.opciones_dispositivos_usb()

        if not puertos:
            puertos = [str(config.get("puerto", "COM3"))]

        etiquetas_usb = [d["etiqueta"] for d in dispositivos_usb]
        if not etiquetas_usb:
            etiquetas_usb = ["Sin dispositivos USB detectados"]

        self._mapa_usb = {d["etiqueta"]: d for d in dispositivos_usb}

        ctk.CTkLabel(
            contenedor,
            text="Impresora térmica",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=fila_inicio, column=0, padx=16, pady=(8, 16), sticky="w")

        ctk.CTkLabel(
            contenedor,
            text=(
                "Configure cómo se conecta la impresora Colpos al equipo.\n\n"
                "• Puerto COM: la más habitual (USB que Windows muestra como COM).\n"
                "• USB directo: conexión nativa por cable USB (requiere driver WinUSB).\n\n"
                "Use «Detectar» tras conectar el cable. Guarde antes de imprimir facturas."
            ),
            font=fuente_normal(),
            text_color=PALETA["texto_suave"],
            justify="left",
            wraplength=560,
        ).grid(row=fila_inicio + 1, column=0, padx=16, pady=(0, 16), sticky="w")

        marco_campos = ctk.CTkFrame(
            contenedor,
            fg_color=PALETA["fondo"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco_campos.grid(
            row=fila_inicio + 2,
            column=0,
            padx=16,
            pady=(0, 16),
            sticky="ew",
        )
        marco_campos.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            marco_campos,
            text="Tipo de conexión",
            font=fuente_normal(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        self._menu_tipo = DesplegableProfesional(
            marco_campos,
            height=38,
            values=impresora_service.tipos_conexion_ui(),
            font=fuente_normal(),
            command=self._alternar_tipo_conexion,
        )
        self._menu_tipo.grid(row=0, column=1, padx=20, pady=(16, 4), sticky="ew")

        ctk.CTkLabel(
            marco_campos,
            text="Ancho de papel (caracteres)",
            font=fuente_normal(),
            text_color=PALETA["texto"],
        ).grid(row=1, column=0, padx=20, pady=(8, 4), sticky="w")

        self._menu_ancho = DesplegableProfesional(
            marco_campos,
            height=38,
            values=[str(valor) for valor in anchos],
            font=fuente_normal(),
        )
        self._menu_ancho.grid(row=1, column=1, padx=20, pady=(8, 4), sticky="ew")

        self._marco_serial = ctk.CTkFrame(marco_campos, fg_color="transparent")
        self._marco_serial.grid(row=2, column=0, columnspan=2, sticky="ew")
        self._marco_serial.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._marco_serial,
            text="Puerto COM",
            font=fuente_normal(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(8, 4), sticky="w")

        self._menu_puerto = DesplegableProfesional(
            self._marco_serial,
            height=38,
            values=puertos,
            font=fuente_normal(),
        )
        self._menu_puerto.grid(row=0, column=1, padx=20, pady=(8, 4), sticky="ew")

        ctk.CTkLabel(
            self._marco_serial,
            text="Velocidad (baudrate)",
            font=fuente_normal(),
            text_color=PALETA["texto"],
        ).grid(row=1, column=0, padx=20, pady=(8, 16), sticky="w")

        self._menu_baudrate = DesplegableProfesional(
            self._marco_serial,
            height=38,
            values=[str(valor) for valor in baudrates],
            font=fuente_normal(),
        )
        self._menu_baudrate.grid(row=1, column=1, padx=20, pady=(8, 16), sticky="ew")

        self._marco_usb = ctk.CTkFrame(marco_campos, fg_color="transparent")
        self._marco_usb.grid(row=3, column=0, columnspan=2, sticky="ew")
        self._marco_usb.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self._marco_usb,
            text="Dispositivo USB",
            font=fuente_normal(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=20, pady=(8, 16), sticky="w")

        self._menu_usb = DesplegableProfesional(
            self._marco_usb,
            height=38,
            values=etiquetas_usb,
            font=fuente_normal(),
        )
        self._menu_usb.grid(row=0, column=1, padx=20, pady=(8, 16), sticky="ew")

        tipo_actual = str(config.get("tipo", "serial")).lower()
        self._menu_tipo.set(impresora_service.etiqueta_tipo_conexion(tipo_actual))

        ancho_actual = str(config.get("ancho_papel", 40))
        valores_ancho = self._menu_ancho.cget("values")
        self._menu_ancho.set(ancho_actual if ancho_actual in valores_ancho else str(anchos[0]))

        puerto_actual = str(config.get("puerto", puertos[0]))
        self._menu_puerto.set(
            puerto_actual if puerto_actual in puertos else puertos[0]
        )

        baudrate_actual = str(config.get("baudrate", 9600))
        valores_baud = self._menu_baudrate.cget("values")
        self._menu_baudrate.set(
            baudrate_actual if baudrate_actual in valores_baud else str(baudrates[0])
        )

        if dispositivos_usb:
            clave_usb = f"{int(config.get('vendor_id', 0)):04X}:{int(config.get('product_id', 0)):04X}"
            seleccion_usb = dispositivos_usb[0]["etiqueta"]
            for dispositivo in dispositivos_usb:
                if dispositivo["clave"] == clave_usb:
                    seleccion_usb = dispositivo["etiqueta"]
                    break
            self._menu_usb.set(seleccion_usb)
        else:
            self._menu_usb.set(etiquetas_usb[0])

        self._alternar_tipo_conexion(self._menu_tipo.get())

        acciones_impresora = ctk.CTkFrame(contenedor, fg_color="transparent")
        acciones_impresora.grid(
            row=fila_inicio + 3,
            column=0,
            padx=PADDING_PANEL_H,
            pady=(4, PADDING_PANEL_INFERIOR),
            sticky="ew",
        )
        acciones_impresora.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(
            acciones_impresora,
            text="Detectar",
            height=44,
            font=fuente_normal(),
            command=self._detectar_impresora,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            acciones_impresora,
            text="Probar conexión",
            height=44,
            font=fuente_normal(),
            command=self._probar_impresora,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            acciones_impresora,
            text="Guardar impresora",
            height=44,
            font=fuente_boton(),
            command=self._guardar_impresora,
            **kwargs_boton_primario(),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _construir_seccion_plantilla(
        self,
        contenedor: ctk.CTkScrollableFrame,
        fila_inicio: int,
    ) -> None:
        """Apartado para personalizar el encabezado del recibo térmico."""
        plantilla = plantilla_factura_service.obtener_config_plantilla()

        ctk.CTkLabel(
            contenedor,
            text="Plantilla de factura (impresión)",
            font=fuente_subtitulo(),
            text_color=PALETA["texto_suave"],
        ).grid(row=fila_inicio, column=0, padx=16, pady=(8, 16), sticky="w")

        ctk.CTkLabel(
            contenedor,
            text=(
                "Personalice el encabezado del recibo térmico Colpos según los datos "
                "del documento de venta.\n\n"
                "Los campos en blanco no se imprimen. A la derecha verá una vista previa "
                "en vivo con ítems de demostración."
            ),
            font=fuente_normal(),
            text_color=PALETA["texto_suave"],
            justify="left",
            wraplength=720,
        ).grid(row=fila_inicio + 1, column=0, padx=16, pady=(0, 16), sticky="w")

        marco_dos_columnas = ctk.CTkFrame(contenedor, fg_color="transparent")
        marco_dos_columnas.grid(
            row=fila_inicio + 2, column=0, padx=8, pady=(0, 16), sticky="nsew"
        )
        marco_dos_columnas.grid_columnconfigure(0, weight=3)
        marco_dos_columnas.grid_columnconfigure(1, weight=2)

        columna_formulario = ctk.CTkFrame(marco_dos_columnas, fg_color="transparent")
        columna_formulario.grid(row=0, column=0, sticky="nsew", padx=(8, 8))
        columna_formulario.grid_columnconfigure(0, weight=1)

        marco_logo = ctk.CTkFrame(
            columna_formulario,
            fg_color=PALETA["fondo"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco_logo.grid(row=0, column=0, padx=8, pady=(0, 16), sticky="ew")

        self._label_logo_preview = ctk.CTkLabel(
            marco_logo,
            text="Sin logotipo",
            width=120,
            height=120,
            fg_color=PALETA["tarjeta"],
            corner_radius=8,
            text_color=PALETA["texto_suave"],
        )
        self._label_logo_preview.pack(side="left", padx=20, pady=16)

        acciones_logo = ctk.CTkFrame(marco_logo, fg_color="transparent")
        acciones_logo.pack(side="left", fill="both", expand=True, padx=(0, 20), pady=16)
        acciones_logo.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            acciones_logo,
            text="Seleccionar logotipo PNG…",
            height=40,
            font=fuente_normal(),
            command=self._seleccionar_logo_factura,
            **kwargs_boton_secundario(),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkButton(
            acciones_logo,
            text="Restaurar logo por defecto",
            height=40,
            font=fuente_normal(),
            command=self._restaurar_logo_factura,
            **kwargs_boton_secundario(),
        ).grid(row=1, column=0, sticky="ew")

        marco_campos = ctk.CTkFrame(
            columna_formulario,
            fg_color=PALETA["fondo"],
            corner_radius=12,
            border_width=1,
            border_color=PALETA["borde"],
        )
        marco_campos.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")
        marco_campos.grid_columnconfigure(1, weight=1)

        campos = (
            ("Identificación del documento", "titulo_documento", plantilla.get("titulo_documento", "")),
            ("Razón social del vendedor", "razon_social", plantilla.get("razon_social", "")),
            ("NIT del vendedor", "nit", plantilla.get("nit", "")),
            ("Dirección del establecimiento", "direccion", plantilla.get("direccion", "")),
            ("Régimen tributario", "regimen_tributario", plantilla.get("regimen_tributario", "")),
        )
        self._entradas_plantilla = {}
        for fila, (etiqueta, clave, valor) in enumerate(campos):
            ctk.CTkLabel(
                marco_campos,
                text=etiqueta,
                font=fuente_pequena(),
                text_color=PALETA["texto_suave"],
            ).grid(row=fila, column=0, padx=20, pady=(14 if fila == 0 else 6, 4), sticky="nw")
            entrada = ctk.CTkEntry(
                marco_campos,
                height=38,
                font=fuente_normal(),
                fg_color=PALETA["entrada_fondo"],
                border_color=PALETA["borde"],
                text_color=PALETA["texto"],
                placeholder_text="Opcional — dejar en blanco para no imprimir",
            )
            entrada.insert(0, valor or "")
            entrada.grid(
                row=fila,
                column=1,
                padx=20,
                pady=(14 if fila == 0 else 6, 4),
                sticky="ew",
            )
            entrada.bind("<KeyRelease>", self._al_cambiar_campo_plantilla)
            self._entradas_plantilla[clave] = entrada

        ctk.CTkFrame(marco_campos, height=8, fg_color="transparent").grid(
            row=len(campos), column=0, columnspan=2
        )

        columna_preview = ctk.CTkFrame(marco_dos_columnas, fg_color="transparent")
        columna_preview.grid(row=0, column=1, sticky="nsew", padx=(8, 8))
        columna_preview.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            columna_preview,
            text="Vista previa del recibo",
            font=fuente_subtitulo(),
            text_color=PALETA["texto"],
        ).grid(row=0, column=0, padx=4, pady=(0, 0), sticky="w")

        ctk.CTkLabel(
            columna_preview,
            text="Demostración con mesa 6 e ítems de ejemplo",
            font=fuente_pequena(),
            text_color=PALETA["texto_suave"],
        ).grid(row=1, column=0, padx=4, pady=(2, 4), sticky="w")

        marco_ticket = ctk.CTkFrame(
            columna_preview,
            fg_color="#ffffff",
            corner_radius=10,
            border_width=2,
            border_color=PALETA["borde"],
        )
        marco_ticket.grid(row=2, column=0, sticky="nsew", padx=4, pady=(8, 0))
        marco_ticket.grid_columnconfigure(0, weight=1)
        marco_ticket.grid_columnconfigure(1, weight=0)
        marco_ticket.grid_columnconfigure(2, weight=1)

        self._ancho_columna_recibo = 280
        self._marco_columna_recibo = ctk.CTkFrame(
            marco_ticket,
            fg_color="transparent",
            width=self._ancho_columna_recibo,
        )
        self._marco_columna_recibo.grid(
            row=0, column=1, rowspan=2, sticky="n", pady=(12, 14)
        )
        self._marco_columna_recibo.grid_propagate(False)

        self._marco_logo_recibo = ctk.CTkFrame(
            self._marco_columna_recibo,
            fg_color="transparent",
            height=76,
            width=self._ancho_columna_recibo,
        )
        self._marco_logo_recibo.pack(anchor="n")
        self._marco_logo_recibo.pack_propagate(False)

        self._label_logo_recibo_preview = ctk.CTkLabel(
            self._marco_logo_recibo,
            text="",
            fg_color="transparent",
        )

        fuente_recibo = ctk.CTkFont(family="Consolas", size=10)

        self._label_texto_recibo_preview = ctk.CTkLabel(
            self._marco_columna_recibo,
            text="",
            font=fuente_recibo,
            text_color=PALETA["texto"],
            fg_color="#ffffff",
            justify="left",
            anchor="nw",
            width=self._ancho_columna_recibo,
        )
        self._label_texto_recibo_preview.pack(anchor="n")

        acciones_plantilla = ctk.CTkFrame(contenedor, fg_color="transparent")
        acciones_plantilla.grid(
            row=fila_inicio + 3,
            column=0,
            padx=PADDING_PANEL_H,
            pady=(4, PADDING_PANEL_INFERIOR),
            sticky="ew",
        )
        acciones_plantilla.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            acciones_plantilla,
            text="Guardar plantilla",
            height=44,
            font=fuente_boton(),
            command=self._guardar_plantilla,
            **kwargs_boton_primario(),
        ).grid(row=0, column=0, sticky="ew")

        self._actualizar_vista_logo()

    def _al_cambiar_campo_plantilla(self, _evento=None) -> None:
        """Programa la actualización fluida de la demo al editar un campo."""
        self._programar_vista_previa_recibo()

    def _programar_vista_previa_recibo(self, demora_ms: int = 180) -> None:
        """Agrupa cambios rápidos para evitar parpadeo en la vista previa."""
        if self._id_debounce_preview is not None:
            self.after_cancel(self._id_debounce_preview)
        self._id_debounce_preview = self.after(
            demora_ms, self._ejecutar_vista_previa_recibo
        )

    def _ejecutar_vista_previa_recibo(self) -> None:
        """Ejecuta la actualización diferida de la demo del recibo."""
        self._id_debounce_preview = None
        self._actualizar_vista_previa_recibo()

    def _leer_campos_plantilla_ui(self) -> dict:
        """Lee los valores actuales del formulario de plantilla."""
        return {
            clave: entrada.get()
            for clave, entrada in self._entradas_plantilla.items()
        }

    def _ancho_px_columna_recibo(self, ancho_caracteres: int) -> int:
        """Calcula el ancho en píxeles de la columna según la fuente del recibo."""
        fuente = ctk.CTkFont(family="Consolas", size=10)
        try:
            muestra = "0" * max(1, ancho_caracteres)
            return max(200, int(fuente.measure(muestra)) + 6)
        except Exception:
            return max(200, ancho_caracteres * 7)

    def _actualizar_logo_en_preview(self, ruta_logo) -> None:
        """Actualiza el logotipo de la demo solo cuando cambia el archivo."""
        clave_logo = str(ruta_logo) if ruta_logo is not None else ""
        if clave_logo == self._logo_preview_cache and self._logo_recibo_colocado:
            return

        self._logo_preview_cache = clave_logo
        if ruta_logo is not None:
            imagen = crear_imagen_asset(ruta_logo, 64, 64)
            if imagen is not None:
                self._imagen_logo_recibo_preview = imagen
                self._label_logo_recibo_preview.configure(image=imagen, text="")
                if not self._logo_recibo_colocado:
                    self._label_logo_recibo_preview.place(
                        relx=0.5, rely=0.5, anchor="center"
                    )
                    self._logo_recibo_colocado = True
                return

        self._label_logo_recibo_preview.place_forget()
        self._label_logo_recibo_preview.configure(image=None, text="")
        self._logo_recibo_colocado = False

    def _actualizar_vista_previa_recibo(self, forzar_logo: bool = False) -> None:
        """Refresca la simulación gráfica del recibo térmico."""
        if not hasattr(self, "_label_texto_recibo_preview"):
            return

        campos = self._leer_campos_plantilla_ui()
        vista = plantilla_factura_service.generar_vista_previa(
            titulo_documento=campos.get("titulo_documento", ""),
            razon_social=campos.get("razon_social", ""),
            nit=campos.get("nit", ""),
            direccion=campos.get("direccion", ""),
            regimen_tributario=campos.get("regimen_tributario", ""),
        )

        ancho_caracteres = int(vista.get("ancho_caracteres", 40))
        ancho_px = self._ancho_px_columna_recibo(ancho_caracteres)
        if forzar_logo or ancho_px != self._preview_ancho_cache:
            self._ancho_columna_recibo = ancho_px
            self._marco_columna_recibo.configure(width=ancho_px)
            self._marco_logo_recibo.configure(width=ancho_px)
            self._label_texto_recibo_preview.configure(width=ancho_px)
            self._preview_ancho_cache = ancho_px

        if forzar_logo:
            self._logo_preview_cache = None

        self._actualizar_logo_en_preview(vista.get("ruta_logo"))

        texto = "\n".join(vista.get("lineas", []))
        if texto == self._texto_preview_cache:
            return
        self._texto_preview_cache = texto
        self._label_texto_recibo_preview.configure(text=texto)

    def _actualizar_vista_logo(self) -> None:
        """Muestra la vista previa del logotipo configurado."""
        ruta = plantilla_factura_service.obtener_ruta_logo_efectiva()
        if ruta is None:
            self._label_logo_preview.configure(image=None, text="Sin logotipo")
            self._actualizar_vista_previa_recibo(forzar_logo=True)
            return
        imagen = crear_imagen_asset(ruta, 110, 110)
        if imagen is None:
            self._label_logo_preview.configure(image=None, text="Sin logotipo")
            self._actualizar_vista_previa_recibo(forzar_logo=True)
            return
        self._imagen_logo_preview = imagen
        self._label_logo_preview.configure(image=imagen, text="")
        self._actualizar_vista_previa_recibo(forzar_logo=True)

    def _seleccionar_logo_factura(self) -> None:
        """Abre el selector de archivo PNG para el logotipo del recibo."""
        ruta = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Seleccionar logotipo de factura",
            filetypes=[("Imagen PNG", "*.png")],
        )
        if not ruta:
            return
        try:
            plantilla_factura_service.importar_logo_factura(Path(ruta))
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            return
        except ValueError as error:
            messagebox.showerror("Plantilla", str(error))
            return
        self._actualizar_vista_logo()
        messagebox.showinfo("Plantilla", "Logotipo actualizado correctamente.")

    def _restaurar_logo_factura(self) -> None:
        """Vuelve al logo Hogareños por defecto."""
        try:
            plantilla_factura_service.restaurar_logo_por_defecto()
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            return
        self._actualizar_vista_logo()
        messagebox.showinfo("Plantilla", "Se restauró el logo por defecto del sistema.")

    def _guardar_plantilla(self) -> None:
        """Persiste los textos de la plantilla de factura."""
        try:
            plantilla_factura_service.guardar_config_plantilla(
                titulo_documento=self._entradas_plantilla["titulo_documento"].get(),
                razon_social=self._entradas_plantilla["razon_social"].get(),
                nit=self._entradas_plantilla["nit"].get(),
                direccion=self._entradas_plantilla["direccion"].get(),
                regimen_tributario=self._entradas_plantilla["regimen_tributario"].get(),
            )
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            return
        except ValueError as error:
            messagebox.showerror("Plantilla", str(error))
            return
        messagebox.showinfo("Plantilla", "Plantilla de factura guardada correctamente.")
        self._actualizar_vista_previa_recibo()

    def _alternar_tipo_conexion(self, _etiqueta=None) -> None:
        """Muestra los campos de COM o USB según el tipo elegido."""
        tipo = impresora_service.tipo_desde_etiqueta(self._menu_tipo.get())
        es_serial = tipo == "serial"

        if es_serial:
            self._marco_serial.grid()
            self._marco_usb.grid_remove()
        else:
            self._marco_serial.grid_remove()
            self._marco_usb.grid()

    def _construir_separador(self, contenedor: ctk.CTkScrollableFrame, fila: int) -> None:
        """Línea divisoria entre secciones de configuración."""
        ctk.CTkFrame(
            contenedor,
            height=1,
            fg_color=PALETA["borde"],
        ).grid(row=fila, column=0, padx=16, pady=20, sticky="ew")

    def _detectar_impresora(self) -> None:
        """Refresca puertos COM o dispositivos USB según el tipo de conexión."""
        tipo = impresora_service.tipo_desde_etiqueta(self._menu_tipo.get())
        if tipo == "serial":
            self._detectar_puertos_com()
        else:
            self._detectar_dispositivos_usb()

    def _detectar_puertos_com(self) -> None:
        """Refresca la lista de puertos COM detectados en Windows."""
        seleccion_previa = self._menu_puerto.get()
        puertos = impresora_service.opciones_puerto_com()
        if not puertos:
            messagebox.showwarning(
                "Impresora",
                "No se detectaron puertos COM. Verifique que la impresora "
                "esté conectada y encendida.",
            )
            return

        self._menu_puerto.configure(values=puertos)
        if seleccion_previa in puertos:
            self._menu_puerto.set(seleccion_previa)
        else:
            self._menu_puerto.set(puertos[0])

        messagebox.showinfo(
            "Impresora",
            f"Se detectaron {len(puertos)} puerto(s) COM: {', '.join(puertos)}",
        )

    def _detectar_dispositivos_usb(self) -> None:
        """Refresca la lista de dispositivos USB conectados."""
        seleccion_previa = self._menu_usb.get()
        dispositivos = impresora_service.opciones_dispositivos_usb()
        if not dispositivos:
            messagebox.showwarning(
                "Impresora",
                "No se detectaron dispositivos USB. Verifique el cable y que "
                "el driver WinUSB/libusb esté instalado si usa USB directo.",
            )
            return

        etiquetas = [d["etiqueta"] for d in dispositivos]
        self._mapa_usb = {d["etiqueta"]: d for d in dispositivos}
        self._menu_usb.configure(values=etiquetas)
        if seleccion_previa in etiquetas:
            self._menu_usb.set(seleccion_previa)
        else:
            self._menu_usb.set(etiquetas[0])

        messagebox.showinfo(
            "Impresora",
            f"Se detectaron {len(dispositivos)} dispositivo(s) USB.",
        )

    def _obtener_parametros_impresora(self):
        """Lee los valores actuales del formulario de impresora."""
        tipo = impresora_service.tipo_desde_etiqueta(self._menu_tipo.get())
        ancho = int(self._menu_ancho.get())
        if tipo == "serial":
            return {
                "tipo": tipo,
                "ancho_papel": ancho,
                "puerto": self._menu_puerto.get(),
                "baudrate": int(self._menu_baudrate.get()),
                "vendor_id": None,
                "product_id": None,
            }

        etiqueta = self._menu_usb.get()
        dispositivo = self._mapa_usb.get(etiqueta)
        if not dispositivo:
            raise ValueError(
                "Seleccione un dispositivo USB válido de la lista."
            )
        return {
            "tipo": tipo,
            "ancho_papel": ancho,
            "puerto": None,
            "baudrate": None,
            "vendor_id": dispositivo["vendor_id"],
            "product_id": dispositivo["product_id"],
        }

    def _guardar_impresora(self) -> None:
        """Persiste la configuración de impresora seleccionada."""
        try:
            params = self._obtener_parametros_impresora()
            impresora_service.guardar_config_impresora(**params)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            return
        except ValueError as error:
            messagebox.showerror("Impresora", str(error))
            return

        if params["tipo"] == "serial":
            detalle = f"{params['puerto']} a {params['baudrate']} bps"
        else:
            detalle = (
                f"USB VID {params['vendor_id']:04X} / PID {params['product_id']:04X}"
            )
        messagebox.showinfo(
            "Impresora",
            f"Configuración guardada ({impresora_service.etiqueta_tipo_conexion(params['tipo'])}): "
            f"{detalle}. Ancho: {params['ancho_papel']} caracteres.",
        )

    def _probar_impresora(self) -> None:
        """Intenta conectar con la impresora usando la selección actual."""
        try:
            params = self._obtener_parametros_impresora()
            exito, mensaje = impresora_service.probar_conexion(**params)
        except ErrorAcceso as error:
            messagebox.showerror("Acceso denegado", str(error))
            return
        except ValueError as error:
            messagebox.showerror("Impresora", str(error))
            return

        if exito:
            messagebox.showinfo("Impresora", mensaje)
        else:
            messagebox.showerror("Impresora", mensaje)

    def _actualizar_reloj(self) -> None:
        """Actualiza la etiqueta de reloj cada segundo."""
        try:
            texto = hora_service.formatear_legible(hora_service.obtener_datetime_actual())
        except ValueError as error:
            texto = f"Hora del sistema inválida: {error}"
        self._label_reloj.configure(text=texto)
        self._id_reloj = self.after(1000, self._actualizar_reloj)

    def _actualizar_reloj_manual(self) -> None:
        """Fuerza una actualización inmediata del reloj en pantalla."""
        if self._id_reloj is not None:
            self.after_cancel(self._id_reloj)
            self._id_reloj = None
        self._actualizar_reloj()

    def _abrir_ajuste_windows(self) -> None:
        """Abre el panel nativo de fecha y hora de Windows."""
        try:
            hora_service.abrir_ajuste_hora_windows()
        except OSError as error:
            messagebox.showerror("Configuración", str(error))

    def destroy(self) -> None:
        """Cancela temporizadores al destruir el módulo."""
        if self._id_reloj is not None:
            self.after_cancel(self._id_reloj)
            self._id_reloj = None
        if self._id_debounce_preview is not None:
            self.after_cancel(self._id_debounce_preview)
            self._id_debounce_preview = None
        super().destroy()


@requiere_rol("administrador")
def mostrar_en(contenedor) -> VentanaConfiguracion:
    """
    Incrusta el módulo de configuración en el frame contenedor.
    Primera línea de defensa: decorador @requiere_rol.
    """
    ventana = VentanaConfiguracion(contenedor)
    ventana.grid(row=0, column=0, sticky="nsew")
    contenedor.grid_columnconfigure(0, weight=1)
    contenedor.grid_rowconfigure(0, weight=1)
    return ventana
