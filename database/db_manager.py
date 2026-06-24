"""Gestión de conexión SQLite y ejecución de queries CRUD."""

import sqlite3
from pathlib import Path
from typing import Optional

import bcrypt

RUTA_DB = Path(__file__).parent / 'restaurante.db'
RUTA_SCHEMA = Path(__file__).parent / 'schema.sql'

_ADMIN_USUARIO_DEFAULT = 'admin'
_ADMIN_PASSWORD_DEFAULT = 'admin123'


# ============================================================
# CONEXIÓN E INICIALIZACIÓN
# ============================================================

def obtener_conexion() -> sqlite3.Connection:
    """
    Abre una conexión a restaurante.db con foreign keys activos y modo WAL.
    Cada llamada retorna una conexión nueva; el llamador es responsable de cerrarla.
    """
    con = sqlite3.connect(str(RUTA_DB))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def init_db() -> None:
    """
    Inicializa la BD de forma idempotente:
      - Crea tablas, índices y datos semilla desde schema.sql si la BD es nueva.
      - Inserta el usuario administrador inicial (con hash bcrypt) si la tabla
        usuarios está vacía.
    Contraseña inicial del admin: 'admin123' — cambiar tras el primer inicio.
    """
    con = obtener_conexion()
    try:
        fila = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if fila is None:
            schema = RUTA_SCHEMA.read_text(encoding='utf-8')
            con.executescript(schema)

        if con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            password_hash = bcrypt.hashpw(
                _ADMIN_PASSWORD_DEFAULT.encode('utf-8'),
                bcrypt.gensalt()
            ).decode('utf-8')
            con.execute(
                "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (?, ?, ?, ?)",
                ('Administrador', _ADMIN_USUARIO_DEFAULT, password_hash, 'administrador')
            )
            con.commit()
    finally:
        con.close()


# ============================================================
# USUARIOS
# ============================================================

