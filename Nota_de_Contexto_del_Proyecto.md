# Nota de Contexto del Proyecto — Sistema POS Restaurante
 
## Descripción general
 
Sistema de facturación y contabilidad offline para restaurante. Desarrollado en Python, diseñado para correr en hardware limitado (HP Pavilion dv4, Windows Vista Basic) sin depender de ningún servicio en red. Todo funciona de forma 100% local.
 
---
 
## Hardware y entorno objetivo
 
- **Equipo:** HP Pavilion dv4 (Core 2 Duo, 2–4 GB RAM)
- **Sistema operativo:** Windows Vista Basic
- **Conexión a internet:** Ninguna — el sistema es completamente offline
- **Impresora:** Térmica Colpos (protocolo ESC/POS, conexión serial COM o USB)
- **Entorno de desarrollo:** Cursor IDE (basado en VS Code)
---
 
## Stack tecnológico
 
| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.9 |
| UI principal | CustomTkinter 5.2.2 |
| Tablas de datos | `ttk.Treeview` nativo (rendimiento) |
| Base de datos | SQLite 3 (archivo local `restaurante.db`) |
| Impresora térmica | `python-escpos` 3.1 |
| Exportar PDF | `reportlab` 4.1.0 |
| Exportar Excel | `openpyxl` 3.1.2 |
| Contraseñas | `bcrypt` 4.1.2 |
| Distribución | PyInstaller → `.exe` standalone |
 
### `requirements.txt`
```
customtkinter==5.2.2
python-escpos==3.1
reportlab==4.1.0
openpyxl==3.1.2
bcrypt==4.1.2
```
 
---
 
## Arquitectura en capas
 
```
[ Inicio de sesión + verificación de rol ]
            ↓
[ Capa de presentación — CustomTkinter ]
  Ventanas por rol: POS, Mesas, Menú, Inventario, Reportes, Usuarios
            ↓
[ Capa de lógica de negocio ]
  auth_service / mesa_service / facturacion_service / inventario_service / reporte_service / hora_service
            ↓
[ Capa de datos — SQLite ]
  Tablas: usuarios, productos, categorias, mesas, pedidos, pedido_items,
          facturas, factura_detalles, cierres_diarios, alertas
            ↓
[ Servicios del sistema ]
  Impresora Colpos ESC/POS | Exportar PDF | Exportar Excel | Hora local
```
 
---
 
## Roles de usuario
 
Tres niveles de acceso controlados por decorador `@requiere_rol` en cada ventana:
 
| Rol | Permisos |
|---|---|
| **Cajero** | Mapa de mesas, POS, generar facturas, imprimir recibos, ver menú |
| **Supervisor** | Todo lo anterior + gestión de menú, inventario, reportes del día |
| **Administrador** | Todo lo anterior + cierres mensuales, gestión de usuarios, configuración del sistema, exportar reportes |
 
Los roles y contraseñas (hash bcrypt) se almacenan en la tabla `usuarios` de SQLite.
 
---
 
## Base de datos — tablas principales (actualizado — schema cerrado)

> **Nota de versión:** esta sección reemplaza el DDL preliminar original.
> Decisiones de diseño cerradas tras la fase de Análisis Arquitectónico
> (foreign keys, vocabulario de estados, dinero en COP, numeración de
> facturas, reparto de división de cuenta). `schema.sql` es el contrato
> único — si el código implementado entra en conflicto con esta sección,
> se corrige el código, no el schema, salvo aprobación explícita.

### Convenciones generales

- **Dinero:** `INTEGER`, pesos colombianos (COP) enteros. No se usan
  centavos — el peso es la unidad atómica real en Colombia, por lo que
  no hay subdivisión que representar. Evita errores de redondeo de punto
  flotante en sumas repetidas (división de cuenta, totales acumulados).
- **Fechas/horas:** `fecha` en ISO `'YYYY-MM-DD'`, `hora` en `'HH:MM:SS'`
  formato 24h.
- **Enums:** todos los campos de tipo "enum" llevan `CHECK` en BD además
  de validación en `services/` (defensa en profundidad).
