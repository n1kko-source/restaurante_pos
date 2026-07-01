"""Gestión de conexión SQLite y ejecución de queries CRUD.

Toda la SQL del sistema vive aquí. Los servicios llaman estas funciones;
nunca importan sqlite3 directamente ni ejecutan queries propias.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import bcrypt

from config import (
    RUTA_DB,
    PAGINA_TAMANO_DEFAULT,
    ADMIN_INICIAL_USUARIO,
    ADMIN_INICIAL_PASSWORD,
)

RUTA_SCHEMA = Path(__file__).parent / "schema.sql"

# Conjunto de tablas que deben existir tras init_db().
# Usado para detectar BD parcial o corrupta y re-ejecutar el schema.
_TABLAS_CONTRATO = {
    "usuarios", "categorias", "productos", "mesas", "pedidos",
    "pedido_items", "contador_facturas", "facturas", "factura_detalles",
    "cierres_diarios", "alertas", "cola_impresion",
}


# ============================================================
# CONEXIÓN E INFRAESTRUCTURA INTERNA
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


@contextmanager
def _conexion(escritura: bool = False):
    """
    Context manager interno: abre conexión, cede control y la cierra.
    Si escritura=True hace commit al salir sin error, o rollback ante cualquier
    excepción (incluyendo ValueError de validaciones de negocio).
    Uso exclusivo de las funciones de este módulo.
    """
    con = obtener_conexion()
    try:
        yield con
        if escritura:
            con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """
    Inicializa la BD de forma idempotente:
      - Crea el directorio padre si no existe (necesario en PyInstaller).
      - Ejecuta schema.sql si faltan tablas del contrato (BD nueva o parcial).
      - Inserta el usuario administrador inicial (hash bcrypt) si la tabla
        usuarios está vacía.
    Contraseña inicial: ver config.py (ADMIN_INICIAL_PASSWORD).
    """
    RUTA_DB.parent.mkdir(parents=True, exist_ok=True)
    con = obtener_conexion()
    try:
        tablas_existentes = {
            fila[0]
            for fila in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        faltantes = _TABLAS_CONTRATO - tablas_existentes
        if not tablas_existentes:
            schema = RUTA_SCHEMA.read_text(encoding="utf-8")
            con.executescript(schema)
        elif faltantes:
            _aplicar_migraciones(con, faltantes)

        _migrar_columnas_facturas(con)
        _migrar_metodos_pago_facturas(con)

        if con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            password_hash = bcrypt.hashpw(
                ADMIN_INICIAL_PASSWORD.encode("utf-8"),
                bcrypt.gensalt(),
            ).decode("utf-8")
            con.execute(
                "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (?, ?, ?, ?)",
                ("Administrador", ADMIN_INICIAL_USUARIO, password_hash, "administrador"),
            )
            con.commit()
    finally:
        con.close()


def _aplicar_migraciones(
    con: sqlite3.Connection, tablas_faltantes: Optional[set] = None
) -> None:
    """Crea tablas nuevas en BD existentes sin re-ejecutar el schema completo."""
    if tablas_faltantes is None:
        tablas_faltantes = {"cola_impresion"}
    if "cola_impresion" in tablas_faltantes:
        con.execute(
            """CREATE TABLE IF NOT EXISTS cola_impresion (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   factura_id INTEGER NOT NULL UNIQUE REFERENCES facturas(id)
                       ON DELETE CASCADE ON UPDATE CASCADE,
                   error_ultimo TEXT,
                   intentos INTEGER NOT NULL DEFAULT 1 CHECK(intentos >= 1),
                   registrado_en TEXT NOT NULL
               )"""
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_cola_impresion_factura "
            "ON cola_impresion(factura_id)"
        )
    con.commit()


def _migrar_columnas_facturas(con: sqlite3.Connection) -> None:
    """Añade columnas de comprador a facturas en bases de datos existentes."""
    columnas = {
        fila[1]
        for fila in con.execute("PRAGMA table_info(facturas)").fetchall()
    }
    if not columnas:
        return
    if "comprador_nombre" not in columnas:
        con.execute(
            "ALTER TABLE facturas ADD COLUMN comprador_nombre TEXT NOT NULL DEFAULT ''"
        )
    if "comprador_identificacion" not in columnas:
        con.execute(
            "ALTER TABLE facturas ADD COLUMN comprador_identificacion TEXT NOT NULL DEFAULT ''"
        )
    con.commit()


def _migrar_metodos_pago_facturas(con: sqlite3.Connection) -> None:
    """Amplía el CHECK de metodo_pago en facturas existentes."""
    fila = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='facturas'"
    ).fetchone()
    if not fila or not fila[0]:
        return
    if "daviplata" in fila[0]:
        return

    con.executescript(
        """
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;

        CREATE TABLE facturas_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL
                CHECK(length(numero) = 16 AND numero LIKE 'FAC-____________'),
            pedido_id INTEGER NOT NULL REFERENCES pedidos(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            mesa_id INTEGER NOT NULL REFERENCES mesas(id)
                ON DELETE RESTRICT ON UPDATE CASCADE,
            fecha TEXT NOT NULL CHECK(fecha LIKE '____-__-__'),
            hora TEXT NOT NULL CHECK(hora LIKE '__:__:__'),
            total INTEGER NOT NULL CHECK(total >= 0),
            descuento INTEGER NOT NULL DEFAULT 0 CHECK(descuento >= 0),
            metodo_pago TEXT NOT NULL DEFAULT 'efectivo'
                CHECK(metodo_pago IN ('efectivo', 'daviplata', 'nequi', 'anotar')),
            estado TEXT NOT NULL DEFAULT 'pagada'
                CHECK(estado IN ('pagada', 'anulada')),
            es_parcial INTEGER NOT NULL DEFAULT 0 CHECK(es_parcial IN (0, 1)),
            grupo_division TEXT,
            comprador_nombre TEXT NOT NULL DEFAULT '',
            comprador_identificacion TEXT NOT NULL DEFAULT '',
            CHECK(
                (es_parcial = 0 AND grupo_division IS NULL)
                OR (es_parcial = 1 AND grupo_division IS NOT NULL)
            )
        );

        INSERT INTO facturas_new (
            id, numero, pedido_id, mesa_id, fecha, hora, total, descuento,
            metodo_pago, estado, es_parcial, grupo_division,
            comprador_nombre, comprador_identificacion
        )
        SELECT
            id, numero, pedido_id, mesa_id, fecha, hora, total, descuento,
            CASE metodo_pago
                WHEN 'billetera_digital' THEN 'daviplata'
                ELSE metodo_pago
            END,
            estado, es_parcial, grupo_division,
            comprador_nombre, comprador_identificacion
        FROM facturas;

        DROP TABLE facturas;
        ALTER TABLE facturas_new RENAME TO facturas;

        CREATE INDEX IF NOT EXISTS idx_facturas_fecha ON facturas(fecha);
        CREATE INDEX IF NOT EXISTS idx_facturas_grupo_division
            ON facturas(grupo_division);

        COMMIT;
        PRAGMA foreign_keys=ON;
        """
    )
    con.commit()


# ============================================================
# USUARIOS
# ============================================================

def crear_usuario(nombre: str, usuario: str, password_hash: str, rol: str) -> int:
    """Inserta un nuevo usuario y retorna su id."""
    with _conexion(escritura=True) as con:
        cursor = con.execute(
            "INSERT INTO usuarios (nombre, usuario, password_hash, rol) VALUES (?, ?, ?, ?)",
            (nombre, usuario, password_hash, rol),
        )
        return cursor.lastrowid


def obtener_usuario_por_nombre(usuario: str) -> Optional[sqlite3.Row]:
    """Retorna la fila del usuario con ese nombre de usuario, o None si no existe."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()


