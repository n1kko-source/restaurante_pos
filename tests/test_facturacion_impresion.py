"""Tests de integración para facturación e impresión Colpos.

Usa BD temporal y mock de ColposPrinter (sin hardware ni red).

Ejecutar desde la raíz del proyecto:
    python -m unittest tests.test_facturacion_impresion -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import database.db_manager as db_manager
from config import RESTAURANTE
from models.usuario import Usuario
from printing.colpos_printer import ErrorImpresora
from services import auth_service, facturacion_service
from printing.plantilla_recibo import FacturaImpresion


class _BdImpresionBase(unittest.TestCase):
    """BD temporal con pedido abierto listo para facturar."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        db_manager.RUTA_DB = Path(self._tmpdir) / "test.db"
        db_manager.init_db()

        auth_service._usuario_actual = Usuario(
            id=1,
            nombre="Cajero Test",
            usuario="cajero_test",
            rol="cajero",
        )

        cat_id = db_manager.crear_categoria("Platos")
        prod_id = db_manager.crear_producto(cat_id, "Bandeja paisa", 18000, 50)
        self._pedido_id = db_manager.crear_pedido(1, "2026-06-25", "12:00:00")
        db_manager.agregar_item_pedido(
            self._pedido_id, prod_id, "Bandeja paisa", 2, 18000, 36000
        )

    def tearDown(self):
        auth_service.cerrar_sesion()
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class TestObtenerDatosImpresion(_BdImpresionBase):
    """Arma del paquete FacturaImpresion desde la BD."""

    def test_datos_incluyen_cabecera_detalles_y_mesa(self):
        factura = facturacion_service.crear_factura(
            self._pedido_id, "efectivo", descuento=0
        )
        datos = facturacion_service.obtener_datos_impresion(factura.id)

        self.assertIsNotNone(datos)
        self.assertIsInstance(datos, FacturaImpresion)
        self.assertEqual(datos.factura.numero, factura.numero)
        self.assertEqual(len(datos.detalles), 1)
        self.assertEqual(datos.detalles[0].nombre_producto, "Bandeja paisa")
        self.assertEqual(datos.mesa_numero, 1)
        self.assertEqual(datos.nombre_restaurante, RESTAURANTE["nombre"])


class TestImprimirFactura(_BdImpresionBase):
    """Envío a impresora con mock de hardware."""

    @patch("services.facturacion_service.ColposPrinter")
    def test_imprimir_factura_exito(self, mock_cls):
        mock_impresora = MagicMock()
        mock_impresora.conectar.return_value = True
        mock_cls.return_value = mock_impresora

        factura = facturacion_service.crear_factura(
            self._pedido_id, "efectivo", descuento=0
        )
        ok, mensaje = facturacion_service.imprimir_factura(factura.id)

        self.assertTrue(ok)
        self.assertIn(factura.numero, mensaje)
        mock_impresora.conectar.assert_called_once()
        mock_impresora.imprimir_factura.assert_called_once()
        mock_impresora.desconectar.assert_called_once()

    @patch("services.facturacion_service.ColposPrinter")
    def test_imprimir_factura_sin_conexion(self, mock_cls):
        mock_impresora = MagicMock()
        mock_impresora.conectar.return_value = False
        mock_impresora.ultimo_error = "Puerto COM3 no disponible"
        mock_cls.return_value = mock_impresora

        factura = facturacion_service.crear_factura(
            self._pedido_id, "efectivo", descuento=0
        )
        ok, mensaje = facturacion_service.imprimir_factura(factura.id)

        self.assertFalse(ok)
        self.assertIn("COM3", mensaje)
        mock_impresora.imprimir_factura.assert_not_called()

    @patch("services.facturacion_service.ColposPrinter")
    def test_imprimir_factura_error_durante_impresion(self, mock_cls):
        mock_impresora = MagicMock()
        mock_impresora.conectar.return_value = True
        mock_impresora.imprimir_factura.side_effect = ErrorImpresora("Papel atascado")
        mock_cls.return_value = mock_impresora

        factura = facturacion_service.crear_factura(
            self._pedido_id, "efectivo", descuento=0
        )
        ok, mensaje = facturacion_service.imprimir_factura(factura.id)

        self.assertFalse(ok)
        self.assertIn("Papel atascado", mensaje)


class TestFacturarEImprimirPedido(_BdImpresionBase):
    """Flujo completo de cobro con persistencia aunque falle la impresora."""

    @patch("services.facturacion_service.ColposPrinter")
    def test_guarda_factura_aunque_falle_impresion(self, mock_cls):
        mock_impresora = MagicMock()
        mock_impresora.conectar.return_value = False
        mock_impresora.ultimo_error = "Impresora apagada"
        mock_cls.return_value = mock_impresora

        factura, ok, mensaje = facturacion_service.facturar_e_imprimir_pedido(
            self._pedido_id,
            metodo_pago="daviplata",
            descuento=2000,
        )

        self.assertFalse(ok)
        self.assertIsNotNone(factura.id)
        self.assertEqual(factura.metodo_pago, "daviplata")
        self.assertEqual(factura.descuento, 2000)
        self.assertEqual(factura.total_neto(), 34000)

        recuperada = facturacion_service.obtener_factura(factura.id)
        self.assertIsNotNone(recuperada)
        self.assertEqual(recuperada.numero, factura.numero)

    @patch("services.facturacion_service.ColposPrinter")
    def test_facturar_e_imprimir_exito(self, mock_cls):
        mock_impresora = MagicMock()
        mock_impresora.conectar.return_value = True
        mock_cls.return_value = mock_impresora

        factura, ok, mensaje = facturacion_service.facturar_e_imprimir_pedido(
            self._pedido_id,
            metodo_pago="efectivo",
        )

        self.assertTrue(ok)
        self.assertIn("enviada", mensaje.lower())
        mock_impresora.imprimir_factura.assert_called_once()
        args = mock_impresora.imprimir_factura.call_args[0][0]
        self.assertEqual(args.factura.numero, factura.numero)
        self.assertEqual(len(args.detalles), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
