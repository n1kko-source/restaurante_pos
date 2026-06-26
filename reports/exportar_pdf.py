"""Exportación de reportes a PDF con ReportLab."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import RESTAURANTE, RUTA_EXPORTACION

_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"$ {monto:,.0f}".replace(",", ".")


def _logo_texto() -> str:
    """Genera un logo textual a partir del nombre del restaurante."""
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
    canvas.setFillColor(colors.grey)
    texto = (
        f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} — "
        "Sistema POS Restaurante Hogareños"
    )
    canvas.drawCentredString(letter[0] / 2, 0.45 * inch, texto)
    canvas.restoreState()


def _estilos():
    """Retorna estilos de párrafo reutilizables."""
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "TituloReporte",
            parent=base["Heading1"],
            fontSize=16,
            spaceAfter=6,
            textColor=colors.HexColor("#1a73e8"),
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloReporte",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#5f6368"),
            spaceAfter=12,
        ),
        "logo": ParagraphStyle(
            "LogoTexto",
            parent=base["Heading1"],
            fontSize=28,
            alignment=1,
            textColor=colors.HexColor("#1a73e8"),
            spaceAfter=4,
        ),
        "nombre": ParagraphStyle(
            "NombreRestaurante",
            parent=base["Heading2"],
            fontSize=14,
            alignment=1,
            spaceAfter=2,
        ),
        "direccion": ParagraphStyle(
            "DireccionRestaurante",
            parent=base["Normal"],
            fontSize=10,
            alignment=1,
            textColor=colors.HexColor("#5f6368"),
            spaceAfter=16,
        ),
        "resumen": ParagraphStyle(
            "ResumenReporte",
            parent=base["Normal"],
            fontSize=11,
            spaceAfter=8,
        ),
    }


def _tabla_estilo(encabezado: bool = True) -> TableStyle:
    """Estilo común para tablas de ventas."""
    comando = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dadce0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if encabezado:
        comando.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
        ])
    return TableStyle(comando)


def _construir_encabezado(est) -> List:
    """Arma bloques de encabezado compartidos (logo texto + datos restaurante)."""
    return [
        Paragraph(_logo_texto(), est["logo"]),
        Paragraph(RESTAURANTE["nombre"], est["nombre"]),
        Paragraph(RESTAURANTE["direccion"], est["direccion"]),
    ]


def exportar_reporte_diario_pdf(
    reporte: Dict[str, Any],
    ruta_destino: Optional[Path] = None,
) -> Path:
    """
    Genera un PDF del reporte diario con tabla de ventas por producto y totales.
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

    filas_tabla = [["Producto", "Cantidad", "Subtotal (COP)"]]
    for item in reporte.get("ventas_por_producto", []):
        filas_tabla.append([
            item["nombre_producto"],
            str(item["cantidad"]),
            _formatear_pesos(item["subtotal"]),
        ])
    if len(filas_tabla) == 1:
        filas_tabla.append(["Sin ventas registradas", "0", _formatear_pesos(0)])

    tabla = Table(filas_tabla, colWidths=[3.2 * inch, 1.2 * inch, 1.6 * inch])
    tabla.setStyle(_tabla_estilo())
    elementos.append(tabla)
    elementos.append(Spacer(1, 16))

    elementos.append(Paragraph(
        f"<b>Total ventas:</b> {_formatear_pesos(reporte['total_ventas'])}",
        est["resumen"],
    ))
    elementos.append(Paragraph(
        f"<b>Número de facturas:</b> {reporte['numero_facturas']}",
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