def obtener_usuarios_pagina(
    pagina: int = 1,
    por_pagina: int = PAGINA_TAMANO_DEFAULT,
    rol: Optional[str] = None,
) -> list:
    """Retorna una página de usuarios ordenados por nombre. pagina es 1-indexado."""
    pagina = max(1, pagina)
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        if rol is not None:
            return con.execute(
                "SELECT * FROM usuarios WHERE rol = ? ORDER BY nombre LIMIT ? OFFSET ?",
                (rol, por_pagina, offset),
            ).fetchall()
        return con.execute(
            "SELECT * FROM usuarios ORDER BY nombre LIMIT ? OFFSET ?",
            (por_pagina, offset),
        ).fetchall()


def obtener_total_usuarios(rol: Optional[str] = None) -> int:
    """Retorna el conteo total de usuarios para calcular el número de páginas."""
    with _conexion() as con:
        if rol is not None:
            return con.execute(
                "SELECT COUNT(*) FROM usuarios WHERE rol = ?", (rol,)
            ).fetchone()[0]
        return con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]


def obtener_todos_usuarios() -> list:
    """
    Retorna todos los usuarios ordenados por nombre.
    Uso interno (exportación, auditoría). Para Treeview usar obtener_usuarios_pagina.
    """
    with _conexion() as con:
        return con.execute("SELECT * FROM usuarios ORDER BY nombre").fetchall()


