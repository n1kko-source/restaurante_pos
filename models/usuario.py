"""DTO que representa un usuario del sistema.

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.
"""

from dataclasses import dataclass


@dataclass
class Usuario:
    """Representa un usuario autenticado del sistema POS."""

    id: int
    nombre: str
    usuario: str
    rol: str  # 'cajero' | 'supervisor' | 'administrador'

    def es_administrador(self) -> bool:
        """Retorna True si el usuario tiene rol administrador."""
        return self.rol == "administrador"

    def es_supervisor_o_superior(self) -> bool:
        """Retorna True si el usuario puede acceder a funciones de supervisor."""
        return self.rol in ("supervisor", "administrador")
