"""DTO que representa un pedido y sus ítems.

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class PedidoItem:
    """Representa un renglón de pedido (tabla pedido_items)."""

    id: int
    producto_id: int
    nombre_producto: str   # copia histórica
    cantidad: int
    precio_unitario: int   # pesos COP enteros
    subtotal: int          # pesos COP enteros


@dataclass
class Pedido:
    """Representa un pedido asociado a una mesa (tabla pedidos)."""

    id: int
    mesa_id: int
    fecha: str   # ISO 'YYYY-MM-DD'
    hora: str    # 'HH:MM:SS' 24h
    estado: str  # 'abierto' | 'cerrado'
    items: List[PedidoItem] = field(default_factory=list)

    def esta_abierto(self) -> bool:
        """Retorna True si el pedido sigue activo."""
        return self.estado == "abierto"

    def total(self) -> int:
        """Suma los subtotales de todos los ítems del pedido."""
        return sum(item.subtotal for item in self.items)
