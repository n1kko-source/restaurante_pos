"""DTO que representa un cierre diario de ventas.

Sin lógica de negocio, sin SQL, sin conexión a base de datos.
Viaja entre capas: database -> services -> ui.

El cierre mensual se calcula desde facturas; no tiene tabla propia.
"""

from dataclasses import dataclass


@dataclass
class Cierre:
    """Representa un cierre diario (tabla cierres_diarios)."""

    id: int
    fecha: str             # ISO 'YYYY-MM-DD'
    total_ventas: int      # pesos COP enteros
    numero_facturas: int
    generado_en: str       # timestamp ISO completo