def actualizar_usuario(
    id: int, nombre: str, usuario: str, password_hash: str, rol: str
) -> None:
    """Actualiza todos los campos de un usuario existente."""
    with _conexion(escritura=True) as con:
        con.execute(
            "UPDATE usuarios SET nombre=?, usuario=?, password_hash=?, rol=? WHERE id=?",
            (nombre, usuario, password_hash, rol, id),
        )


def eliminar_usuario(id: int) -> None:
    """Elimina un usuario por su id."""
    with _conexion(escritura=True) as con:
        con.execute("DELETE FROM usuarios WHERE id=?", (id,))


# ============================================================
# CATEGORÍAS
# ============================================================

def crear_categoria(nombre: str) -> int:
    """Inserta una nueva categoría y retorna su id."""
    with _conexion(escritura=True) as con:
        cursor = con.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
        return cursor.lastrowid


def obtener_categorias_pagina(
    pagina: int = 1, por_pagina: int = PAGINA_TAMANO_DEFAULT
) -> list:
    """Retorna una página de categorías ordenadas por nombre. pagina es 1-indexado."""
    pagina = max(1, pagina)
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM categorias ORDER BY nombre LIMIT ? OFFSET ?",
            (por_pagina, offset),
        ).fetchall()


def obtener_total_categorias() -> int:
    """Retorna el conteo total de categorías para calcular el número de páginas."""
    with _conexion() as con:
        return con.execute("SELECT COUNT(*) FROM categorias").fetchone()[0]


def obtener_todas_categorias() -> list:
    """
    Retorna todas las categorías ordenadas por nombre.
    Uso interno (selectores en POS/menú). Para Treeview usar obtener_categorias_pagina.
    """
    with _conexion() as con:
        return con.execute("SELECT * FROM categorias ORDER BY nombre").fetchall()


def actualizar_categoria(id: int, nombre: str) -> None:
    """Actualiza el nombre de una categoría."""
    with _conexion(escritura=True) as con:
        con.execute("UPDATE categorias SET nombre=? WHERE id=?", (nombre, id))


def eliminar_categoria(id: int) -> None:
    """
    Elimina una categoría por su id.
    Lanza sqlite3.IntegrityError si tiene productos asociados (ON DELETE RESTRICT).
    """
    with _conexion(escritura=True) as con:
        con.execute("DELETE FROM categorias WHERE id=?", (id,))


# ============================================================
# PRODUCTOS
# ============================================================

def crear_producto(
    categoria_id: int, nombre: str, precio: int, stock: int
) -> int:
    """Inserta un nuevo producto activo y retorna su id."""
    with _conexion(escritura=True) as con:
        cursor = con.execute(
            "INSERT INTO productos (categoria_id, nombre, precio, stock) VALUES (?, ?, ?, ?)",
            (categoria_id, nombre, precio, stock),
        )
        return cursor.lastrowid


