"""Exportación de reportes a PDF con ReportLab."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import ETIQUETAS_METODO_PAGO, MARCA_COLORES, RESTAURANTE, RUTA_EXPORTACION, RUTA_LOGO_PNG
from reports.utilidades_reporte import (
    ENCABEZADOS_DETALLE_DIARIO,
    agrupar_detalle_por_factura,
    etiqueta_metodo_pago,
    numero_factura_corto,
    texto_comprador,
)

_ANCHOS_COL_DIARIO = [
    0.42 * inch, 0.82 * inch, 1.15 * inch, 2.35 * inch, 0.48 * inch, 0.98 * inch,
]
_SEPARACION_BLOQUES_FACTURA_PDF = 10

_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_COLOR_NARANJA = colors.HexColor(MARCA_COLORES["naranja"])
_COLOR_NARANJA_OSCURO = colors.HexColor(MARCA_COLORES["naranja_oscuro"])
_COLOR_FONDO_TABLA = colors.HexColor(MARCA_COLORES["fondo_tabla"])
_COLOR_TEXTO = colors.HexColor(MARCA_COLORES["texto"])
_COLOR_TEXTO_SUAVE = colors.HexColor(MARCA_COLORES["texto_suave"])
_COLOR_BORDE = colors.HexColor(MARCA_COLORES["borde"])


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"$ {monto:,.0f}".replace(",", ".")


def _logo_texto_respaldo() -> str:
    """Iniciales de respaldo si no existe el archivo PNG del logo."""
    nombre = RESTAURANTE["nombre"].strip()
    palabras = [p for p in nombre.split() if p]
    if len(palabras) >= 2:
        return (palabras[0][0] + palabras[1][0]).upper()
    if palabras:
        return palabras[0][:2].upper()
    return "RH"


def _asegurar_directorio_destino(ruta: Path) -> None:
    """Crea el directorio padre del archivo de destino si no existe."""
    ruta.parent.mkdir(parents=True, exist_ok=True)


def _pie_pagina(canvas, doc) -> None:
    """Dibuja el pie de página en cada hoja del PDF."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_COLOR_TEXTO_SUAVE)
    texto = (
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — "
        "Sistema POS Restaurante Hogareños"
    )
    canvas.drawCentredString(letter[0] / 2, 0.45 * inch, texto)
    canvas.restoreState()


def _estilos():
    """Retorna estilos de párrafo con la identidad visual Hogareños."""
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "TituloReporte",
            parent=base["Heading1"],
            fontSize=16,
            spaceAfter=6,
            textColor=_COLOR_NARANJA_OSCURO,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloReporte",
            parent=base["Normal"],
            fontSize=11,
            textColor=_COLOR_TEXTO_SUAVE,
            spaceAfter=12,
        ),
        "logo": ParagraphStyle(
            "LogoTexto",
            parent=base["Heading1"],
            fontSize=28,
            alignment=1,
            textColor=_COLOR_NARANJA,
            spaceAfter=4,
        ),
        "nombre": ParagraphStyle(
            "NombreRestaurante",
            parent=base["Heading2"],
            fontSize=14,
            alignment=1,
            textColor=_COLOR_TEXTO,
            spaceAfter=2,
        ),
        "direccion": ParagraphStyle(
            "DireccionRestaurante",
            parent=base["Normal"],
            fontSize=10,
            alignment=1,
            textColor=_COLOR_TEXTO_SUAVE,
            spaceAfter=16,
        ),
        "resumen": ParagraphStyle(
            "ResumenReporte",
            parent=base["Normal"],
            fontSize=11,
            textColor=_COLOR_TEXTO,
            spaceAfter=8,
        ),
    }


def _tabla_estilo(encabezado: bool = True) -> TableStyle:
    """Estilo común para tablas de ventas con acentos naranja."""
    comando = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), _COLOR_TEXTO),
        ("GRID", (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if encabezado:
        comando.extend([
            ("BACKGROUND", (0, 0), (-1, 0), _COLOR_FONDO_TABLA),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), _COLOR_NARANJA_OSCURO),
        ])
    return TableStyle(comando)


def _tabla_estilo_compacta(encabezado: bool = False) -> TableStyle:
    """Estilo denso para tablas del detalle diario (encabezado o bloque de factura)."""
    comando = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), _COLOR_TEXTO),
        ("BOX", (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _COLOR_BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (4, 0), (4, -1), "CENTER"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
    ]
    if encabezado:
        comando.extend([
            ("BACKGROUND", (0, 0), (-1, 0), _COLOR_FONDO_TABLA),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), _COLOR_NARANJA_OSCURO),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
        ])
    return TableStyle(comando)


def _fila_detalle_pdf(item: Dict[str, Any]) -> List[str]:
    """Convierte un renglón de detalle en fila de tabla PDF."""
    return [
        numero_factura_corto(item["factura_numero"]),
        etiqueta_metodo_pago(item["metodo_pago"]),
        texto_comprador(item["comprador_nombre"]),
        item["nombre_producto"],
        str(item["cantidad"]),
        _formatear_pesos(item["subtotal"]),
    ]


