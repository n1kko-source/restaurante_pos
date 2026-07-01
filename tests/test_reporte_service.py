"""Tests de integración para services/reporte_service.py.

Ejecutar desde la raíz del proyecto:
    python -m unittest tests.test_reporte_service -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database.db_manager as db_manager
from models.usuario import Usuario
from services import auth_service, reporte_service


class _ReporteBdTemporal(unittest.TestCase):
    """BD temporal con sesión de supervisor para pruebas de reportes."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        db_manager.RUTA_DB = Path(self._tmpdir) / "test.db"
        db_manager.init_db()
        auth_service._usuario_actual = Usuario(
            id=1,
            nombre="Supervisor Test",
            usuario="supervisor_test",
            rol="supervisor",
        )

    def tearDown(self):
        auth_service.cerrar_sesion()
        shutil.rmtree(self._tmpdir, ignore_errors=True)


class TestReporteDiario(_ReporteBdTemporal):
    """Consolidado diario y registro de cierre."""

    def setUp(self):
        super().setUp()
        con = db_manager.obtener_conexion()
        con.execute("INSERT INTO categorias (nombre) VALUES ('Platos')")
        con.execute(
            "INSERT INTO productos (categoria_id, nombre, precio, stock) "
            "VALUES (1, 'Bandeja', 18000, 10)"
        )
        con.execute(
            "INSERT INTO productos (categoria_id, nombre, precio, stock) "
            "VALUES (1, 'Jugo', 3000, 20)"
        )
        pedido_id = con.execute(
            "INSERT INTO pedidos (mesa_id, fecha, hora) VALUES (1, '2026-06-20', '12:00:00')"
        ).lastrowid

        con.execute(
            """INSERT INTO facturas
               (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
                metodo_pago, estado, es_parcial, grupo_division,
                comprador_nombre, comprador_identificacion)
               VALUES ('FAC-20260620-001', ?, 1, '2026-06-20', '13:00:00',
                       21000, 1000, 'efectivo', 'pagada', 0, NULL,
                       'Juan Pérez', '123456')""",
            (pedido_id,),
        )
        con.execute(
            """INSERT INTO factura_detalles
               (factura_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
               VALUES (1, 1, 'Bandeja', 1, 18000, 18000)"""
        )
        con.execute(
            """INSERT INTO factura_detalles
               (factura_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
               VALUES (1, 2, 'Jugo', 1, 3000, 3000)"""
        )
        con.commit()
        con.close()

    def test_reporte_diario_consolida_y_registra_cierre(self):
        reporte = reporte_service.reporte_diario("2026-06-20")

        self.assertEqual(reporte["fecha"], "2026-06-20")
        self.assertEqual(reporte["total_ventas"], 20000)
        self.assertEqual(reporte["numero_facturas"], 1)
        self.assertEqual(len(reporte["detalle_ventas"]), 2)
        self.assertTrue(reporte["cierre_registrado"])
        self.assertTrue(db_manager.existe_cierre_diario("2026-06-20"))

        self.assertEqual(reporte["totales_por_metodo_pago"]["efectivo"], 20000)
        self.assertEqual(reporte["totales_por_metodo_pago"]["nequi"], 0)

        renglones = reporte["detalle_ventas"]
        self.assertEqual(renglones[0]["factura_numero"], "FAC-20260620-001")
        self.assertEqual(renglones[0]["metodo_pago"], "efectivo")
        self.assertEqual(renglones[0]["comprador_nombre"], "Juan Pérez")
        self.assertEqual(renglones[0]["nombre_producto"], "Bandeja")
        self.assertEqual(renglones[1]["nombre_producto"], "Jugo")

    def test_reporte_diario_no_duplica_cierre(self):
        reporte_service.reporte_diario("2026-06-20")
        segundo = reporte_service.reporte_diario("2026-06-20")

        self.assertFalse(segundo["cierre_registrado"])
        self.assertEqual(segundo["total_ventas"], 20000)


class TestReporteMensual(_ReporteBdTemporal):
    """Consolidado mensual con cierres diarios."""

    def setUp(self):
        super().setUp()
        auth_service._usuario_actual = Usuario(
            id=2,
            nombre="Admin Test",
            usuario="admin_test",
            rol="administrador",
        )
        con = db_manager.obtener_conexion()
        con.execute("INSERT INTO categorias (nombre) VALUES ('Cat')")
        con.execute(
            "INSERT INTO productos (categoria_id, nombre, precio, stock) VALUES (1, 'Prod', 5000, 1)"
        )
        pedido_id = con.execute(
            "INSERT INTO pedidos (mesa_id, fecha, hora) VALUES (1, '2026-06-01', '08:00:00')"
        ).lastrowid
        con.execute(
            """INSERT INTO facturas
               (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
                metodo_pago, estado, es_parcial, grupo_division)
               VALUES ('FAC-20260601-001', ?, 1, '2026-06-01', '10:00:00',
                       5000, 0, 'efectivo', 'pagada', 0, NULL)""",
            (pedido_id,),
        )
        con.execute(
            """INSERT INTO factura_detalles
               (factura_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
               VALUES (1, 1, 'Prod', 1, 5000, 5000)"""
        )
        con.execute(
            """INSERT INTO cierres_diarios (fecha, total_ventas, numero_facturas, generado_en)
               VALUES ('2026-06-01', 5000, 1, '2026-06-01T22:00:00')"""
        )
        con.commit()
        con.close()

    def test_reporte_mensual_incluye_cierres(self):
        reporte = reporte_service.reporte_mensual(2026, 6)

        self.assertEqual(reporte["anio"], 2026)
        self.assertEqual(reporte["mes"], 6)
        self.assertEqual(reporte["total_ventas"], 5000)
        self.assertEqual(reporte["numero_facturas"], 1)
        self.assertEqual(len(reporte["cierres_diarios"]), 1)
        self.assertEqual(reporte["cierres_diarios"][0]["fecha"], "2026-06-01")


class TestControlAccesoReportes(_ReporteBdTemporal):
    """Restricción de roles en reportes."""

    def test_cajero_no_puede_reporte_diario(self):
        auth_service._usuario_actual = Usuario(
            id=3, nombre="Cajero", usuario="cajero", rol="cajero"
        )
        with self.assertRaises(auth_service.ErrorAcceso):
            reporte_service.reporte_diario("2026-06-01")

    def test_supervisor_no_puede_reporte_mensual(self):
        with self.assertRaises(auth_service.ErrorAcceso):
            reporte_service.reporte_mensual(2026, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
