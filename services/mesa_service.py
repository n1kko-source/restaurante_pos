"""Lógica de negocio para estados de mesa y apertura o cierre de pedidos.

Flujo de capas: ui/ -> services/mesa_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

from typing import Dict, List, Optional, Set

import database.db_manager as db
from models.mesa import (
    ESTADO_ESPERANDO_PAGO,
    ESTADO_LIBRE,
    ESTADO_OCUPADA,
    Mesa,
)
from models.pedido import Pedido, PedidoItem
from services.auth_service import requiere_rol
from services import hora_service

# Transiciones válidas entre estados de mesa según el flujo operativo del salón.
_TRANSICIONES_PERMITIDAS: Dict[str, Set[str]] = {
    ESTADO_LIBRE: {ESTADO_OCUPADA},
    ESTADO_OCUPADA: {ESTADO_ESPERANDO_PAGO, ESTADO_LIBRE},
    ESTADO_ESPERANDO_PAGO: {ESTADO_LIBRE},
}

_ESTADOS_MESA_VALIDOS = frozenset(_TRANSICIONES_PERMITIDAS.keys())


# ============================================================
# HELPERS INTERNOS
# ============================================================

def _obtener_fecha_hora_actual() -> tuple:
    """Delega en hora_service la obtención validada de fecha y hora."""
    return hora_service.obtener_fecha_hora_actual()


def _mesa_desde_fila(fila) -> Mesa:
    """Convierte una fila sqlite3.Row de mesas en instancia Mesa."""
    return Mesa(
        id=fila["id"],
        numero=fila["numero"],
        estado=fila["estado"],
        num_personas=fila["num_personas"],
    )


def _pedido_desde_fila(fila, items: Optional[List[PedidoItem]] = None) -> Pedido:
    """Convierte una fila sqlite3.Row de pedidos en instancia Pedido."""
    return Pedido(
        id=fila["id"],
        mesa_id=fila["mesa_id"],
        fecha=fila["fecha"],
        hora=fila["hora"],
        estado=fila["estado"],
        items=items if items is not None else [],
    )


def _item_desde_fila(fila) -> PedidoItem:
    """Convierte una fila sqlite3.Row de pedido_items en instancia PedidoItem."""
    return PedidoItem(
        id=fila["id"],
        producto_id=fila["producto_id"],
        nombre_producto=fila["nombre_producto"],
        cantidad=fila["cantidad"],
        precio_unitario=fila["precio_unitario"],
        subtotal=fila["subtotal"],
    )


def _validar_transicion(estado_actual: str, nuevo_estado: str) -> None:
    """Lanza ValueError si la transición de estado de mesa no está permitida."""
    if nuevo_estado not in _ESTADOS_MESA_VALIDOS:
        raise ValueError(
            f"Estado de mesa inválido: '{nuevo_estado}'. "
            f"Valores permitidos: {', '.join(sorted(_ESTADOS_MESA_VALIDOS))}."
        )
    permitidos = _TRANSICIONES_PERMITIDAS.get(estado_actual, set())
    if nuevo_estado not in permitidos:
        raise ValueError(
            f"No se puede cambiar la mesa de '{estado_actual}' a '{nuevo_estado}'."
        )


# ============================================================
# CONSULTAS DE MESAS
# ============================================================

def obtener_todas_mesas() -> List[Mesa]:
    """Retorna todas las mesas del salón ordenadas por número."""
    filas = db.obtener_todas_mesas()
    return [_mesa_desde_fila(fila) for fila in filas]


def obtener_mesa(mesa_id: int) -> Optional[Mesa]:
    """Retorna la mesa con ese id, o None si no existe."""
    fila = db.obtener_mesa_por_id(mesa_id)
    if fila is None:
        return None
    return _mesa_desde_fila(fila)


# ============================================================
# CICLO DE VIDA DE PEDIDOS
# ============================================================

@requiere_rol("cajero", "supervisor", "administrador")
def abrir_pedido(mesa_id: int) -> Pedido:
    """
    Abre un pedido nuevo en una mesa libre.

    Cambia el estado de la mesa a 'ocupada' (con pedido) y crea el registro
    en la tabla pedidos con estado 'abierto'.
    Retorna el Pedido creado.
    """
    mesa = db.obtener_mesa_por_id(mesa_id)
    if mesa is None:
        raise ValueError(f"No existe una mesa con id {mesa_id}.")

    if mesa["estado"] != ESTADO_LIBRE:
        raise ValueError(
            f"La mesa {mesa['numero']} no está libre "
            f"(estado actual: '{mesa['estado']}')."
        )

    if db.obtener_pedido_abierto_por_mesa(mesa_id) is not None:
        raise ValueError(
            f"La mesa {mesa['numero']} ya tiene un pedido abierto."
        )

    fecha, hora = _obtener_fecha_hora_actual()
    pedido_id = db.crear_pedido(mesa_id, fecha, hora)
    db.actualizar_estado_mesa(mesa_id, ESTADO_OCUPADA, mesa["num_personas"])

    fila_pedido = db.obtener_pedido_por_id(pedido_id)
    return _pedido_desde_fila(fila_pedido)


@requiere_rol("cajero", "supervisor", "administrador")
def cerrar_pedido(pedido_id: int) -> None:
    """Marca un pedido como cerrado. No modifica el estado de la mesa."""
    fila = db.obtener_pedido_por_id(pedido_id)
    if fila is None:
        raise ValueError(f"No existe un pedido con id {pedido_id}.")

    if fila["estado"] != "abierto":
        raise ValueError(
            f"El pedido {pedido_id} no está abierto (estado: '{fila['estado']}')."
        )

    db.cerrar_pedido(pedido_id)


@requiere_rol("cajero", "supervisor", "administrador")
def cambiar_estado_mesa(mesa_id: int, nuevo_estado: str) -> Mesa:
    """
    Cambia el estado de una mesa validando las transiciones permitidas.

    Transiciones válidas:
      libre -> ocupada
      ocupada -> esperando_pago | libre
      esperando_pago -> libre

    Al pasar a 'libre' se resetea num_personas a 0 (requisito del schema).
    Retorna la mesa actualizada.
    """
    fila = db.obtener_mesa_por_id(mesa_id)
    if fila is None:
        raise ValueError(f"No existe una mesa con id {mesa_id}.")

    estado_actual = fila["estado"]
    _validar_transicion(estado_actual, nuevo_estado)

    num_personas = 0 if nuevo_estado == ESTADO_LIBRE else fila["num_personas"]
    db.actualizar_estado_mesa(mesa_id, nuevo_estado, num_personas)

    fila_actualizada = db.obtener_mesa_por_id(mesa_id)
    return _mesa_desde_fila(fila_actualizada)


def obtener_pedido_activo(mesa_id: int) -> Optional[Pedido]:
    """Retorna el pedido abierto de la mesa, o None si no tiene uno activo."""
    fila = db.obtener_pedido_abierto_por_mesa(mesa_id)
    if fila is None:
        return None
    return _pedido_desde_fila(fila)


def obtener_items_pedido(pedido_id: int) -> List[PedidoItem]:
    """Retorna los ítems de un pedido con sus subtotales, ordenados por id."""
    fila = db.obtener_pedido_por_id(pedido_id)
    if fila is None:
        raise ValueError(f"No existe un pedido con id {pedido_id}.")

    filas = db.obtener_items_pedido(pedido_id)
    return [_item_desde_fila(fila) for fila in filas]