def obtener_producto_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila del producto con ese id, o None si no existe."""
    with _conexion() as con:
        return con.execute(
            """SELECT p.*, c.nombre AS nombre_categoria
               FROM productos p JOIN categorias c ON p.categoria_id = c.id
               WHERE p.id=?""",
            (id,),
        ).fetchone()


def obtener_productos_pagina(
    pagina: int = 1,
    por_pagina: int = PAGINA_TAMANO_DEFAULT,
    categoria_id: Optional[int] = None,
    solo_activos: bool = True,
) -> list:
    """
    Retorna una página de productos con JOIN a categorías.
    pagina es 1-indexado. Nunca carga toda la tabla en memoria.
    """
    pagina = max(1, pagina)
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
    with _conexion() as con:
        return con.execute(
            f"""SELECT p.*, c.nombre AS nombre_categoria
                FROM productos p
                JOIN categorias c ON p.categoria_id = c.id
                {where}
                ORDER BY c.nombre, p.nombre
                LIMIT ? OFFSET ?""",
            params,
        ).fetchall()


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
    with _conexion() as con:
        return con.execute(
            f"SELECT COUNT(*) FROM productos {where}", params
        ).fetchone()[0]


def actualizar_producto(
    id: int, categoria_id: int, nombre: str,
    precio: int, stock: int, activo: int,
) -> None:
    """Actualiza todos los campos editables de un producto."""
    with _conexion(escritura=True) as con:
        con.execute(
            "UPDATE productos SET categoria_id=?, nombre=?, precio=?, stock=?, activo=? WHERE id=?",
            (categoria_id, nombre, precio, stock, activo, id),
        )


def obtener_productos_catalogo(termino: Optional[str] = None) -> list:
    """
    Retorna productos activos con JOIN a categorías para el POS.
    termino: filtro opcional por nombre (LIKE case-insensitive).
    Sin paginar: catálogo de menú acotado en operación normal.
    """
    condiciones = ["p.activo = 1"]
    params = []
    if termino:
        condiciones.append("LOWER(p.nombre) LIKE LOWER(?)")
        params.append(f"%{termino}%")
    where = "WHERE " + " AND ".join(condiciones)
    with _conexion() as con:
        return con.execute(
            f"""SELECT p.*, c.nombre AS nombre_categoria
                FROM productos p
                JOIN categorias c ON p.categoria_id = c.id
                {where}
                ORDER BY c.nombre, p.nombre""",
            params,
        ).fetchall()


def desactivar_producto(id: int) -> None:
    """
    Marca un producto como inactivo (activo=0).
    No elimina el registro para preservar el histórico de pedidos y facturas.
    """
    with _conexion(escritura=True) as con:
        con.execute("UPDATE productos SET activo=0 WHERE id=?", (id,))


def actualizar_stock(id: int, nuevo_stock: int) -> None:
    """Actualiza el stock de un producto."""
    with _conexion(escritura=True) as con:
        con.execute("UPDATE productos SET stock=? WHERE id=?", (nuevo_stock, id))


# ============================================================
# MESAS
# ============================================================

def obtener_todas_mesas() -> list:
    """Retorna todas las mesas ordenadas por número. Sin paginar: son 11 filas fijas."""
    with _conexion() as con:
        return con.execute("SELECT * FROM mesas ORDER BY numero").fetchall()


def obtener_mesa_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila de la mesa con ese id, o None si no existe."""
    with _conexion() as con:
        return con.execute("SELECT * FROM mesas WHERE id=?", (id,)).fetchone()


def actualizar_estado_mesa(id: int, estado: str, num_personas: int) -> None:
    """
    Actualiza el estado y número de personas de una mesa.
    El estado debe ser uno de: 'libre', 'ocupada', 'esperando_pago'.
    """
    with _conexion(escritura=True) as con:
        con.execute(
            "UPDATE mesas SET estado=?, num_personas=? WHERE id=?",
            (estado, num_personas, id),
        )


# ============================================================
# PEDIDOS
# ============================================================

def crear_pedido(mesa_id: int, fecha: str, hora: str) -> int:
    """Inserta un pedido nuevo en estado 'abierto' y retorna su id."""
    with _conexion(escritura=True) as con:
        cursor = con.execute(
            "INSERT INTO pedidos (mesa_id, fecha, hora) VALUES (?, ?, ?)",
            (mesa_id, fecha, hora),
        )
        return cursor.lastrowid


