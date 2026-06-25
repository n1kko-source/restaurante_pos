"""DTO que representa una mesa del salón.

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.
"""

from dataclasses import dataclass

# Vocabulario de estado según schema.sql (tabla mesas).
ESTADO_LIBRE = "libre"
ESTADO_OCUPADA = "ocupada"
ESTADO_ESPERANDO_PAGO = "esperando_pago"

_ETIQUETAS_ESTADO = {
    ESTADO_LIBRE: "Libre",
    ESTADO_OCUPADA: "Con pedido",
    ESTADO_ESPERANDO_PAGO: "Esperando factura",
}


@dataclass
class Mesa:
    """Representa una mesa del salón (tabla mesas)."""

    id: int
    numero: int
    estado: str   # 'libre' | 'ocupada' | 'esperando_pago'
    num_personas: int

    def etiqueta_estado(self) -> str:
        """Retorna el texto de estado para mostrar en la UI."""
        return _ETIQUETAS_ESTADO.get(self.estado, self.estado)

    def esta_libre(self) -> bool:
        """Retorna True si la mesa no tiene pedido activo."""
        return self.estado == ESTADO_LIBRE
