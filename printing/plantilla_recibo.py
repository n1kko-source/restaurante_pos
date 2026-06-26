"""Formato y contenido del recibo térmico impreso."""

from dataclasses import dataclass, field
from typing import List, Optional

from models.factura import Factura, FacturaDetalle

# Anchos estándar ESC/POS para papel térmico.
ANCHO_PAPEL_58MM = 32
ANCHO_PAPEL_80MM = 48

_NOMBRE_RESTAURANTE_DEFAULT = "Restaurante Hogarenos"


@dataclass
class FacturaImpresion:
    """Datos completos de una factura lista para imprimir en Colpos."""

    factura: Factura
    detalles: List[FacturaDetalle] = field(default_factory=list)
    mesa_numero: Optional[int] = None
    nombre_restaurante: str = _NOMBRE_RESTAURANTE_DEFAULT


def normalizar_ancho_papel(ancho_config: int) -> int:
    """
    Normaliza el ancho configurado a un valor usable en caracteres.

    Acepta 32 (58 mm), 40 (intermedio) u 48 (80 mm).
    """
    if ancho_config <= 34:
        return ANCHO_PAPEL_58MM
    if ancho_config >= 44:
        return ANCHO_PAPEL_80MM
    return max(24, ancho_config)


def _formatear_pesos(monto: int) -> str:
    """Formatea un monto entero COP con separador de miles."""
    return f"${monto:,.0f}".replace(",", ".")


def _truncar(texto: str, maximo: int) -> str:
    """Recorta texto que excede el ancho disponible."""
    if len(texto) <= maximo:
        return texto
    if maximo <= 3:
        return texto[:maximo]
    return texto[: maximo - 3] + "..."


def _alinear_linea(izquierda: str, derecha: str, ancho: int) -> str:
    """Arma una línea con texto a la izquierda y monto alineado a la derecha."""
    derecha = derecha.strip()
    izquierda = _truncar(izquierda.strip(), max(1, ancho - len(derecha) - 1))
    espacio = ancho - len(izquierda) - len(derecha)
    if espacio < 1:
        espacio = 1
    return izquierda + (" " * espacio) + derecha


def _etiqueta_metodo_pago(metodo_pago: str) -> str:
    """Traduce el método de pago del schema a texto legible en el recibo."""
    etiquetas = {
        "efectivo": "Efectivo",
        "billetera_digital": "Billetera digital",
    }
    return etiquetas.get(metodo_pago, metodo_pago)


def generar_lineas_recibo(
    datos: FacturaImpresion,
    ancho_papel: int,
) -> List[str]:
    """
    Genera las líneas de texto del recibo según el ancho de papel configurado.

    Compatible con papel 58 mm (32 caracteres) y 80 mm (48 caracteres).
    """
    ancho = normalizar_ancho_papel(ancho_papel)
    factura = datos.factura
    lineas: List[str] = []

    titulo = _truncar(datos.nombre_restaurante.upper(), ancho)
    lineas.append(titulo.center(ancho))
    lineas.append("=" * ancho)
    lineas.append(f"Factura: {factura.numero}")
    lineas.append(f"Fecha: {factura.fecha}  {factura.hora[:5]}")
    if datos.mesa_numero is not None:
        lineas.append(f"Mesa: {datos.mesa_numero}")
    if factura.es_division_parcial():
        lineas.append("Cuenta dividida")
    lineas.append("-" * ancho)
    lineas.append("DETALLE")

    for detalle in datos.detalles:
        descripcion = f"{detalle.cantidad}x {detalle.nombre_producto}"
        lineas.append(_truncar(descripcion, ancho))
        lineas.append(
            _alinear_linea(
                f"  @{_formatear_pesos(detalle.precio_unitario)}",
                _formatear_pesos(detalle.subtotal),
                ancho,
            )
        )

    lineas.append("-" * ancho)
    if factura.descuento > 0:
        lineas.append(
            _alinear_linea("Subtotal:", _formatear_pesos(factura.total), ancho)
        )
        lineas.append(
            _alinear_linea(
                "Descuento:",
                f"-{_formatear_pesos(factura.descuento)}",
                ancho,
            )
        )
    lineas.append(
        _alinear_linea("TOTAL:", _formatear_pesos(factura.total_neto()), ancho)
    )
    lineas.append(f"Pago: {_etiqueta_metodo_pago(factura.metodo_pago)}")
    lineas.append("")
    lineas.append(_truncar("Gracias por su visita", ancho).center(ancho))
    lineas.append("")

    return lineas