def obtener_pedido_abierto_por_mesa(mesa_id: int) -> Optional[sqlite3.Row]:
    """Retorna el pedido en estado 'abierto' de una mesa, o None si no tiene."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM pedidos WHERE mesa_id=? AND estado='abierto'",
            (mesa_id,),
        ).fetchone()


def obtener_pedido_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila del pedido con ese id, o None si no existe."""
    with _conexion() as con:
        return con.execute("SELECT * FROM pedidos WHERE id=?", (id,)).fetchone()


def cerrar_pedido(id: int) -> None:
    """Cambia el estado de un pedido a 'cerrado'."""
    with _conexion(escritura=True) as con:
        con.execute("UPDATE pedidos SET estado='cerrado' WHERE id=?", (id,))


# ============================================================
# PEDIDO ÍTEMS
# ============================================================

def agregar_item_pedido(
    pedido_id: int,
    producto_id: int,
    nombre_producto: str,
    cantidad: int,
    precio_unitario: int,
    subtotal: int,
) -> int:
    """Agrega un ítem al pedido y retorna su id."""
    with _conexion(escritura=True) as con:
        cursor = con.execute(
            """INSERT INTO pedido_items
               (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pedido_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal),
        )
        return cursor.lastrowid


def obtener_items_pedido(pedido_id: int) -> list:
    """Retorna todos los ítems de un pedido ordenados por id. Sin paginar: pedido de 1 mesa."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM pedido_items WHERE pedido_id=? ORDER BY id",
            (pedido_id,),
        ).fetchall()


def obtener_item_pedido_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna un ítem de pedido por su id, o None si no existe."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM pedido_items WHERE id=?", (id,)
        ).fetchone()


def obtener_item_pedido_por_producto(pedido_id: int, producto_id: int) -> Optional[sqlite3.Row]:
    """Retorna el primer ítem del pedido con ese producto, o None."""
    with _conexion() as con:
        return con.execute(
            """SELECT * FROM pedido_items
               WHERE pedido_id=? AND producto_id=?
               ORDER BY id LIMIT 1""",
            (pedido_id, producto_id),
        ).fetchone()


def actualizar_cantidad_item(id: int, cantidad: int) -> None:
    """
    Actualiza la cantidad de un ítem y recalcula el subtotal en BD como
    cantidad * precio_unitario, garantizando el CHECK del schema sin depender
    del llamador para el cálculo.
    """
    with _conexion(escritura=True) as con:
        con.execute(
            "UPDATE pedido_items SET cantidad=?, subtotal=? * precio_unitario WHERE id=?",
            (cantidad, cantidad, id),
        )


def eliminar_item_pedido(id: int) -> None:
    """Elimina un ítem de pedido por su id."""
    with _conexion(escritura=True) as con:
        con.execute("DELETE FROM pedido_items WHERE id=?", (id,))


# ============================================================
# FACTURAS — contador atómico y transacción completa
# ============================================================

def obtener_ultimo_numero_factura(fecha: str) -> int:
    """Retorna el último número de factura reservado para una fecha (0 si no hay)."""
    with _conexion() as con:
        fila = con.execute(
            "SELECT ultimo_numero FROM contador_facturas WHERE fecha=?", (fecha,)
        ).fetchone()
        return fila[0] if fila is not None else 0


