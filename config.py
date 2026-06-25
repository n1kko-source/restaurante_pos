"""Constantes de configuración: impresora, rutas de exportación y parámetros del sistema."""

from pathlib import Path

# ============================================================
# BASE DE DATOS
# ============================================================

RUTA_DB = Path(__file__).parent / "database" / "restaurante.db"

# Tamaño de página para listados Treeview. Cambiar aquí afecta a todos los
# módulos; mantener en 50 salvo pruebas en el equipo objetivo.
PAGINA_TAMANO_DEFAULT = 50

# Credenciales del usuario administrador creado en el primer arranque.
# IMPORTANTE: el cajero/supervisor debe cambiar esta contraseña en el
# primer inicio de sesión. auth_service.py es responsable de forzar ese cambio.
ADMIN_INICIAL_USUARIO = "admin"
ADMIN_INICIAL_PASSWORD = "admin123"

# ============================================================
# IMPRESORA TÉRMICA COLPOS (ESC/POS)
# ============================================================

IMPRESORA = {
    "tipo": "serial",       # "serial" | "usb"
    "puerto": "COM3",
    "baudrate": 9600,
    "ancho_papel": 40,      # 32 para papel 58mm, 48 para 80mm
}

# ============================================================
# EXPORTACIÓN DE REPORTES
# ============================================================

RUTA_EXPORTACION = Path(__file__).parent / "exports"
