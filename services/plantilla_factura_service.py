"""Configuración de la plantilla del recibo térmico de factura."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from config import PLANTILLA_FACTURA, RUTA_CONFIG_LOCAL, RUTA_LOGO_FACTURA, RUTA_LOGO_PNG, RESTAURANTE
from models.factura import Factura, FacturaDetalle
from services.auth_service import requiere_rol
from services.impresora_service import _guardar_seccion_local, obtener_config_impresora

_CLAVES_PLANTILLA = (
    "titulo_documento",
    "razon_social",
    "nit",
    "direccion",
    "regimen_tributario",
    "usar_logo_personalizado",
)


def _leer_seccion_plantilla() -> Dict[str, Any]:
    """Lee la sección plantilla_factura de config_local.json."""
    if not RUTA_CONFIG_LOCAL.is_file():
        return {}
    try:
        with open(RUTA_CONFIG_LOCAL, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(datos, dict):
        return {}
    seccion = datos.get("plantilla_factura", {})
    return dict(seccion) if isinstance(seccion, dict) else {}


def obtener_config_plantilla() -> Dict[str, Any]:
    """Retorna la plantilla efectiva (defaults + archivo local)."""
    config = dict(PLANTILLA_FACTURA)
    guardada = _leer_seccion_plantilla()
    for clave in _CLAVES_PLANTILLA:
        if clave in guardada and guardada[clave] is not None:
            config[clave] = guardada[clave]
    for clave in (
        "titulo_documento",
        "razon_social",
        "nit",
        "direccion",
        "regimen_tributario",
    ):
        if isinstance(config.get(clave), str):
            config[clave] = config[clave].strip()
    return config


def obtener_ruta_logo_efectiva() -> Optional[Path]:
    """
    Retorna la ruta del PNG a imprimir en el encabezado, o None si no hay logo.
    Prioriza logo_factura.png personalizado; si no existe, usa el logo Hogareños.
    """
    config = obtener_config_plantilla()
    if config.get("usar_logo_personalizado") and RUTA_LOGO_FACTURA.is_file():
        return RUTA_LOGO_FACTURA
    if RUTA_LOGO_PNG.is_file():
        return RUTA_LOGO_PNG
    return None


@requiere_rol("administrador")
def guardar_config_plantilla(
    titulo_documento: str,
    razon_social: str,
    nit: str,
    direccion: str,
    regimen_tributario: str,
) -> None:
    """Persiste los textos de la plantilla de factura térmica."""
    config_actual = obtener_config_plantilla()
    plantilla = {
        "titulo_documento": titulo_documento.strip(),
        "razon_social": razon_social.strip(),
        "nit": nit.strip(),
        "direccion": direccion.strip(),
        "regimen_tributario": regimen_tributario.strip(),
        "usar_logo_personalizado": bool(config_actual.get("usar_logo_personalizado")),
    }
    _guardar_seccion_local("plantilla_factura", plantilla)


@requiere_rol("administrador")
def importar_logo_factura(ruta_origen: Path) -> None:
    """Copia un PNG seleccionado por el usuario como logotipo de factura."""
    origen = Path(ruta_origen)
    if not origen.is_file():
        raise ValueError("No se encontró el archivo de imagen seleccionado.")
    if origen.suffix.lower() != ".png":
        raise ValueError("El logotipo debe ser un archivo PNG.")

    RUTA_LOGO_FACTURA.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, RUTA_LOGO_FACTURA)

    config = obtener_config_plantilla()
    config["usar_logo_personalizado"] = True
    _guardar_seccion_local("plantilla_factura", config)


@requiere_rol("administrador")
def restaurar_logo_por_defecto() -> None:
    """Vuelve a usar el logo Hogareños del sistema en la plantilla."""
    config = obtener_config_plantilla()
    config["usar_logo_personalizado"] = False
    _guardar_seccion_local("plantilla_factura", config)


def generar_vista_previa(
    titulo_documento: str = "",
    razon_social: str = "",
    nit: str = "",
    direccion: str = "",
    regimen_tributario: str = "",
    ancho_papel: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Genera las líneas de un recibo de demostración con los textos indicados.

    Usa ítems y totales de ejemplo para mostrar en la UI cómo quedará la factura
    impresa. Reutiliza la misma lógica que la impresora Colpos.
    """
    from printing.plantilla_recibo import (
        FacturaImpresion,
        generar_lineas_recibo,
        normalizar_ancho_papel,
    )

    if ancho_papel is None:
        ancho_papel = int(obtener_config_impresora().get("ancho_papel", 40))

    factura_demo = Factura(
        id=0,
        numero="FAC-20260629-001",
        pedido_id=0,
        mesa_id=0,
        fecha="2026-06-29",
        hora="14:30:00",
        total=36000,
        descuento=0,
        metodo_pago="efectivo",
        estado="pagada",
        es_parcial=0,
        grupo_division=None,
    )
    detalles_demo = [
        FacturaDetalle(1, 0, 1, "Jugo natural", 3, 5000, 15000),
        FacturaDetalle(2, 0, 2, "Bandeja paisa", 1, 21000, 21000),
    ]

    datos = FacturaImpresion(
        factura=factura_demo,
        detalles=detalles_demo,
        mesa_numero=6,
        nombre_restaurante=razon_social.strip() or RESTAURANTE["nombre"],
        direccion_restaurante=direccion.strip() or RESTAURANTE["direccion"],
        titulo_documento=titulo_documento.strip(),
        razon_social=razon_social.strip(),
        nit=nit.strip(),
        direccion=direccion.strip(),
        regimen_tributario=regimen_tributario.strip(),
        comprador_nombre="",
        comprador_identificacion="",
        ruta_logo=obtener_ruta_logo_efectiva(),
    )
    ancho_efectivo = normalizar_ancho_papel(ancho_papel)
    return {
        "lineas": generar_lineas_recibo(datos, ancho_papel),
        "ruta_logo": datos.ruta_logo,
        "ancho_caracteres": ancho_efectivo,
    }
