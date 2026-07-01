"""Formato y contenido del recibo térmico impreso."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from config import ETIQUETAS_METODO_PAGO, RESTAURANTE
from models.factura import Factura, FacturaDetalle

# Anchos estándar ESC/POS para papel térmico.
ANCHO_PAPEL_58MM = 32
ANCHO_PAPEL_80MM = 48

_MENSAJE_AGRADECIMIENTO = "Gracias por su visita"


@dataclass
class FacturaImpresion:
    """Datos completos de una factura lista para imprimir en Colpos."""

    factura: Factura
    detalles: List[FacturaDetalle] = field(default_factory=list)
    mesa_numero: Optional[int] = None
    # Compatibilidad con código existente; la plantilla usa razon_social/direccion.
    nombre_restaurante: str = RESTAURANTE["nombre"]
    direccion_restaurante: str = RESTAURANTE["direccion"]
    # Encabezado configurable (vacío = no se imprime la línea).
    titulo_documento: str = ""
    razon_social: str = ""
    nit: str = ""
    direccion: str = ""
    regimen_tributario: str = ""
    comprador_nombre: str = ""
    comprador_identificacion: str = ""
    ruta_logo: Optional[Path] = None


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


def _centrar(texto: str, ancho: int) -> str:
    """Centra texto respetando el ancho máximo de la línea."""
    texto = _truncar(texto.strip(), ancho)
    return texto.center(ancho)


def _linea_separadora(ancho: int) -> str:
    """Genera una línea de guiones ajustada al ancho configurado."""
    return "-" * ancho


def _alinear_linea(izquierda: str, derecha: str, ancho: int) -> str:
    """Arma una línea con texto a la izquierda y monto alineado a la derecha."""
    derecha = derecha.strip()
    izquierda = _truncar(izquierda.strip(), max(1, ancho - len(derecha) - 1))
    espacio = ancho - len(izquierda) - len(derecha)
    if espacio < 1:
        espacio = 1
    return izquierda + (" " * espacio) + derecha


def _anchos_tabla_items(ancho: int) -> Tuple[int, int, int, int]:
    """Calcula anchos de columnas para la tabla de ítems según el papel."""
    if ancho <= ANCHO_PAPEL_58MM:
        cant_w, pu_w, sub_w = 2, 8, 9
    else:
        cant_w, pu_w, sub_w = 3, 10, 11
    nombre_w = ancho - cant_w - pu_w - sub_w - 3
    if nombre_w < 4:
        nombre_w = 4
    return cant_w, nombre_w, pu_w, sub_w


def _formatear_fila_detalle(detalle: FacturaDetalle, ancho: int) -> str:
    """Formatea un renglón: cantidad, nombre truncado, precio unitario y subtotal."""
    cant_w, nombre_w, pu_w, sub_w = _anchos_tabla_items(ancho)
    cantidad = _truncar(str(detalle.cantidad), cant_w)
    nombre = _truncar(detalle.nombre_producto, nombre_w)
    precio = _formatear_pesos(detalle.precio_unitario)
    subtotal = _formatear_pesos(detalle.subtotal)
    return (
        f"{cantidad:>{cant_w}} "
        f"{nombre:<{nombre_w}} "
        f"{precio:>{pu_w}} "
        f"{subtotal:>{sub_w}}"
    )


def _encabezado_tabla_items(ancho: int) -> str:
    """Etiquetas de columnas para la tabla de ítems."""
    cant_w, nombre_w, pu_w, sub_w = _anchos_tabla_items(ancho)
    return (
        f"{'Ct':>{cant_w}} "
        f"{'Producto':<{nombre_w}} "
        f"{'P.Unit':>{pu_w}} "
        f"{'Total':>{sub_w}}"
    )


def _etiqueta_metodo_pago(metodo_pago: str) -> str:
    """Traduce el método de pago del schema a texto legible en el recibo."""
    etiquetas_legacy = {
        "billetera_digital": "Billetera digital",
    }
    if metodo_pago in etiquetas_legacy:
        return etiquetas_legacy[metodo_pago]
    return ETIQUETAS_METODO_PAGO.get(metodo_pago, metodo_pago)


def _formatear_fecha_hora(fecha: str, hora: str) -> str:
    """Combina fecha ISO y hora 24h para el encabezado del recibo."""
    hora_corta = hora[:5] if len(hora) >= 5 else hora
    return f"{fecha}  {hora_corta}"


def _agregar_linea_centrada(
    lineas: List[str], texto: str, ancho: int, mayusculas: bool = False
) -> None:
    """Añade una línea centrada solo si el texto no está vacío."""
    limpio = texto.strip()
    if not limpio:
        return
    if mayusculas:
        limpio = limpio.upper()
    lineas.append(_centrar(limpio, ancho))


def _agregar_linea_izquierda(lineas: List[str], texto: str) -> None:
    """Añade una línea alineada a la izquierda solo si el texto no está vacío."""
    limpio = texto.strip()
    if limpio:
        lineas.append(limpio)


def generar_lineas_recibo(
    datos: FacturaImpresion,
    ancho_papel: int,
) -> List[str]:
    """
    Genera las líneas de texto del recibo según el ancho de papel configurado.

    Compatible con papel 58 mm (32 caracteres) y 80 mm (48 caracteres).
    Los campos de plantilla vacíos no generan línea en el recibo.
    """
    ancho = normalizar_ancho_papel(ancho_papel)
    factura = datos.factura
    lineas: List[str] = []

    razon = datos.razon_social.strip() or datos.nombre_restaurante.strip()
    direccion = datos.direccion.strip() or datos.direccion_restaurante.strip()

    _agregar_linea_centrada(lineas, datos.titulo_documento, ancho, mayusculas=True)
    _agregar_linea_centrada(lineas, razon, ancho, mayusculas=True)
    if datos.nit.strip():
        _agregar_linea_centrada(lineas, f"NIT: {datos.nit.strip()}", ancho)
    _agregar_linea_centrada(lineas, direccion, ancho)
    _agregar_linea_centrada(lineas, datos.regimen_tributario, ancho)

    if datos.comprador_nombre.strip() or datos.comprador_identificacion.strip():
        lineas.append(_linea_separadora(ancho))
        if datos.comprador_nombre.strip():
            _agregar_linea_izquierda(
                lineas, f"Comprador: {datos.comprador_nombre.strip()}"
            )
        if datos.comprador_identificacion.strip():
            _agregar_linea_izquierda(
                lineas,
                f"Identificación: {datos.comprador_identificacion.strip()}",
            )

    lineas.append(_centrar(_formatear_fecha_hora(factura.fecha, factura.hora), ancho))
    lineas.append(_linea_separadora(ancho))

    lineas.append(f"Factura: {factura.numero}")
    if datos.mesa_numero is not None:
        lineas.append(f"Mesa: {datos.mesa_numero}")
    if factura.es_division_parcial():
        lineas.append("Cuenta dividida")

    lineas.append(_encabezado_tabla_items(ancho))
    for detalle in datos.detalles:
        lineas.append(_formatear_fila_detalle(detalle, ancho))

    lineas.append(_linea_separadora(ancho))

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
    lineas.append(
        _alinear_linea(
            "Pago:",
            _etiqueta_metodo_pago(factura.metodo_pago),
            ancho,
        )
    )

    lineas.append("")
    lineas.append(_centrar(_MENSAJE_AGRADECIMIENTO, ancho))
    lineas.append("")

    return lineas


def formatear_recibo(datos: FacturaImpresion, ancho: int) -> str:
    """
    Retorna el recibo como un string listo para enviar a la impresora.

    datos: cabecera de factura, renglones y datos del restaurante.
    ancho: caracteres por línea según config.IMPRESORA['ancho_papel'].
    """
    lineas = generar_lineas_recibo(datos, ancho)
    return "\n".join(lineas)
