"""Exportación de reportes a Excel con openpyxl."""

from pathlib import Path
from typing import Any, Dict, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import RESTAURANTE, RUTA_EXPORTACION

_NOMBRE_HOJA = "Ventas"
_FILA_ENCABEZADO = 1
_FILL_ENCABEZADO = PatternFill("solid", fgColor="E8F0FE")
_FONT_ENCABEZADO = Font(bold=True, color="1A73E8")
_FONT_TITULO = Font(bold=True, size=14)


def _asegurar_directorio_destino(ruta: Path) -> None:
    """Crea el directorio padre del archivo de destino si no existe."""
    ruta.parent.mkdir(parents=True, exist_ok=True)


def _ajustar_ancho_columnas(hoja) -> None:
    """Ajusta el ancho de columnas según el contenido."""
    for columna in hoja.columns:
        maximo = 0
        letra = get_column_letter(columna[0].column)
        for celda in columna:
            if celda.value is not None:
                maximo = max(maximo, len(str(celda.value)))
        hoja.column_dimensions[letra].width = min(max(maximo + 2, 12), 40)


def _escribir_encabezado_hoja(hoja, titulo: str, subtitulo: str) -> int:
    """Escribe metadatos del reporte y retorna la fila donde empiezan los datos."""
    hoja["A1"] = RESTAURANTE["nombre"]
    hoja["A1"].font = _FONT_TITULO
    hoja["A2"] = RESTAURANTE["direccion"]
    hoja["A3"] = titulo
    hoja["A3"].font = Font(bold=True)
    hoja["A4"] = subtitulo
    return 6


def _aplicar_estilo_encabezado_tabla(hoja, fila: int, columnas: int) -> None:
    """Aplica estilo a la fila de encabezados de la tabla de datos."""
    for col in range(1, columnas + 1):
        celda = hoja.cell(row=fila, column=col)
        celda.font = _FONT_ENCABEZADO
        celda.fill = _FILL_ENCABEZADO
        celda.alignment = Alignment(horizontal="center")


def exportar_reporte_diario_excel(
    reporte: Dict[str, Any],
    ruta_destino: Optional[Path] = None,
) -> Path:
    """
    Genera un Excel del reporte diario en hoja Ventas con fila SUM() de subtotales.
    Retorna la ruta del archivo guardado.
    """
    fecha = reporte["fecha"]
    if ruta_destino is None:
        RUTA_EXPORTACION.mkdir(parents=True, exist_ok=True)
        ruta_destino = RUTA_EXPORTACION / f"reporte_diario_{fecha}.xlsx"
    _asegurar_directorio_destino(ruta_destino)

    libro = Workbook()
    hoja = libro.active
    hoja.title = _NOMBRE_HOJA

    fila_datos = _escribir_encabezado_hoja(
        hoja,
        "Reporte de ventas diario",
        f"Fecha: {fecha}",
    )

    encabezados = ["ID producto", "Producto", "Cantidad", "Subtotal (COP)"]
    for col, texto in enumerate(encabezados, start=1):
        hoja.cell(row=fila_datos, column=col, value=texto)
    _aplicar_estilo_encabezado_tabla(hoja, fila_datos, len(encabezados))

    fila_actual = fila_datos + 1
    ventas = reporte.get("ventas_por_producto", [])
    if ventas:
        for item in ventas:
            hoja.cell(row=fila_actual, column=1, value=item["producto_id"])
            hoja.cell(row=fila_actual, column=2, value=item["nombre_producto"])
            hoja.cell(row=fila_actual, column=3, value=item["cantidad"])
            hoja.cell(row=fila_actual, column=4, value=item["subtotal"])
            fila_actual += 1
    else:
        hoja.cell(row=fila_actual, column=2, value="Sin ventas registradas")
        fila_actual += 1

    fila_total = fila_actual
    hoja.cell(row=fila_total, column=3, value="TOTAL")
    hoja.cell(row=fila_total, column=3).font = Font(bold=True)
    col_subtotal = get_column_letter(4)
    primera_fila = fila_datos + 1
    ultima_fila = fila_actual - 1
    if ventas:
        hoja.cell(
            row=fila_total,
            column=4,
            value=f"=SUM({col_subtotal}{primera_fila}:{col_subtotal}{ultima_fila})",
        )
    else:
        hoja.cell(row=fila_total, column=4, value=0)
    hoja.cell(row=fila_total, column=4).font = Font(bold=True)

    fila_total += 1
    hoja.cell(row=fila_total, column=2, value="Número de facturas")
    hoja.cell(row=fila_total, column=4, value=reporte["numero_facturas"])

    _ajustar_ancho_columnas(hoja)
    libro.save(str(ruta_destino))
    return Path(ruta_destino)


def exportar_reporte_mensual_excel(
    reporte: Dict[str, Any],
    ruta_destino: Optional[Path] = None,
) -> Path:
    """
    Genera un Excel del reporte mensual en hoja Ventas con fila SUM() de ventas.
    Retorna la ruta del archivo guardado.
    """
    anio = reporte["anio"]
    mes = reporte["mes"]
    if ruta_destino is None:
        RUTA_EXPORTACION.mkdir(parents=True, exist_ok=True)
        ruta_destino = RUTA_EXPORTACION / f"reporte_mensual_{anio}-{mes:02d}.xlsx"
    _asegurar_directorio_destino(ruta_destino)

    libro = Workbook()
    hoja = libro.active
    hoja.title = _NOMBRE_HOJA

    fila_datos = _escribir_encabezado_hoja(
        hoja,
        "Reporte de ventas mensual",
        f"Período: {mes:02d}/{anio}",
    )

    encabezados = ["Fecha", "Total ventas (COP)", "Nº facturas"]
    for col, texto in enumerate(encabezados, start=1):
        hoja.cell(row=fila_datos, column=col, value=texto)
    _aplicar_estilo_encabezado_tabla(hoja, fila_datos, len(encabezados))

    fila_actual = fila_datos + 1
    cierres = reporte.get("cierres_diarios", [])
    if cierres:
        for cierre in cierres:
            hoja.cell(row=fila_actual, column=1, value=cierre["fecha"])
            hoja.cell(row=fila_actual, column=2, value=cierre["total_ventas"])
            hoja.cell(row=fila_actual, column=3, value=cierre["numero_facturas"])
            fila_actual += 1
    else:
        hoja.cell(row=fila_actual, column=1, value="Sin cierres registrados")
        fila_actual += 1

    fila_total = fila_actual
    hoja.cell(row=fila_total, column=1, value="TOTAL")
    hoja.cell(row=fila_total, column=1).font = Font(bold=True)
    col_ventas = get_column_letter(2)
    col_facturas = get_column_letter(3)
    primera_fila = fila_datos + 1
    ultima_fila = fila_actual - 1
    if cierres:
        hoja.cell(
            row=fila_total,
            column=2,
            value=f"=SUM({col_ventas}{primera_fila}:{col_ventas}{ultima_fila})",
        )
        hoja.cell(
            row=fila_total,
            column=3,
            value=f"=SUM({col_facturas}{primera_fila}:{col_facturas}{ultima_fila})",
        )
    else:
        hoja.cell(row=fila_total, column=2, value=0)
        hoja.cell(row=fila_total, column=3, value=0)
    hoja.cell(row=fila_total, column=2).font = Font(bold=True)
    hoja.cell(row=fila_total, column=3).font = Font(bold=True)

    _ajustar_ancho_columnas(hoja)
    libro.save(str(ruta_destino))
    return Path(ruta_destino)
