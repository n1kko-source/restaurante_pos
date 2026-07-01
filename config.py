"""Constantes de configuración: impresora, rutas de exportación y parámetros del sistema."""

import sys
from pathlib import Path

# ============================================================
# RUTAS DE LA APLICACIÓN
# ============================================================

def _ruta_base_aplicacion() -> Path:
    """
    Raíz de recursos empaquetados (PyInstaller) o del proyecto en desarrollo.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


RUTA_BASE = _ruta_base_aplicacion()
RUTA_ASSETS = RUTA_BASE / "assets"
RUTA_LOGO_PNG = RUTA_ASSETS / "logo_hogarenos.png"
RUTA_ICONO_APP = RUTA_ASSETS / "logo_hogarenos.ico"
RUTA_ICONOS = RUTA_ASSETS / "iconos"
# Logotipo personalizado del encabezado de factura térmica (configurable en UI).
RUTA_LOGO_FACTURA = RUTA_ASSETS / "logo_factura.png"

# ============================================================
# BASE DE DATOS
# ============================================================

RUTA_DB = Path(__file__).parent / "database" / "restaurante.db"

# Preferencias del usuario (puerto de impresora, etc.). Sobrescribe defaults de IMPRESORA.
RUTA_CONFIG_LOCAL = Path(__file__).parent / "config_local.json"

# Tamaño de página para listados Treeview. Cambiar aquí afecta a todos los
# módulos; mantener en 50 salvo pruebas en el equipo objetivo.
PAGINA_TAMANO_DEFAULT = 50

# Credenciales del usuario administrador creado en el primer arranque.
# IMPORTANTE: el cajero/supervisor debe cambiar esta contraseña en el
# primer inicio de sesión. auth_service.py es responsable de forzar ese cambio.
ADMIN_INICIAL_USUARIO = "admin"
ADMIN_INICIAL_PASSWORD = "admin123"

# ============================================================
# DATOS DEL RESTAURANTE (encabezado de recibos y reportes)
# ============================================================

RESTAURANTE = {
    "nombre": "Restaurante Hogareños",
    "direccion": "Cra 15 # 23-45, Bogotá",
}

# Métodos de pago aceptados en facturas (código interno -> etiqueta en UI/recibo).
METODOS_PAGO = (
    ("efectivo", "Efectivo"),
    ("daviplata", "Daviplata"),
    ("nequi", "Nequi"),
    ("anotar", "Anotar"),
)
METODOS_PAGO_VALIDOS = frozenset(codigo for codigo, _ in METODOS_PAGO)
ETIQUETAS_METODO_PAGO = {codigo: etiqueta for codigo, etiqueta in METODOS_PAGO}
ETIQUETA_A_METODO_PAGO = {etiqueta: codigo for codigo, etiqueta in METODOS_PAGO}

# Plantilla del recibo térmico (valores por defecto; se sobrescriben en config_local.json).
PLANTILLA_FACTURA = {
    "titulo_documento": "Factura Electrónica de Venta",
    "razon_social": RESTAURANTE["nombre"],
    "nit": "",
    "direccion": RESTAURANTE["direccion"],
    "regimen_tributario": "",
    "usar_logo_personalizado": False,
}

# Colores de marca Hogareños (logo #f59c0c). Compartidos por UI y exportadores.
MARCA_COLORES = {
    "naranja": "#f59c0c",
    "naranja_oscuro": "#d97706",
    "fondo_tabla": "#ffedd5",
    "texto": "#2c2416",
    "texto_suave": "#6b5d4a",
    "borde": "#e8dcc8",
}

# ============================================================
# IMPRESORA TÉRMICA COLPOS (ESC/POS)
# ============================================================

IMPRESORA = {
    "tipo": "serial",       # "serial" | "usb"
    "puerto": "COM3",
    "baudrate": 9600,
    "ancho_papel": 40,      # 32 = papel 58 mm, 48 = papel 80 mm
    # Solo si tipo="usb" (requiere vendor_id y product_id del dispositivo):
    # "vendor_id": 0x04b8,
    # "product_id": 0x0e15,
}

# ============================================================
# EXPORTACIÓN DE REPORTES
# ============================================================

# Carpeta inicial sugerida en el diálogo "Guardar como" de reportes.
# El usuario puede elegir otra ubicación en cada exportación.
RUTA_EXPORTACION = Path(__file__).parent / "exports"