- **Foreign keys:** `PRAGMA foreign_keys = ON` activo en cada conexión
  (no es persistente en el archivo `.db`, debe activarse en
  `obtener_conexion()` de `db_manager.py`).
- **Modo journal:** `WAL`, por resiliencia ante cierre abrupto del proceso
  (relevante en el hardware/SO objetivo).

### DDL completo

```sql
-- ============================================================
-- schema.sql — Sistema POS Restaurante
-- Contrato único de base de datos (ver .cursorrules: schema.sql
-- es la fuente de verdad; el código se ajusta a él, no al revés)
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

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
    num_personas INTEGER NOT NULL DEFAULT 0 CHECK(num_personas >= 0)
);

-- ============================================================
-- PEDIDOS
-- ============================================================
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mesa_id INTEGER NOT NULL REFERENCES mesas(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    fecha TEXT NOT NULL,   -- ISO: 'YYYY-MM-DD'
    hora TEXT NOT NULL,    -- 'HH:MM:SS' 24h
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
    subtotal INTEGER NOT NULL CHECK(subtotal >= 0)
);

-- ============================================================
-- FACTURACIÓN
-- ============================================================
-- Numeración FAC-YYYYMMDD-NNN vía contador (evita condición de carrera
-- de calcular MAX(numero)+1 en aplicación)
CREATE TABLE contador_facturas (
    fecha TEXT PRIMARY KEY,           -- 'YYYY-MM-DD'
    ultimo_numero INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE facturas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT UNIQUE NOT NULL,          -- ej: FAC-20260620-001
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    mesa_id INTEGER NOT NULL REFERENCES mesas(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    total INTEGER NOT NULL CHECK(total >= 0),
    descuento INTEGER NOT NULL DEFAULT 0 CHECK(descuento >= 0),
    metodo_pago TEXT NOT NULL DEFAULT 'efectivo'
        CHECK(metodo_pago IN ('efectivo', 'billetera_digital')),
    estado TEXT NOT NULL DEFAULT 'pagada'
        CHECK(estado IN ('pagada', 'anulada')),
    es_parcial INTEGER NOT NULL DEFAULT 0 CHECK(es_parcial IN (0, 1)),
    grupo_division TEXT   -- formato: split-{pedido_id}-{timestamp_unix}
);

CREATE TABLE factura_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factura_id INTEGER NOT NULL REFERENCES facturas(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    producto_id INTEGER NOT NULL REFERENCES productos(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    nombre_producto TEXT NOT NULL,   -- copia histórica
    cantidad INTEGER NOT NULL CHECK(cantidad > 0),
    precio_unitario INTEGER NOT NULL CHECK(precio_unitario >= 0),
    subtotal INTEGER NOT NULL CHECK(subtotal >= 0)
);

-- ============================================================
-- CIERRES DIARIOS
-- ============================================================
-- El cierre MENSUAL se calcula desde facturas; no tiene tabla propia.
CREATE TABLE cierres_diarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT UNIQUE NOT NULL,
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
    fecha TEXT NOT NULL,
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
```

### Regla de negocio asociada — reparto de residuos en división de cuenta

Cuando un ítem marcado "Todos" se divide en partes iguales entre N
personas, la suma de las partes individuales debe ser **exactamente**
igual al total (sin perder ni sobrar pesos por redondeo). Regla:

1. `parte_base = total // num_personas` (división entera).
2. `residuo = total - (parte_base * num_personas)`.
3. Las primeras `residuo` personas (en el orden en que fueron asignadas)
   pagan `parte_base + 1`; el resto paga `parte_base`.

Esta lógica vive en `facturacion_service.py`, no en el schema ni en
`db_manager.py`:

```python
def calcular_division_partes_iguales(total: int, num_personas: int) -> list[int]:
    """
    Reparte un monto total en partes enteras iguales, asignando el residuo
    a las primeras posiciones de la lista para que la suma sea exacta.
    Retorna una lista de N montos en pesos enteros (COP).
    """
    parte_base = total // num_personas
    residuo = total - (parte_base * num_personas)
    return [parte_base + 1 if i < residuo else parte_base for i in range(num_personas)]
```
 