def _siguiente_numero_factura_tx(con: sqlite3.Connection, fecha: str) -> str:
    """
    Genera y reserva el siguiente número de factura para una fecha usando
    el contador atómico de contador_facturas.
    Debe ejecutarse dentro de una transacción abierta.
    Retorna el número en formato 'FAC-YYYYMMDD-NNN' (16 chars, máx 999/día).
    Lanza ValueError si se supera el límite operativo de 999 facturas diarias.
    """
    con.execute(
        """INSERT INTO contador_facturas (fecha, ultimo_numero) VALUES (?, 1)
           ON CONFLICT(fecha) DO UPDATE SET ultimo_numero = ultimo_numero + 1""",
        (fecha,),
    )
    numero = con.execute(
        "SELECT ultimo_numero FROM contador_facturas WHERE fecha=?", (fecha,)
    ).fetchone()[0]
    if numero > 999:
        raise ValueError(
            f"Límite diario de facturas alcanzado (999) para {fecha}. "
            "Contacte al administrador del sistema."
        )
    fecha_compacta = fecha.replace("-", "")
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
    grupo_division: Optional[str] = None,
    comprador_nombre: str = "",
    comprador_identificacion: str = "",
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
    with _conexion(escritura=True) as con:
        con.execute("BEGIN")
        numero = _siguiente_numero_factura_tx(con, fecha)
        cursor = con.execute(
            """INSERT INTO facturas
               (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
                metodo_pago, es_parcial, grupo_division,
                comprador_nombre, comprador_identificacion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
             metodo_pago, es_parcial, grupo_division,
             comprador_nombre.strip(), comprador_identificacion.strip()),
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
                    detalle["producto_id"],
                    detalle["nombre_producto"],
                    detalle["cantidad"],
                    detalle["precio_unitario"],
                    detalle["subtotal"],
                ),
            )
        return factura_id, numero


def obtener_factura_por_id(id: int) -> Optional[sqlite3.Row]:
    """Retorna la fila de la factura con ese id, o None si no existe."""
    with _conexion() as con:
        return con.execute("SELECT * FROM facturas WHERE id=?", (id,)).fetchone()


def obtener_facturas_por_fecha_pagina(
    fecha: str, pagina: int = 1, por_pagina: int = PAGINA_TAMANO_DEFAULT
) -> list:
    """Retorna una página de facturas de una fecha, ordenadas por hora. pagina es 1-indexado."""
    pagina = max(1, pagina)
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM facturas WHERE fecha=? ORDER BY hora LIMIT ? OFFSET ?",
            (fecha, por_pagina, offset),
        ).fetchall()


def obtener_total_facturas_fecha(fecha: str) -> int:
    """Retorna el conteo de facturas de una fecha para calcular páginas."""
    with _conexion() as con:
        return con.execute(
            "SELECT COUNT(*) FROM facturas WHERE fecha=?", (fecha,)
        ).fetchone()[0]


def obtener_facturas_por_fecha(fecha: str) -> list:
    """
    Retorna todas las facturas de una fecha ordenadas por hora.
    Uso interno (exportación PDF/Excel). Para Treeview usar obtener_facturas_por_fecha_pagina.
    """
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM facturas WHERE fecha=? ORDER BY hora", (fecha,)
        ).fetchall()


def obtener_facturas_mes_pagina(
    anio: int, mes: int, pagina: int = 1, por_pagina: int = PAGINA_TAMANO_DEFAULT
) -> list:
    """
    Retorna una página de facturas de un mes/año, ordenadas por fecha y hora.
    pagina es 1-indexado.
    """
    pagina = max(1, pagina)
    prefijo = f"{anio:04d}-{mes:02d}-%"
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        return con.execute(
            """SELECT * FROM facturas WHERE fecha LIKE ?
               ORDER BY fecha, hora LIMIT ? OFFSET ?""",
            (prefijo, por_pagina, offset),
        ).fetchall()


def obtener_total_facturas_mes(anio: int, mes: int) -> int:
    """Retorna el conteo de facturas de un mes/año para calcular páginas."""
    prefijo = f"{anio:04d}-{mes:02d}-%"
    with _conexion() as con:
        return con.execute(
            "SELECT COUNT(*) FROM facturas WHERE fecha LIKE ?", (prefijo,)
        ).fetchone()[0]


def anular_factura(id: int) -> None:
    """Cambia el estado de una factura a 'anulada'."""
    with _conexion(escritura=True) as con:
        con.execute("UPDATE facturas SET estado='anulada' WHERE id=?", (id,))


def obtener_detalles_factura(factura_id: int) -> list:
    """Retorna todos los renglones de factura_detalles de una factura."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM factura_detalles WHERE factura_id=? ORDER BY id",
            (factura_id,),
        ).fetchall()


# ============================================================
# REPORTES — resúmenes de ventas para reporte_service
# ============================================================

