"""DTO que representa un producto del menú.

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.
"""

from dataclasses import dataclass


@dataclass
class Producto:
    """Representa un producto del catálogo (tabla productos)."""

    id: int
    categoria_id: int
    nombre: str
    precio: int   # pesos COP enteros
    stock: int
    activo: int   # 0 = inactivo, 1 = activo

    def esta_activo(self) -> bool:
        """Retorna True si el producto está disponible en el menú."""
        return self.activo == 1