## Módulo de mesas — ventana_mesas.py
 
### Diseño visual
El salón tiene forma de **L invertida** con 11 mesas distribuidas en una cuadrícula de 4 filas × 3 columnas. La celda inferior izquierda (fila 4, columna 1) está vacía por la geometría del local.
 
```
Distribución en plano:
  [ 1 ]  [ 2 ]  [ 3 ]
  [ 4 ]  [ 5 ]  [ 6 ]
  [ 7 ]  [ 8 ]  [ 9 ]
         [10 ]  [11 ]
```
 
### Estados de mesa
Cada mesa puede estar en uno de tres estados:
 
| Estado | Color | Significado operativo |
|---|---|---|
| **Libre** | Gris neutro | Sin pedido activo, disponible |
| **Con pedido** | Verde | Pedido abierto en curso |
| **Esperando factura** | Ámbar | Cliente listo para pagar |
 
### Panel lateral de detalle
Al seleccionar una mesa, el panel lateral muestra:
- Número de mesa y estado actual
- Lista de ítems del pedido con cantidades y subtotales
- Total acumulado
- Botones de acción según el estado
### Acciones por estado
 
**Mesa libre:**
- Abrir pedido nuevo → activa la mesa y abre el POS
**Mesa con pedido:**
- Generar factura → cambia estado a "Esperando factura"
- Agregar ítem → regresa al POS con el pedido activo
- Dividir cuenta → abre el módulo de división
**Mesa esperando factura:**
- Imprimir factura → envía a impresora Colpos y libera la mesa
- Dividir cuenta → abre el módulo de división
### Módulo de dividir cuenta
Permite repartir el pedido entre 2 a 8 personas antes de imprimir:
 
1. El cajero selecciona el número de personas
2. Asigna cada ítem a una persona específica o marca "Todos" para repartir en partes iguales
3. El sistema calcula el total individual de cada persona
4. Se generan facturas independientes, cada una con su propio número de serie
5. Las facturas del mismo split comparten el campo `grupo_division` para trazabilidad contable
**Regla de negocio:** los ítems marcados como "Todos" se dividen en partes iguales entre el número de personas. Los ítems asignados a una persona específica van 100% a esa factura.
 
---
 
## Módulos especiales
 
### Alerta de inventario dominical
- Al iniciar sesión, el sistema lee `datetime.now()` del reloj del sistema.
- Si es **domingo después de las 18:00**, lanza una alerta visual pidiendo revisar el inventario.
- Se registra en la tabla `alertas` para no repetirla si se reabre el programa el mismo día.
### Gestión de fecha/hora offline
- El sistema usa el reloj interno de Windows (se mantiene aunque no haya internet, via batería CMOS).
- La pantalla de login **siempre muestra la fecha y hora actual** detectada.
- El Administrador puede corregir la hora del sistema desde el panel de configuración (usando `subprocess` para llamar al ajuste de hora de Windows) si nota desincronización.
- Todas las facturas guardan su timestamp en el momento de creación.
### Impresora térmica Colpos (ESC/POS)
- Conexión por puerto serial COM o USB.
- Configuración centralizada en `config.py`:
```python
IMPRESORA = {
    "tipo": "serial",       # "serial" | "usb"
    "puerto": "COM3",
    "baudrate": 9600,
    "ancho_papel": 40       # 32 para papel 58mm, 48 para 80mm
}
```
 
### Reportes
- **PDF** (ReportLab): documento formal con encabezado del restaurante, tabla de ventas, totales. Ideal para archivar o imprimir.
- **Excel** (openpyxl): hoja con datos crudos + fórmulas de suma. Ideal para análisis adicional.
- Ambos disponibles desde la ventana de reportes con botones separados: `Exportar PDF` / `Exportar Excel`.
- Tipos de reporte: **Diario** (ventas del día) y **Mensual** (consolidado del mes).
---
 
## Estructura del proyecto
 