def crear_usuario(nombre: str, usuario: str, password_hash: str, rol: str) -> int:
    """Inserta un nuevo usuario y retorna su id."""
    con = obtener_conexion()
    try:
        cursor = con.execute(
            "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (?, ?, ?, ?)",
            (nombre, usuario, password_hash, rol)
        )
        con.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_usuario_por_nombre(usuario: str) -> Optional[sqlite3.Row]:
    """Retorna la fila del usuario con ese nombre de usuario, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()
    finally:
        con.close()


def obtener_todos_usuarios() -> list:
    """Retorna todos los usuarios ordenados por nombre."""
    con = obtener_conexion()
    try:
        return con.execute("SELECT * FROM usuarios ORDER BY nombre").fetchall()
    finally:
        con.close()


def actualizar_usuario(
    id: int, nombre: str, usuario: str, password_hash: str, rol: str
) -> None:
    """Actualiza todos los campos de un usuario existente."""
    con = obtener_conexion()
    try:
        con.execute(
            "UPDATE usuarios SET nombre=?, usuario=?, password_hash=?, rol=? WHERE id=?",
            (nombre, usuario, password_hash, rol, id)
        )
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def eliminar_usuario(id: int) -> None:
    """Elimina un usuario por su id."""
    con = obtener_conexion()
    try:
        con.execute("DELETE FROM usuarios WHERE id=?", (id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


# ============================================================
# CATEGORÍAS
# ============================================================

def crear_categoria(nombre: str) -> int:
    """Inserta una nueva categoría y retorna su id."""
    con = obtener_conexion()
    try:
        cursor = con.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
        con.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_todas_categorias() -> list:
    """Retorna todas las categorías ordenadas por nombre."""
    con = obtener_conexion()
    try:
        return con.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()
    finally:
        con.close()


def actualizar_categoria(id: int, nombre: str) -> None:
    """Actualiza el nombre de una categoría."""
    con = obtener_conexion()
    try:
        con.execute("UPDATE categorias SET nombre=? WHERE id=?", (nombre, id))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def eliminar_categoria(id: int) -> None:
    """
    Elimina una categoría por su id.
    Lanza sqlite3.IntegrityError si tiene productos asociados (ON DELETE RESTRICT).
    """
    con = obtener_conexion()
    try:
        con.execute("DELETE FROM categorias WHERE id=?", (id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


# ============================================================
# PRODUCTOS
# ============================================================

def crear_producto(
    categoria_id: int, nombre: str, precio: int, stock: int
) -> int:
    """Inserta un nuevo producto activo y retorna su id."""
    con = obtener_conexion()
    try:
        cursor = con.execute(
            "INSERT INTO productos (categoria_id, nombre, precio, stock) VALUES (?, ?, ?, ?)",
            (categoria_id, nombre, precio, stock)
        )
        con.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_producto_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila del producto con ese id, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute(
            """SELECT p.*, c.nombre AS nombre_categoria
               FROM productos p JOIN categorias c ON p.categoria_id = c.id
               WHERE p.id=?""",
            (id,)
        ).fetchone()
    finally:
        con.close()


def obtener_productos_pagina(
    pagina: int = 1,
    por_pagina: int = 50,
    categoria_id: Optional[int] = None,
    solo_activos: bool = True
) -> list:
    """
    Retorna una página de productos con JOIN a categorías.
    pagina es 1-indexado. Nunca carga toda la tabla en memoria.
    """
    condiciones = []
    params = []
    if solo_activos:
        condiciones.append("p.activo = 1")
    if categoria_id is not None:
        condiciones.append("p.categoria_id = ?")
        params.append(categoria_id)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    offset = (pagina - 1) * por_pagina
    params.extend([por_pagina, offset])
    con = obtener_conexion()
    try:
        return con.execute(
            f"""SELECT p.*, c.nombre AS nombre_categoria
                FROM productos p
                JOIN categorias c ON p.categoria_id = c.id
                {where}
                ORDER BY c.nombre, p.nombre
                LIMIT ? OFFSET ?""",
            params
        ).fetchall()
    finally:
        con.close()


def obtener_total_productos(
    categoria_id: Optional[int] = None, solo_activos: bool = True
) -> int:
    """Retorna el conteo total de productos para calcular el número de páginas."""
    condiciones = []
    params = []
    if solo_activos:
        condiciones.append("activo = 1")
    if categoria_id is not None:
        condiciones.append("categoria_id = ?")
        params.append(categoria_id)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    con = obtener_conexion()
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM productos {where}", params
        ).fetchone()[0]
    finally:
        con.close()


def actualizar_producto(
    id: int, categoria_id: int, nombre: str,
    precio: int, stock: int, activo: int
) -> None:
    """Actualiza todos los campos editables de un producto."""
    con = obtener_conexion()
    try:
        con.execute(
            "UPDATE productos SET categoria_id=?, nombre=?, precio=?, stock=?, activo=? WHERE id=?",
            (categoria_id, nombre, precio, stock, activo, id)
        )
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def desactivar_producto(id: int) -> None:
    """
    Marca un producto como inactivo (activo=0).
    No elimina el registro para preservar el histórico de pedidos y facturas.
    """
    con = obtener_conexion()
    try:
        con.execute("UPDATE productos SET activo=0 WHERE id=?", (id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def actualizar_stock(id: int, nuevo_stock: int) -> None:
    """Actualiza el stock de un producto."""
    con = obtener_conexion()
    try:
        con.execute("UPDATE productos SET stock=? WHERE id=?", (nuevo_stock, id))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


# ============================================================
# MESAS
# ============================================================

def obtener_todas_mesas() -> list:
    """Retorna todas las mesas ordenadas por número."""
    con = obtener_conexion()
    try:
        return con.execute("SELECT * FROM mesas ORDER BY numero").fetchall()
    finally:
        con.close()


def obtener_mesa_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila de la mesa con ese id, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute("SELECT * FROM mesas WHERE id=?", (id,)).fetchone()
    finally:
        con.close()


def actualizar_estado_mesa(id: int, estado: str, num_personas: int) -> None:
    """
    Actualiza el estado y número de personas de una mesa.
    El estado debe ser uno de: 'libre', 'ocupada', 'esperando_pago'.
    """
    con = obtener_conexion()
    try:
        con.execute(
            "UPDATE mesas SET estado=?, num_personas=? WHERE id=?",
            (estado, num_personas, id)
        )
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


# ============================================================
# PEDIDOS
# ============================================================

def crear_pedido(mesa_id: int, fecha: str, hora: str) -> int:
    """Inserta un pedido nuevo en estado 'abierto' y retorna su id."""
    con = obtener_conexion()
    try:
        cursor = con.execute(
            "INSERT INTO pedidos (mesa_id, fecha, hora) VALUES (?, ?, ?)",
            (mesa_id, fecha, hora)
        )
        con.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_pedido_abierto_por_mesa(mesa_id: int) -> Optional[sqlite3.Row]:
    """Retorna el pedido en estado 'abierto' de una mesa, o None si no tiene."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM pedidos WHERE mesa_id=? AND estado='abierto'",
            (mesa_id,)
        ).fetchone()
    finally:
        con.close()


def obtener_pedido_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila del pedido con ese id, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute("SELECT * FROM pedidos WHERE id=?", (id,)).fetchone()
    finally:
        con.close()


