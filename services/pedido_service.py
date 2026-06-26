"""Lógica de negocio para ítems de pedido y catálogo del POS.

Flujo de capas: ui/ -> services/pedido_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import database.db_manager as db
from models.mesa import ESTADO_OCUPADA, Mesa
from models.pedido import Pedido, PedidoItem
from services import mesa_service
from services.auth_service import requiere_rol


@dataclass
class ProductoCatalogo:
    """Producto activo con nombre de categoría para el catálogo del POS."""

    id: int
    categoria_id: int
    nombre_categoria: str
    nombre: str
    precio: int
    stock: int


def _producto_catalogo_desde_fila(fila) -> ProductoCatalogo:
    """Convierte una fila sqlite3.Row del catálogo en ProductoCatalogo."""
    return ProductoCatalogo(
        id=fila["id"],
        categoria_id=fila["categoria_id"],
        nombre_categoria=fila["nombre_categoria"],
        nombre=fila["nombre"],
        precio=fila["precio"],
        stock=fila["stock"],
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


def _validar_pedido_abierto(pedido_id: int) -> None:
    """Lanza ValueError si el pedido no existe o no está abierto."""
    fila = db.obtener_pedido_por_id(pedido_id)
    if fila is None:
        raise ValueError(f"No existe un pedido con id {pedido_id}.")
    if fila["estado"] != "abierto":
        raise ValueError(
            f"El pedido {pedido_id} no está abierto (estado: '{fila['estado']}')."
        )


def _validar_item_pertenece_pedido(item_id: int, pedido_id: int) -> None:
    """Lanza ValueError si el ítem no pertenece al pedido indicado."""
    fila = db.obtener_item_pedido_por_id(item_id)
    if fila is None:
        raise ValueError(f"No existe un ítem con id {item_id}.")
    if fila["pedido_id"] != pedido_id:
        raise ValueError("El ítem seleccionado no pertenece a este pedido.")


def validar_acceso_pos(mesa_id: int, pedido_id: int) -> Tuple[Mesa, Pedido]:
    """
    Valida que el POS pueda abrirse para la mesa y pedido indicados.

    Requiere mesa en estado 'ocupada' con pedido abierto que coincida.
    Retorna (Mesa, Pedido) si todo es válido.
    """
    mesa = mesa_service.obtener_mesa(mesa_id)
    if mesa is None:
        raise ValueError(f"No existe una mesa con id {mesa_id}.")

    if mesa.estado != ESTADO_OCUPADA:
        raise ValueError(
            f"La mesa {mesa.numero} no tiene un pedido activo "
            f"(estado actual: '{mesa.estado}')."
        )

    pedido = mesa_service.obtener_pedido_activo(mesa_id)
    if pedido is None:
        raise ValueError(f"La mesa {mesa.numero} no tiene un pedido abierto.")

    if pedido.id != pedido_id:
        raise ValueError(
            f"El pedido #{pedido_id} no corresponde al pedido activo "
            f"de la mesa {mesa.numero}."
        )

    if not pedido.esta_abierto():
        raise ValueError(f"El pedido #{pedido_id} ya no está abierto.")

    return mesa, pedido


def obtener_catalogo_agrupado(
    termino: str = "",
) -> Dict[str, List[ProductoCatalogo]]:
    """
    Retorna el catálogo de productos activos agrupado por categoría.

    termino: texto opcional para filtrar por nombre de producto.
    """
    texto = termino.strip()
    filas = db.obtener_productos_catalogo(texto if texto else None)
    agrupado: Dict[str, List[ProductoCatalogo]] = {}
    for fila in filas:
        producto = _producto_catalogo_desde_fila(fila)
        agrupado.setdefault(producto.nombre_categoria, []).append(producto)
    return agrupado


@requiere_rol("cajero", "supervisor", "administrador")
def agregar_item(
    pedido_id: int,
    producto_id: int,
    cantidad: int = 1,
) -> PedidoItem:
    """
    Agrega un producto al pedido copiando nombre y precio para histórico.

    Si el producto ya está en el pedido, incrementa la cantidad existente.
    """
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")

    _validar_pedido_abierto(pedido_id)

    fila_producto = db.obtener_producto_por_id(producto_id)
    if fila_producto is None:
        raise ValueError(f"No existe un producto con id {producto_id}.")
    if fila_producto["activo"] != 1:
        raise ValueError(
            f"El producto '{fila_producto['nombre']}' no está disponible."
        )

    existente = db.obtener_item_pedido_por_producto(pedido_id, producto_id)
    if existente is not None:
        nueva_cantidad = existente["cantidad"] + cantidad
        db.actualizar_cantidad_item(existente["id"], nueva_cantidad)
        fila_actualizada = db.obtener_item_pedido_por_id(existente["id"])
        return _item_desde_fila(fila_actualizada)

    precio = fila_producto["precio"]
    subtotal = cantidad * precio
    item_id = db.agregar_item_pedido(
        pedido_id=pedido_id,
        producto_id=producto_id,
        nombre_producto=fila_producto["nombre"],
        cantidad=cantidad,
        precio_unitario=precio,
        subtotal=subtotal,
    )
    fila_item = db.obtener_item_pedido_por_id(item_id)
    return _item_desde_fila(fila_item)


@requiere_rol("cajero", "supervisor", "administrador")
def eliminar_item(pedido_id: int, item_id: int) -> None:
    """Elimina un ítem del pedido activo."""
    _validar_pedido_abierto(pedido_id)
    _validar_item_pertenece_pedido(item_id, pedido_id)
    db.eliminar_item_pedido(item_id)


@requiere_rol("cajero", "supervisor", "administrador")
def cambiar_cantidad_item(
    pedido_id: int,
    item_id: int,
    nueva_cantidad: int,
) -> PedidoItem:
    """Actualiza la cantidad de un ítem y recalcula el subtotal."""
    if nueva_cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a cero.")

    _validar_pedido_abierto(pedido_id)
    _validar_item_pertenece_pedido(item_id, pedido_id)
    db.actualizar_cantidad_item(item_id, nueva_cantidad)
    fila = db.obtener_item_pedido_por_id(item_id)
    return _item_desde_fila(fila)


def obtener_items_pedido(pedido_id: int) -> List[PedidoItem]:
    """Retorna los ítems del pedido con subtotales."""
    return mesa_service.obtener_items_pedido(pedido_id)
