"""Gestión de stock y alertas de inventario.

Flujo de capas: ui/ -> services/inventario_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

import math
from typing import List, Optional, Tuple

import database.db_manager as db
from config import PAGINA_TAMANO_DEFAULT
from models.producto import ProductoListado
from services.auth_service import requiere_rol
from services import hora_service

TIPO_ALERTA_DOMINICAL = "inventario_dominical"

_MENSAJE_ALERTA_DOMINICAL = (
    "Es domingo después de las 18:00.\n\n"
    "Por favor revise el inventario de productos antes de cerrar la jornada."
)


def _producto_listado_desde_fila(fila) -> ProductoListado:
    """Convierte fila con JOIN a categorías en ProductoListado."""
    return ProductoListado(
        id=fila["id"],
        categoria_id=fila["categoria_id"],
        nombre_categoria=fila["nombre_categoria"],
        nombre=fila["nombre"],
        precio=fila["precio"],
        stock=fila["stock"],
        activo=fila["activo"],
    )


def _calcular_total_paginas(total: int, por_pagina: int = PAGINA_TAMANO_DEFAULT) -> int:
    """Calcula el número de páginas para un listado paginado."""
    if total <= 0:
        return 1
    return max(1, math.ceil(total / por_pagina))


def _obtener_producto_o_error(producto_id: int) -> ProductoListado:
    """Retorna el producto o lanza ValueError si no existe."""
    fila = db.obtener_producto_por_id(producto_id)
    if fila is None:
        raise ValueError(f"No existe un producto con id {producto_id}.")
    return _producto_listado_desde_fila(fila)


@requiere_rol("supervisor", "administrador")
def listar_inventario_pagina(
    pagina: int = 1,
) -> Tuple[List[ProductoListado], int, int]:
    """
    Retorna (productos, total_registros, total_paginas) para el Treeview de inventario.
    Incluye productos activos e inactivos.
    """
    total = db.obtener_total_productos(solo_activos=False)
    total_paginas = _calcular_total_paginas(total)
    pagina = max(1, min(pagina, total_paginas))
    filas = db.obtener_productos_pagina(pagina, solo_activos=False)
    return (
        [_producto_listado_desde_fila(fila) for fila in filas],
        total,
        total_paginas,
    )


@requiere_rol("supervisor", "administrador")
def incrementar_stock(producto_id: int) -> ProductoListado:
    """Suma una unidad al stock del producto y retorna el estado actualizado."""
    producto = _obtener_producto_o_error(producto_id)
    db.actualizar_stock(producto_id, producto.stock + 1)
    return _obtener_producto_o_error(producto_id)


@requiere_rol("supervisor", "administrador")
def decrementar_stock(producto_id: int) -> ProductoListado:
    """Resta una unidad al stock del producto (mínimo 0) y retorna el estado actualizado."""
    producto = _obtener_producto_o_error(producto_id)
    if producto.stock <= 0:
        raise ValueError("El stock ya está en cero.")
    db.actualizar_stock(producto_id, producto.stock - 1)
    return _obtener_producto_o_error(producto_id)


def verificar_alerta_dominical() -> Optional[str]:
    """
    Si es domingo a las 18:00 o después y no hay alerta registrada hoy,
    la registra en la tabla alertas y retorna el mensaje para el popup.

    Retorna None si no corresponde mostrar la alerta.
    """
    ahora = hora_service.obtener_datetime_actual()
    if ahora.weekday() != 6:
        return None
    if ahora.hour < 18:
        return None

    fecha = ahora.strftime("%Y-%m-%d")
    if db.obtener_alerta(TIPO_ALERTA_DOMINICAL, fecha) is not None:
        return None

    db.registrar_alerta(TIPO_ALERTA_DOMINICAL, fecha)
    return _MENSAJE_ALERTA_DOMINICAL
