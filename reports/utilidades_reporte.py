"""Helpers compartidos para exportación de reportes PDF y Excel."""

from typing import Any, Dict, List, Optional

from config import ETIQUETAS_METODO_PAGO

# Encabezados compactos del detalle diario por factura.
ENCABEZADOS_DETALLE_DIARIO = (
    "No.",
    "Método",
    "Comprador",
    "Producto",
    "Cant.",
    "Subtotal",
)


def numero_factura_corto(numero: str) -> str:
    """
    Extrae el consecutivo diario de un número FAC-YYYYMMDD-XXX.
    En reportes del mismo día basta el sufijo (ej. 001) porque la fecha va en el encabezado.
    """
    if not numero:
        return "—"
    partes = numero.rsplit("-", 1)
    if len(partes) == 2 and partes[1].isdigit():
        return partes[1]
    return numero


def etiqueta_metodo_pago(metodo_pago: str) -> str:
    """Traduce el código de método de pago a texto legible en el reporte."""
    etiquetas_legacy = {"billetera_digital": "Billetera digital"}
    if metodo_pago in etiquetas_legacy:
        return etiquetas_legacy[metodo_pago]
    return ETIQUETAS_METODO_PAGO.get(metodo_pago, metodo_pago)


def texto_comprador(nombre: str) -> str:
    """Muestra guión cuando no hay nombre de comprador registrado."""
    return nombre.strip() if nombre and nombre.strip() else "—"


def detalle_con_separadores_factura(
    detalle: List[Dict[str, Any]],
) -> List[Optional[Dict[str, Any]]]:
    """
    Inserta None entre renglones cuando cambia el número de factura.
    None representa una fila en blanco de separación visual en Excel.
    """
    resultado: List[Optional[Dict[str, Any]]] = []
    factura_anterior = None
    for item in detalle:
        if factura_anterior is not None and item["factura_numero"] != factura_anterior:
            resultado.append(None)
        resultado.append(item)
        factura_anterior = item["factura_numero"]
    return resultado


def agrupar_detalle_por_factura(
    detalle: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Agrupa renglones consecutivos por número de factura (orden del día)."""
    if not detalle:
        return []

    grupos: List[List[Dict[str, Any]]] = []
    grupo_actual = [detalle[0]]
    for item in detalle[1:]:
        if item["factura_numero"] != grupo_actual[0]["factura_numero"]:
            grupos.append(grupo_actual)
            grupo_actual = [item]
        else:
            grupo_actual.append(item)
    grupos.append(grupo_actual)
    return grupos