```
restaurante_pos/
├── main.py
├── config.py                      # Puerto COM, ancho papel, rutas de exportación
├── requirements.txt
│
├── database/
│   ├── db_manager.py              # Conexión y queries SQLite
│   ├── schema.sql                 # Definición de todas las tablas
│   └── restaurante.db             # Archivo generado en runtime
│
├── models/
│   ├── usuario.py
│   ├── producto.py
│   ├── mesa.py
│   ├── pedido.py
│   ├── factura.py
│   └── cierre.py
│
├── services/
│   ├── auth_service.py            # Login, decorador @requiere_rol
│   ├── mesa_service.py            # Estados de mesa, apertura/cierre de pedidos
│   ├── facturacion_service.py     # Cálculo de totales, descuentos, numeración, división
│   ├── inventario_service.py      # Stock, alertas dominicales
│   ├── reporte_service.py         # Consolidación diaria y mensual
│   └── hora_service.py            # datetime local + corrección manual
│
├── ui/
│   ├── ventana_login.py           # Muestra hora actual, verifica credenciales
│   ├── ventana_principal.py       # Barra lateral con opciones según rol
│   ├── ventana_mesas.py           # Mapa visual del salón — módulo de entrada al POS
│   ├── ventana_pos.py             # Punto de venta vinculado a mesa activa
│   ├── ventana_menu.py            # Gestión de productos y categorías
│   ├── ventana_inventario.py      # Stock y movimientos
│   ├── ventana_reportes.py        # Botones Exportar PDF / Exportar Excel
│   └── ventana_usuarios.py        # Solo Administrador
│
├── printing/
│   ├── colpos_printer.py          # Integración python-escpos
│   └── plantilla_recibo.py        # Formato del recibo impreso
│
└── reports/
    ├── exportar_pdf.py             # ReportLab
    └── exportar_excel.py           # openpyxl
```
 
---
 
## Configuración de Cursor IDE
 
Extensiones recomendadas:
- `Python` (Pylance) — autocompletado e inferencia de tipos
- `SQLite Viewer` (Florian Klampfer) — inspección del `.db` en tiempo real
- `Error Lens` — errores inline mientras se escribe
- `Todo Tree` — rastreo de pendientes en el código
```json
// .cursor/settings.json
{
  "python.defaultInterpreterPath": "./venv/Scripts/python.exe",
  "python.linting.enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```
 
---
 
## Decisiones de arquitectura clave
 
- **CustomTkinter solo para contenedores y controles** — las tablas de datos usan `ttk.Treeview` nativo para máximo rendimiento en hardware limitado.
- **SQLite con índices** en columnas `fecha` y `producto_id` para que los reportes no sean lentos.
- **Nunca cargar toda la BD en memoria** — usar paginación en listados y reportes.
- **PyInstaller** genera un `.exe` standalone: el cliente no necesita tener Python instalado.
- **bcrypt** para contraseñas: nunca se almacena la contraseña en texto plano.
- **Copia del nombre del producto en `pedido_items` y `factura_detalles`**: garantiza que el histórico no se rompa si un producto se edita o elimina del menú.
- **El mapa de mesas es el punto de entrada al POS**: el cajero siempre selecciona una mesa antes de tomar un pedido. No existe factura sin mesa asociada.
- **División de cuenta genera facturas independientes**: cada factura parcial tiene su propio número de serie y queda registrada individualmente en contabilidad. El campo `grupo_division` permite agruparlas si se necesita auditar.
---
 
## Orden de desarrollo sugerido
 
1. `schema.sql` + `db_manager.py` — base de datos y operaciones CRUD
2. `auth_service.py` + `ventana_login.py` — sistema de usuarios y roles
3. `models/` — entidades del negocio
4. `ventana_mesas.py` + `mesa_service.py` — mapa visual del salón
5. `ventana_pos.py` + `facturacion_service.py` — núcleo del sistema
6. `colpos_printer.py` + `plantilla_recibo.py` — integración impresora
7. `ventana_menu.py` + `ventana_inventario.py` — gestión de productos
8. `reporte_service.py` + `exportar_pdf.py` + `exportar_excel.py` — reportes
9. `ventana_usuarios.py` + `hora_service.py` — administración
10. Empaquetado con PyInstaller → `.exe`