"""Integración con impresora térmica Colpos vía python-escpos (COM/USB)."""

import logging
from typing import Any, Dict, Optional, Union

from config import IMPRESORA
from printing.plantilla_recibo import FacturaImpresion, formatear_recibo

logger = logging.getLogger(__name__)


class ErrorImpresora(Exception):
    """Error controlado de impresión; no debe tumbar el POS."""


class ColposPrinter:
    """
    Controlador de la impresora térmica Colpos (protocolo ESC/POS).

    Lee la configuración centralizada de config.IMPRESORA:
      - tipo: 'serial' | 'usb'
      - puerto: ej. 'COM3' (serial)
      - baudrate: ej. 9600 (serial)
      - ancho_papel: 32 (58 mm) o 48 (80 mm)
      - vendor_id / product_id: requeridos si tipo='usb'
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = dict(config or IMPRESORA)
        self._impresora: Any = None
        self._ultimo_error = ""
        self._ancho_papel = int(self._config.get("ancho_papel", 32))

    @property
    def ultimo_error(self) -> str:
        """Retorna el mensaje del último fallo de conexión o impresión."""
        return self._ultimo_error

    @property
    def esta_conectada(self) -> bool:
        """Indica si hay una sesión activa con la impresora."""
        return self._impresora is not None

    def conectar(self) -> bool:
        """
        Abre la conexión serial o USB según config.IMPRESORA.

        Retorna True si la conexión fue exitosa; False si la impresora
        no está disponible, sin lanzar excepción al llamador.
        """
        self._ultimo_error = ""
        self.desconectar()

        tipo = str(self._config.get("tipo", "serial")).lower()
        try:
            if tipo == "serial":
                self._impresora = self._crear_impresora_serial()
            elif tipo == "usb":
                self._impresora = self._crear_impresora_usb()
            else:
                raise ValueError(
                    f"Tipo de impresora no soportado: '{tipo}'. "
                    "Use 'serial' o 'usb'."
                )

            if hasattr(self._impresora, "open"):
                self._impresora.open(raise_not_found=True)
            return True
        except Exception as exc:
            self._ultimo_error = (
                f"No se pudo conectar con la impresora ({tipo}): {exc}"
            )
            logger.warning(self._ultimo_error)
            self._impresora = None
            return False

    def _crear_impresora_serial(self):
        """Instancia el driver Serial de python-escpos."""
        from escpos.printer import Serial

        puerto = self._config.get("puerto", "COM3")
        baudrate = int(self._config.get("baudrate", 9600))
        timeout = self._config.get("timeout", 1)
        return Serial(devfile=puerto, baudrate=baudrate, timeout=timeout)

    def _crear_impresora_usb(self):
        """Instancia el driver USB de python-escpos."""
        from escpos.printer import Usb

        vendor_id = self._config.get("vendor_id")
        product_id = self._config.get("product_id")
        if vendor_id is None or product_id is None:
            raise ValueError(
                "Configuración USB incompleta: defina vendor_id y product_id "
                "en config.IMPRESORA."
            )
        return Usb(int(vendor_id), int(product_id))

    def imprimir_factura(self, factura: Union[FacturaImpresion, Any]) -> None:
        """
        Imprime el recibo de una factura con sus detalles.

        factura: instancia FacturaImpresion con cabecera y renglones.
        Lanza ErrorImpresora si falla la impresión (sin tumbar el proceso).
        """
        if self._impresora is None:
            raise ErrorImpresora(
                "Impresora no conectada. Llame a conectar() primero."
            )

        if not isinstance(factura, FacturaImpresion):
            raise TypeError(
                "Se esperaba FacturaImpresion con cabecera y detalles."
            )

        try:
            texto = formatear_recibo(factura, self._ancho_papel)
            for linea in texto.splitlines():
                self._impresora.textln(linea)
            self.cortar_papel()
        except ErrorImpresora:
            raise
        except Exception as exc:
            self._ultimo_error = f"Error al imprimir la factura: {exc}"
            logger.warning(self._ultimo_error)
            raise ErrorImpresora(self._ultimo_error) from exc

    def cortar_papel(self) -> None:
        """Envía el comando ESC/POS de corte de papel."""
        if self._impresora is None:
            raise ErrorImpresora("Impresora no conectada.")
        try:
            self._impresora.cut(mode="FULL")
        except Exception as exc:
            self._ultimo_error = f"Error al cortar el papel: {exc}"
            logger.warning(self._ultimo_error)
            raise ErrorImpresora(self._ultimo_error) from exc

    def desconectar(self) -> None:
        """Cierra la conexión con la impresora de forma segura."""
        if self._impresora is None:
            return
        try:
            if hasattr(self._impresora, "close"):
                self._impresora.close()
        except Exception as exc:
            logger.warning("Error al cerrar la impresora: %s", exc)
        finally:
            self._impresora = None