def _construir_bloques_detalle_diario_pdf(detalle: List[Dict[str, Any]]) -> List:
    """
    Arma encabezado y bloques independientes por factura.
    El espacio entre bloques queda sin bordes (como cajas separadas).
    """
    bloques: List = []

    tabla_encabezado = Table(
        [list(ENCABEZADOS_DETALLE_DIARIO)],
        colWidths=_ANCHOS_COL_DIARIO,
    )
    tabla_encabezado.setStyle(_tabla_estilo_compacta(encabezado=True))
    bloques.append(tabla_encabezado)

    grupos = agrupar_detalle_por_factura(detalle)
    if not grupos:
        bloques.append(Spacer(1, _SEPARACION_BLOQUES_FACTURA_PDF))
        tabla_vacia = Table(
            [["Sin ventas registradas", "", "", "", "0", _formatear_pesos(0)]],
            colWidths=_ANCHOS_COL_DIARIO,
        )
        tabla_vacia.setStyle(_tabla_estilo_compacta())
        bloques.append(tabla_vacia)
        return bloques

    for grupo in grupos:
        bloques.append(Spacer(1, _SEPARACION_BLOQUES_FACTURA_PDF))
        tabla_grupo = Table(
            [_fila_detalle_pdf(item) for item in grupo],
            colWidths=_ANCHOS_COL_DIARIO,
        )
        tabla_grupo.setStyle(_tabla_estilo_compacta())
        bloques.append(tabla_grupo)

    return bloques


def _construir_encabezado(est) -> List:
    """Arma bloques de encabezado con logo PNG o respaldo textual."""
    elementos = []
    if RUTA_LOGO_PNG.is_file():
        logo = RLImage(str(RUTA_LOGO_PNG), width=0.85 * inch, height=0.85 * inch)
        logo.hAlign = "CENTER"
        elementos.append(logo)
        elementos.append(Spacer(1, 6))
    else:
        elementos.append(Paragraph(_logo_texto_respaldo(), est["logo"]))

    elementos.extend([
        Paragraph(RESTAURANTE["nombre"], est["nombre"]),
        Paragraph(RESTAURANTE["direccion"], est["direccion"]),
    ])
    return elementos


def _agregar_totales_reporte_diario(elementos, reporte: Dict[str, Any], est) -> None:
    """Añade bloque de totales generales y por método de pago al PDF diario."""
    totales_metodo = reporte.get("totales_por_metodo_pago", {})
    elementos.append(Spacer(1, 16))
    elementos.append(Paragraph(
        f"<b>Total:</b> {_formatear_pesos(reporte['total_ventas'])}",
        est["resumen"],
    ))
    for codigo in ("anotar", "nequi", "daviplata", "efectivo"):
        etiqueta = ETIQUETAS_METODO_PAGO.get(codigo, codigo)
        monto = int(totales_metodo.get(codigo, 0))
        elementos.append(Paragraph(
            f"<b>Total {etiqueta}:</b> {_formatear_pesos(monto)}",
            est["resumen"],
        ))
    elementos.append(Paragraph(
        f"<b>Número de facturas:</b> {reporte['numero_facturas']}",
        est["resumen"],
    ))


def exportar_reporte_diario_pdf(
    reporte: Dict[str, Any],
    ruta_destino: Optional[Path] = None,
) -> Path:
    """
    Genera un PDF del reporte diario con detalle por factura y totales por método.
    Retorna la ruta del archivo guardado.
    """
    fecha = reporte["fecha"]
    if ruta_destino is None:
        RUTA_EXPORTACION.mkdir(parents=True, exist_ok=True)
        ruta_destino = RUTA_EXPORTACION / f"reporte_diario_{fecha}.pdf"
    _asegurar_directorio_destino(ruta_destino)

    est = _estilos()
    elementos = _construir_encabezado(est)
    elementos.append(Paragraph("Reporte de ventas diario", est["titulo"]))
    elementos.append(Paragraph(f"Fecha: {fecha}", est["subtitulo"]))

    detalle = reporte.get("detalle_ventas", [])
    elementos.extend(_construir_bloques_detalle_diario_pdf(detalle))
    _agregar_totales_reporte_diario(elementos, reporte, est)

    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    return Path(ruta_destino)


def exportar_reporte_mensual_pdf(
    reporte: Dict[str, Any],
    ruta_destino: Optional[Path] = None,
) -> Path:
    """
    Genera un PDF del reporte mensual con cierres diarios y totales del mes.
    Retorna la ruta del archivo guardado.
    """
    anio = reporte["anio"]
    mes = reporte["mes"]
    etiqueta_mes = _MESES[mes - 1]
    if ruta_destino is None:
        RUTA_EXPORTACION.mkdir(parents=True, exist_ok=True)
        ruta_destino = RUTA_EXPORTACION / f"reporte_mensual_{anio}-{mes:02d}.pdf"
    _asegurar_directorio_destino(ruta_destino)

    est = _estilos()
    elementos = _construir_encabezado(est)
    elementos.append(Paragraph("Reporte de ventas mensual", est["titulo"]))
    elementos.append(Paragraph(
        f"Período: {etiqueta_mes} de {anio}",
        est["subtitulo"],
    ))

    filas_tabla = [["Fecha", "Total ventas (COP)", "Nº facturas"]]
    for cierre in reporte.get("cierres_diarios", []):
        filas_tabla.append([
            cierre["fecha"],
            _formatear_pesos(cierre["total_ventas"]),
            str(cierre["numero_facturas"]),
        ])
    if len(filas_tabla) == 1:
        filas_tabla.append(["Sin cierres registrados", _formatear_pesos(0), "0"])

    tabla = Table(filas_tabla, colWidths=[1.8 * inch, 2.2 * inch, 1.5 * inch])
    tabla.setStyle(_tabla_estilo())
    elementos.append(tabla)
    elementos.append(Spacer(1, 16))

    elementos.append(Paragraph(
        f"<b>Total ventas del mes:</b> {_formatear_pesos(reporte['total_ventas'])}",
        est["resumen"],
    ))
    elementos.append(Paragraph(
        f"<b>Total facturas del mes:</b> {reporte['numero_facturas']}",
        est["resumen"],
    ))

    doc = SimpleDocTemplate(
        str(ruta_destino),
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    return Path(ruta_destino)