def cerrar_pedido(id: int) -> None:
    """Cambia el estado de un pedido a 'cerrado'."""
    con = obtener_conexion()
    try:
        con.execute("UPDATE pedidos SET estado='cerrado' WHERE id=?", (id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


# ============================================================
# PEDIDO ÍTEMS
# ============================================================

def agregar_item_pedido(
    pedido_id: int,
    producto_id: int,
    nombre_producto: str,
    cantidad: int,
    precio_unitario: int,
    subtotal: int
) -> int:
    """Agrega un ítem al pedido y retorna su id."""
    con = obtener_conexion()
    try:
        cursor = con.execute(
            """INSERT INTO pedido_items
               (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
        )
        con.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_items_pedido(pedido_id: int) -> list:
    """Retorna todos los ítems de un pedido ordenados por id de inserción."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? ORDER BY id",
            (pedido_id,)
        ).fetchall()
    finally:
        con.close()


def actualizar_cantidad_item(id: int, cantidad: int, subtotal: int) -> None:
    """Actualiza la cantidad y el subtotal calculado de un ítem de pedido."""
    con = obtener_conexion()
    try:
        con.execute(
            "UPDATE pedido_items SET cantidad=?, subtotal=? WHERE id=?",
            (cantidad, subtotal, id)
        )
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def eliminar_item_pedido(id: int) -> None:
    """Elimina un ítem de pedido por su id."""
    con = obtener_conexion()
    try:
        con.execute("DELETE FROM pedido_items WHERE id=?", (id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


# ============================================================
# FACTURAS — contador atómico y transacción completa
# ============================================================

def _siguiente_numero_factura_tx(con: sqlite3.Connection, fecha: str) -> str:
    """
    Genera y reserva el siguiente número de factura para una fecha usando
    el contador atómico de contador_facturas.
    Debe ejecutarse dentro de una transacción ya iniciada (BEGIN explícito).
    Retorna el número en formato 'FAC-YYYYMMDD-NNN'.
    """
    con.execute(
        """INSERT INTO contador_facturas (fecha, ultimo_numero) VALUES (?, 1)
           ON CONFLICT(fecha) DO UPDATE SET ultimo_numero = ultimo_numero + 1""",
        (fecha,)
    )
    numero = con.execute(
        "SELECT ultimo_numero FROM contador_facturas WHERE fecha=?", (fecha,)
    ).fetchone()[0]
    fecha_compacta = fecha.replace('-', '')
    return f"FAC-{fecha_compacta}-{numero:03d}"


def registrar_factura_completa(
    pedido_id: int,
    mesa_id: int,
    fecha: str,
    hora: str,
    total: int,
    descuento: int,
    metodo_pago: str,
    detalles: list,
    es_parcial: int = 0,
    grupo_division: Optional[str] = None
) -> tuple:
    """
    Registra una factura completa en una sola transacción atómica:
      1. Genera y reserva el número de factura (FAC-YYYYMMDD-NNN).
      2. Inserta la factura en facturas.
      3. Inserta cada renglón en factura_detalles.
    Retorna (id_factura, numero_factura).

    detalles: lista de dicts con claves:
        producto_id, nombre_producto, cantidad, precio_unitario, subtotal
    """
    con = obtener_conexion()
    try:
        con.execute("BEGIN")
        numero = _siguiente_numero_factura_tx(con, fecha)
        cursor = con.execute(
            """INSERT INTO facturas
               (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
                metodo_pago, es_parcial, grupo_division)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
             metodo_pago, es_parcial, grupo_division)
        )
        factura_id = cursor.lastrowid
        for detalle in detalles:
            con.execute(
                """INSERT INTO factura_detalles
                   (factura_id, producto_id, nombre_producto,
                    cantidad, precio_unitario, subtotal)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    factura_id,
                    detalle['producto_id'],
                    detalle['nombre_producto'],
                    detalle['cantidad'],
                    detalle['precio_unitario'],
                    detalle['subtotal'],
                )
            )
        con.commit()
        return factura_id, numero
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_factura_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila de la factura con ese id, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute("SELECT * FROM facturas WHERE id=?", (id,)).fetchone()
    finally:
        con.close()


def obtener_facturas_por_fecha(fecha: str) -> list:
    """Retorna todas las facturas de una fecha ordenadas por hora."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM facturas WHERE fecha=? ORDER BY hora", (fecha,)
        ).fetchall()
    finally:
        con.close()


def obtener_facturas_mes_pagina(
    anio: int, mes: int, pagina: int = 1, por_pagina: int = 50
) -> list:
    """
    Retorna una página de facturas de un mes/año, ordenadas por fecha y hora.
    pagina es 1-indexado.
    """
    prefijo = f"{anio:04d}-{mes:02d}-%"
    offset = (pagina - 1) * por_pagina
    con = obtener_conexion()
    try:
        return con.execute(
            """SELECT * FROM facturas WHERE fecha LIKE ?
               ORDER BY fecha, hora LIMIT ? OFFSET ?""",
            (prefijo, por_pagina, offset)
        ).fetchall()
    finally:
        con.close()


def obtener_total_facturas_mes(anio: int, mes: int) -> int:
    """Retorna el conteo de facturas de un mes/año para calcular páginas."""
    prefijo = f"{anio:04d}-{mes:02d}-%"
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT COUNT(*) FROM facturas WHERE fecha LIKE ?", (prefijo,)
        ).fetchone()[0]
    finally:
        con.close()


def anular_factura(id: int) -> None:
    """Cambia el estado de una factura a 'anulada'."""
    con = obtener_conexion()
    try:
        con.execute("UPDATE facturas SET estado='anulada' WHERE id=?", (id,))
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_detalles_factura(factura_id: int) -> list:
    """Retorna todos los renglones de factura_detalles de una factura."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM factura_detalles WHERE factura_id=? ORDER BY id",
            (factura_id,)
        ).fetchall()
    finally:
        con.close()


# ============================================================
# REPORTES — resúmenes de ventas para reporte_service
# ============================================================

def obtener_resumen_ventas_dia(fecha: str) -> sqlite3.Row:
    """
    Retorna total_ventas y numero_facturas de las facturas pagadas de un día.
    Usado por reporte_service para generar el cierre diario.
    """
    con = obtener_conexion()
    try:
        return con.execute(
            """SELECT COALESCE(SUM(total - descuento), 0) AS total_ventas,
                      COUNT(*) AS numero_facturas
               FROM facturas WHERE fecha=? AND estado='pagada'""",
            (fecha,)
        ).fetchone()
    finally:
        con.close()


def obtener_resumen_ventas_mes(anio: int, mes: int) -> sqlite3.Row:
    """
    Retorna total_ventas y numero_facturas de las facturas pagadas de un mes.
    Usado por reporte_service para el reporte mensual.
    """
    prefijo = f"{anio:04d}-{mes:02d}-%"
    con = obtener_conexion()
    try:
        return con.execute(
            """SELECT COALESCE(SUM(total - descuento), 0) AS total_ventas,
                      COUNT(*) AS numero_facturas
               FROM facturas WHERE fecha LIKE ? AND estado='pagada'""",
            (prefijo,)
        ).fetchone()
    finally:
        con.close()


# ============================================================
# CIERRES DIARIOS
# ============================================================

def existe_cierre_diario(fecha: str) -> bool:
    """Retorna True si ya existe un cierre registrado para esa fecha."""
    con = obtener_conexion()
    try:
        fila = con.execute(
            "SELECT id FROM cierres_diarios WHERE fecha=?", (fecha,)
        ).fetchone()
        return fila is not None
    finally:
        con.close()


def crear_cierre_diario(
    fecha: str, total_ventas: int, numero_facturas: int, generado_en: str
) -> int:
    """Inserta un registro de cierre diario y retorna su id."""
    con = obtener_conexion()
    try:
        cursor = con.execute(
            """INSERT INTO cierres_diarios (fecha, total_ventas, numero_facturas, generado_en)
               VALUES (?, ?, ?, ?)""",
            (fecha, total_ventas, numero_facturas, generado_en)
        )
        con.commit()
        return cursor.lastrowid
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_cierre_por_fecha(fecha: str) -> Optional[sqlite3.Row]:
    """Retorna el cierre diario de una fecha, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM cierres_diarios WHERE fecha=?", (fecha,)
        ).fetchone()
    finally:
        con.close()


# ============================================================
# ALERTAS
# ============================================================

def registrar_alerta(tipo: str, fecha: str) -> None:
    """
    Registra una alerta si no existe una del mismo tipo y fecha.
    Usa INSERT OR IGNORE para ser idempotente (no duplica la alerta).
    """
    con = obtener_conexion()
    try:
        con.execute(
            "INSERT OR IGNORE INTO alertas (tipo, fecha) VALUES (?, ?)",
            (tipo, fecha)
        )
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()


def obtener_alerta(tipo: str, fecha: str) -> Optional[sqlite3.Row]:
    """Retorna una alerta por tipo y fecha, o None si no existe."""
    con = obtener_conexion()
    try:
        return con.execute(
            "SELECT * FROM alertas WHERE tipo=? AND fecha=?", (tipo, fecha)
        ).fetchone()
    finally:
        con.close()


def marcar_alerta_mostrada(tipo: str, fecha: str) -> None:
    """Marca una alerta como ya mostrada al usuario."""
    con = obtener_conexion()
    try:
        con.execute(
            "UPDATE alertas SET mostrada=1 WHERE tipo=? AND fecha=?",
            (tipo, fecha)
        )
        con.commit()
    except sqlite3.Error:
        con.rollback()
        raise
    finally:
        con.close()
