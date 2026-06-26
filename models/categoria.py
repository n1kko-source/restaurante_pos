"""DTO que representa una categoría del menú.

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.
"""

from dataclasses import dataclass


@dataclass
class Categoria:
    """Representa una categoría del catálogo (tabla categorias)."""

    id: int
    nombre: str
