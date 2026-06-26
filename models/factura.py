"""DTO que representa una factura (cabecera).

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.
Los renglones (factura_detalles) se manejan en facturacion_service.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class FacturaDetalle:
    """Representa un renglón de factura (tabla factura_detalles)."""

    id: int
    factura_id: int
    producto_id: int
    nombre_producto: str
    cantidad: int
    precio_unitario: int
    subtotal: int


@dataclass
class Factura:
    """Representa la cabecera de una factura (tabla facturas)."""

    id: int
    numero: str            # formato 'FAC-YYYYMMDD-NNN' (16 chars)
    pedido_id: int
    mesa_id: int
    fecha: str             # ISO 'YYYY-MM-DD'
    hora: str              # 'HH:MM:SS' 24h
    total: int             # pesos COP enteros
    descuento: int         # pesos COP enteros
    metodo_pago: str       # 'efectivo' | 'billetera_digital'
    estado: str            # 'pagada' | 'anulada'
    es_parcial: int        # 0 | 1
    grupo_division: Optional[str] = None

    def total_neto(self) -> int:
        """Retorna el total después de aplicar el descuento."""
        return self.total - self.descuento

    def esta_pagada(self) -> bool:
        """Retorna True si la factura no está anulada."""
        return self.estado == "pagada"

    def es_division_parcial(self) -> bool:
        """Retorna True si la factura proviene de una división de cuenta."""
        return self.es_parcial == 1
