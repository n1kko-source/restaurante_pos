-- ============================================================
-- schema.sql — Sistema POS Restaurante
-- Contrato único de base de datos (ver .cursorrules: schema.sql
-- es la fuente de verdad; el código se ajusta a él, no al revés)
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ADVERTENCIA — validación de fechas/horas:
-- Los CHECK con LIKE validan FORMATO ('____-__-__' / '__:__:__') pero
-- no validan RANGOS SEMÁNTICOS. Un valor como '2026-99-61' o '25:61:99'
-- pasa los CHECK sin error. La validación de rangos reales (horas 00-23,
-- minutos/segundos 00-59) es responsabilidad OBLIGATORIA de hora_service.py
-- y facturacion_service.py antes de cada INSERT/UPDATE.

-- ============================================================
-- USUARIOS Y ROLES
-- ============================================================
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    usuario TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL CHECK(rol IN ('cajero', 'supervisor', 'administrador'))
);

-- ============================================================
-- CATÁLOGO
-- ============================================================
CREATE TABLE categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL
);

CREATE TABLE productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id INTEGER NOT NULL REFERENCES categorias(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    nombre TEXT NOT NULL,
    precio INTEGER NOT NULL CHECK(precio >= 0),      -- pesos COP enteros
    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
    activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0, 1))
);

-- ============================================================
-- MESAS DEL SALÓN
-- ============================================================
-- Vocabulario único de estado: 'libre' | 'ocupada' | 'esperando_pago'
-- La UI traduce: 'ocupada' -> "Con pedido", 'esperando_pago' -> "Esperando factura"
CREATE TABLE mesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero INTEGER UNIQUE NOT NULL,
    estado TEXT NOT NULL DEFAULT 'libre'
        CHECK(estado IN ('libre', 'ocupada', 'esperando_pago')),
    num_personas INTEGER NOT NULL DEFAULT 0 CHECK(num_personas >= 0),
    CHECK((estado = 'libre' AND num_personas = 0) OR (estado IN ('ocupada', 'esperando_pago') AND num_personas >= 0))
);

-- ============================================================
-- PEDIDOS
-- ============================================================
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id INTEGER NOT NULL REFERENCES mesas(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    fecha TEXT NOT NULL CHECK(fecha LIKE '____-__-__'),   -- ISO: 'YYYY-MM-DD'
    hora TEXT NOT NULL CHECK(hora LIKE '__:__:__'),    -- 'HH:MM:SS' 24h
    estado TEXT NOT NULL DEFAULT 'abierto'
        CHECK(estado IN ('abierto', 'cerrado'))
);

-- Solo un pedido abierto por mesa a la vez
CREATE UNIQUE INDEX idx_pedido_abierto_unico
    ON pedidos(mesa_id)
    WHERE estado = 'abierto';

CREATE TABLE pedido_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    nombre_producto TEXT NOT NULL,   -- copia histórica
    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
    precio_unitario INTEGER NOT NULL CHECK(precio_unitario >= 0),
    subtotal INTEGER NOT NULL CHECK(subtotal >= 0),
    CHECK(subtotal = cantidad * precio_unitario)
);

-- ============================================================
-- FACTURACIÓN
-- ============================================================
-- Numeración FAC-YYYYMMDD-NNN vía contador (evita condición de carrera
-- de calcular MAX(numero)+1 en aplicación)
CREATE TABLE contador_facturas (
    fecha TEXT PRIMARY KEY CHECK(fecha LIKE '____-__-__'),           -- 'YYYY-MM-DD'
    ultimo_numero INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE facturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT UNIQUE NOT NULL CHECK(length(numero) = 16 AND numero LIKE 'FAC-____________'),          -- ej: FAC-20260620-001
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    mesa_id INTEGER NOT NULL REFERENCES mesas(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    fecha TEXT NOT NULL CHECK(fecha LIKE '____-__-__'),
    hora TEXT NOT NULL CHECK(hora LIKE '__:__:__'),
    total INTEGER NOT NULL CHECK(total >= 0),
    descuento INTEGER NOT NULL DEFAULT 0 CHECK(descuento >= 0),
    metodo_pago TEXT NOT NULL DEFAULT 'efectivo'
        CHECK(metodo_pago IN ('efectivo', 'billetera_digital')),
    estado TEXT NOT NULL DEFAULT 'pagada'
        CHECK(estado IN ('pagada', 'anulada')),
    es_parcial INTEGER NOT NULL DEFAULT 0 CHECK(es_parcial IN (0, 1)),
    grupo_division TEXT,   -- formato: split-{pedido_id}-{timestamp_unix}
    CHECK((es_parcial = 0 AND grupo_division IS NULL) OR (es_parcial = 1 AND grupo_division IS NOT NULL))
);

CREATE TABLE factura_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factura_id INTEGER NOT NULL REFERENCES facturas(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    nombre_producto TEXT NOT NULL,   -- copia histórica
    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
    precio_unitario INTEGER NOT NULL CHECK(precio_unitario >= 0),
    subtotal INTEGER NOT NULL CHECK(subtotal >= 0),
    CHECK(subtotal = cantidad * precio_unitario)
);

-- ============================================================
-- CIERRES DIARIOS
-- ============================================================
-- El cierre MENSUAL se calcula desde facturas; no tiene tabla propia.
CREATE TABLE cierres_diarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT UNIQUE NOT NULL CHECK(fecha LIKE '____-__-__'),
    total_ventas INTEGER NOT NULL CHECK(total_ventas >= 0),
    numero_facturas INTEGER NOT NULL CHECK(numero_facturas >= 0),
    generado_en TEXT NOT NULL   -- timestamp ISO completo
);

-- ============================================================
-- ALERTAS
-- ============================================================
CREATE TABLE alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    fecha TEXT NOT NULL CHECK(fecha LIKE '____-__-__'),
    mostrada INTEGER NOT NULL DEFAULT 0 CHECK(mostrada IN (0, 1)),
    UNIQUE(tipo, fecha)   -- evita duplicar la misma alerta el mismo día
);

-- ============================================================
-- ÍNDICES
-- ============================================================
CREATE INDEX idx_facturas_fecha ON facturas(fecha);
CREATE INDEX idx_pedidos_fecha ON pedidos(fecha);
CREATE INDEX idx_pedido_items_producto ON pedido_items(producto_id);
CREATE INDEX idx_factura_detalles_producto ON factura_detalles(producto_id);
CREATE INDEX idx_alertas_tipo_fecha ON alertas(tipo, fecha);
CREATE INDEX idx_facturas_grupo_division ON facturas(grupo_division);

-- ============================================================
-- DATOS SEMILLA
-- ============================================================
-- 11 mesas, distribución en L invertida (4 filas x 3 columnas, sin
-- la celda [fila 4, columna 1])
INSERT INTO mesas (numero, estado, num_personas) VALUES
    (1, 'libre', 0), (2, 'libre', 0), (3, 'libre', 0),
    (4, 'libre', 0), (5, 'libre', 0), (6, 'libre', 0),
    (7, 'libre', 0), (8, 'libre', 0), (9, 'libre', 0),
    (10, 'libre', 0), (11, 'libre', 0);

-- NOTA: el usuario administrador inicial NO se inserta aquí porque su
-- password_hash requiere bcrypt generado en runtime (Python), no en SQL
-- estático. Se inserta desde init_db() en db_manager.py, de forma
-- idempotente (solo si la tabla usuarios está vacía).