def obtener_resumen_ventas_dia(fecha: str) -> sqlite3.Row:
    """
    Retorna total_ventas y numero_facturas de las facturas pagadas de un día.
    Agrega en SQL para no cargar filas en memoria (relevante en hardware limitado).
    """
    with _conexion() as con:
        return con.execute(
            """SELECT COALESCE(SUM(total - descuento), 0) AS total_ventas,
                      COUNT(*) AS numero_facturas
               FROM facturas WHERE fecha=? AND estado='pagada'""",
            (fecha,),
        ).fetchone()


def obtener_resumen_ventas_mes(anio: int, mes: int) -> sqlite3.Row:
    """
    Retorna total_ventas y numero_facturas de las facturas pagadas de un mes.
    Agrega en SQL para no cargar filas en memoria.
    """
    prefijo = f"{anio:04d}-{mes:02d}-%"
    with _conexion() as con:
        return con.execute(
            """SELECT COALESCE(SUM(total - descuento), 0) AS total_ventas,
                      COUNT(*) AS numero_facturas
               FROM facturas WHERE fecha LIKE ? AND estado='pagada'""",
            (prefijo,),
        ).fetchone()


def obtener_detalles_ventas_dia_pagina(
    fecha: str,
    pagina: int = 1,
    por_pagina: int = PAGINA_TAMANO_DEFAULT,
) -> list:
    """
    Retorna una página de renglones de facturas pagadas de un día.
    Incluye número de factura, método de pago y comprador; ordenado por factura.
    """
    pagina = max(1, pagina)
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        return con.execute(
            """SELECT f.numero AS factura_numero,
                      f.metodo_pago,
                      f.comprador_nombre,
                      fd.producto_id,
                      fd.nombre_producto,
                      fd.cantidad,
                      fd.subtotal
               FROM factura_detalles fd
               INNER JOIN facturas f ON f.id = fd.factura_id
               WHERE f.fecha = ? AND f.estado = 'pagada'
               ORDER BY f.numero, fd.id
               LIMIT ? OFFSET ?""",
            (fecha, por_pagina, offset),
        ).fetchall()


def obtener_totales_ventas_dia_por_metodo_pago(fecha: str) -> list:
    """Retorna total neto por método de pago para facturas pagadas de un día."""
    with _conexion() as con:
        return con.execute(
            """SELECT metodo_pago,
                      COALESCE(SUM(total - descuento), 0) AS total
               FROM facturas
               WHERE fecha = ? AND estado = 'pagada'
               GROUP BY metodo_pago""",
            (fecha,),
        ).fetchall()


def obtener_cierres_mes_pagina(
    anio: int,
    mes: int,
    pagina: int = 1,
    por_pagina: int = PAGINA_TAMANO_DEFAULT,
) -> list:
    """
    Retorna una página de cierres diarios de un mes/año, ordenados por fecha.
    pagina es 1-indexado.
    """
    prefijo = f"{anio:04d}-{mes:02d}-%"
    pagina = max(1, pagina)
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        return con.execute(
            """SELECT * FROM cierres_diarios
               WHERE fecha LIKE ?
               ORDER BY fecha
               LIMIT ? OFFSET ?""",
            (prefijo, por_pagina, offset),
        ).fetchall()


def obtener_total_cierres_mes(anio: int, mes: int) -> int:
    """Retorna el conteo de cierres diarios registrados en un mes/año."""
    prefijo = f"{anio:04d}-{mes:02d}-%"
    with _conexion() as con:
        return con.execute(
            "SELECT COUNT(*) FROM cierres_diarios WHERE fecha LIKE ?",
            (prefijo,),
        ).fetchone()[0]


# ============================================================
# CIERRES DIARIOS
# ============================================================

def existe_cierre_diario(fecha: str) -> bool:
    """Retorna True si ya existe un cierre registrado para esa fecha."""
    with _conexion() as con:
        return con.execute(
            "SELECT id FROM cierres_diarios WHERE fecha=?", (fecha,)
        ).fetchone() is not None


