"""Gestión del menú: productos y categorías.

Flujo de capas: ui/ -> services/menu_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

import math
from typing import List, Optional, Tuple

import database.db_manager as db
from config import PAGINA_TAMANO_DEFAULT
from models.categoria import Categoria
from models.producto import ProductoListado
from services.auth_service import requiere_rol


def _categoria_desde_fila(fila) -> Categoria:
    """Convierte una fila sqlite3.Row de categorias en instancia Categoria."""
    return Categoria(id=fila["id"], nombre=fila["nombre"])


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


def _validar_nombre(nombre: str, etiqueta: str = "nombre") -> str:
    """Valida que un nombre no esté vacío y retorna el texto limpio."""
    limpio = nombre.strip()
    if not limpio:
        raise ValueError(f"El {etiqueta} no puede estar vacío.")
    return limpio


def _validar_precio_stock(precio: int, stock: int) -> None:
    """Valida rangos de precio y stock según el schema."""
    if precio < 0:
        raise ValueError("El precio no puede ser negativo.")
    if stock < 0:
        raise ValueError("El stock no puede ser negativo.")


def _calcular_total_paginas(total: int, por_pagina: int = PAGINA_TAMANO_DEFAULT) -> int:
    """Calcula el número de páginas para un listado paginado."""
    if total <= 0:
        return 1
    return max(1, math.ceil(total / por_pagina))


def _validar_categoria_existe(categoria_id: int) -> None:
    """Verifica que la categoría exista antes de asociar un producto."""
    categorias = db.obtener_todas_categorias()
    if not any(fila["id"] == categoria_id for fila in categorias):
        raise ValueError(f"No existe una categoría con id {categoria_id}.")


@requiere_rol("supervisor", "administrador")
def listar_categorias_selector() -> List[Categoria]:
    """Retorna todas las categorías para selectores (dropdowns)."""
    filas = db.obtener_todas_categorias()
    return [_categoria_desde_fila(fila) for fila in filas]


@requiere_rol("supervisor", "administrador")
def listar_categorias_pagina(
    pagina: int = 1,
) -> Tuple[List[Categoria], int, int]:
    """
    Retorna (categorías, total_registros, total_paginas) para el Treeview.
    pagina es 1-indexado.
    """
    total = db.obtener_total_categorias()
    filas = db.obtener_categorias_pagina(pagina)
    return (
        [_categoria_desde_fila(fila) for fila in filas],
        total,
        _calcular_total_paginas(total),
    )


@requiere_rol("supervisor", "administrador")
def crear_categoria(nombre: str) -> Categoria:
    """Registra una categoría nueva y retorna su DTO."""
    nombre_limpio = _validar_nombre(nombre, "nombre de la categoría")
    cat_id = db.crear_categoria(nombre_limpio)
    return Categoria(id=cat_id, nombre=nombre_limpio)


@requiere_rol("supervisor", "administrador")
def renombrar_categoria(categoria_id: int, nombre: str) -> Categoria:
    """Actualiza el nombre de una categoría existente."""
    nombre_limpio = _validar_nombre(nombre, "nombre de la categoría")
    filas = db.obtener_todas_categorias()
    existe = next((fila for fila in filas if fila["id"] == categoria_id), None)
    if existe is None:
        raise ValueError(f"No existe una categoría con id {categoria_id}.")
    db.actualizar_categoria(categoria_id, nombre_limpio)
    return Categoria(id=categoria_id, nombre=nombre_limpio)


@requiere_rol("supervisor", "administrador")
def listar_productos_pagina(
    pagina: int = 1,
    categoria_id: Optional[int] = None,
) -> Tuple[List[ProductoListado], int, int]:
    """
    Retorna (productos, total_registros, total_paginas) para el Treeview.
    Incluye productos inactivos para permitir reactivación.
    """
    total = db.obtener_total_productos(
        categoria_id=categoria_id,
        solo_activos=False,
    )
    filas = db.obtener_productos_pagina(
        pagina,
        categoria_id=categoria_id,
        solo_activos=False,
    )
    return (
        [_producto_listado_desde_fila(fila) for fila in filas],
        total,
        _calcular_total_paginas(total),
    )


@requiere_rol("supervisor", "administrador")
def obtener_producto(producto_id: int) -> ProductoListado:
    """Retorna un producto con su categoría o lanza ValueError si no existe."""
    fila = db.obtener_producto_por_id(producto_id)
    if fila is None:
        raise ValueError(f"No existe un producto con id {producto_id}.")
    return _producto_listado_desde_fila(fila)


@requiere_rol("supervisor", "administrador")
def crear_producto(
    categoria_id: int,
    nombre: str,
    precio: int,
    stock: int,
) -> ProductoListado:
    """Registra un producto activo en el menú."""
    nombre_limpio = _validar_nombre(nombre, "nombre del producto")
    _validar_precio_stock(precio, stock)
    _validar_categoria_existe(categoria_id)
    prod_id = db.crear_producto(categoria_id, nombre_limpio, precio, stock)
    return obtener_producto(prod_id)


@requiere_rol("supervisor", "administrador")
def actualizar_producto(
    producto_id: int,
    categoria_id: int,
    nombre: str,
    precio: int,
    stock: int,
) -> ProductoListado:
    """Actualiza los datos editables de un producto conservando su estado activo."""
    nombre_limpio = _validar_nombre(nombre, "nombre del producto")
    _validar_precio_stock(precio, stock)
    _validar_categoria_existe(categoria_id)
    actual = obtener_producto(producto_id)
    db.actualizar_producto(
        producto_id,
        categoria_id,
        nombre_limpio,
        precio,
        stock,
        actual.activo,
    )
    return obtener_producto(producto_id)


@requiere_rol("supervisor", "administrador")
def activar_producto(producto_id: int) -> ProductoListado:
    """Marca un producto como activo (visible en el POS)."""
    actual = obtener_producto(producto_id)
    db.actualizar_producto(
        producto_id,
        actual.categoria_id,
        actual.nombre,
        actual.precio,
        actual.stock,
        1,
    )
    return obtener_producto(producto_id)


@requiere_rol("supervisor", "administrador")
def desactivar_producto(producto_id: int) -> ProductoListado:
    """Marca un producto como inactivo sin borrar el histórico."""
    obtener_producto(producto_id)
    db.desactivar_producto(producto_id)
    return obtener_producto(producto_id)