def crear_cierre_diario(
    fecha: str, total_ventas: int, numero_facturas: int, generado_en: str
) -> int:
    """Inserta un registro de cierre diario y retorna su id."""
    with _conexion(escritura=True) as con:
        cursor = con.execute(
            """INSERT INTO cierres_diarios (fecha, total_ventas, numero_facturas, generado_en)
               VALUES (?, ?, ?, ?)""",
            (fecha, total_ventas, numero_facturas, generado_en),
        )
        return cursor.lastrowid


def obtener_cierre_por_fecha(fecha: str) -> Optional[sqlite3.Row]:
    """Retorna el cierre diario de una fecha, o None si no existe."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM cierres_diarios WHERE fecha=?", (fecha,)
        ).fetchone()


# ============================================================
# COLA DE IMPRESIÓN
# ============================================================

def registrar_cola_impresion(
    factura_id: int, error_ultimo: str, registrado_en: str
) -> None:
    """
    Registra o actualiza una factura pendiente de impresión.
    Incrementa intentos si ya estaba en cola.
    """
    with _conexion(escritura=True) as con:
        existente = con.execute(
            "SELECT id, intentos FROM cola_impresion WHERE factura_id=?",
            (factura_id,),
        ).fetchone()
        if existente is not None:
            con.execute(
                """UPDATE cola_impresion
                   SET error_ultimo=?, intentos=?, registrado_en=?
                   WHERE factura_id=?""",
                (
                    error_ultimo,
                    int(existente["intentos"]) + 1,
                    registrado_en,
                    factura_id,
                ),
            )
        else:
            con.execute(
                """INSERT INTO cola_impresion
                   (factura_id, error_ultimo, intentos, registrado_en)
                   VALUES (?, ?, 1, ?)""",
                (factura_id, error_ultimo, registrado_en),
            )


def quitar_de_cola_impresion(factura_id: int) -> None:
    """Elimina una factura de la cola tras imprimirla correctamente."""
    with _conexion(escritura=True) as con:
        con.execute("DELETE FROM cola_impresion WHERE factura_id=?", (factura_id,))


def obtener_total_cola_impresion() -> int:
    """Retorna cuántas facturas están pendientes de impresión."""
    with _conexion() as con:
        return con.execute("SELECT COUNT(*) FROM cola_impresion").fetchone()[0]


def obtener_cola_impresion_pagina(
    pagina: int = 1, por_pagina: int = PAGINA_TAMANO_DEFAULT
) -> list:
    """
    Retorna una página de la cola con datos de la factura asociada.
    Orden: más antiguas primero (registrado_en ASC).
    """
    pagina = max(1, pagina)
    offset = (pagina - 1) * por_pagina
    with _conexion() as con:
        return con.execute(
            """SELECT c.id AS cola_id, c.factura_id, c.error_ultimo, c.intentos,
                      c.registrado_en, f.numero, f.fecha, f.hora, f.total, f.descuento
               FROM cola_impresion c
               INNER JOIN facturas f ON f.id = c.factura_id
               ORDER BY c.registrado_en ASC
               LIMIT ? OFFSET ?""",
            (por_pagina, offset),
        ).fetchall()


# ============================================================
# ALERTAS
# ============================================================

def registrar_alerta(tipo: str, fecha: str) -> None:
    """
    Registra una alerta si no existe una del mismo tipo y fecha.
    Usa INSERT OR IGNORE para ser idempotente (no duplica la alerta).
    """
    with _conexion(escritura=True) as con:
        con.execute(
            "INSERT OR IGNORE INTO alertas (tipo, fecha) VALUES (?, ?)",
            (tipo, fecha),
        )


def obtener_alerta(tipo: str, fecha: str) -> Optional[sqlite3.Row]:
    """Retorna una alerta por tipo y fecha, o None si no existe."""
    with _conexion() as con:
        return con.execute(
            "SELECT * FROM alertas WHERE tipo=? AND fecha=?", (tipo, fecha)
        ).fetchone()


def marcar_alerta_mostrada(tipo: str, fecha: str) -> None:
    """Marca una alerta como ya mostrada al usuario."""
    with _conexion(escritura=True) as con:
        con.execute(
            "UPDATE alertas SET mostrada=1 WHERE tipo=? AND fecha=?",
            (tipo, fecha),
        )
