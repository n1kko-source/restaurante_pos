"""Tests para reports/utilidades_reporte.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from reports.utilidades_reporte import numero_factura_corto, detalle_con_separadores_factura, agrupar_detalle_por_factura


class TestNumeroFacturaCorto(unittest.TestCase):
    """Formato compacto del número de factura en reportes diarios."""

    def test_extrae_consecutivo_diario(self):
        self.assertEqual(numero_factura_corto("FAC-20260701-001"), "001")
        self.assertEqual(numero_factura_corto("FAC-20260701-012"), "012")

    def test_valor_vacio_o_desconocido(self):
        self.assertEqual(numero_factura_corto(""), "—")
        self.assertEqual(numero_factura_corto("FAC-INVALIDA"), "FAC-INVALIDA")


class TestDetalleConSeparadoresFactura(unittest.TestCase):
    """Separación visual entre grupos de factura distintos."""

    def test_inserta_espacio_al_cambiar_factura(self):
        detalle = [
            {"factura_numero": "FAC-20260701-001", "nombre_producto": "A"},
            {"factura_numero": "FAC-20260701-001", "nombre_producto": "B"},
            {"factura_numero": "FAC-20260701-002", "nombre_producto": "C"},
        ]
        resultado = detalle_con_separadores_factura(detalle)
        self.assertEqual(len(resultado), 4)
        self.assertIsNone(resultado[2])
        self.assertEqual(resultado[3]["nombre_producto"], "C")

    def test_sin_separador_en_una_sola_factura(self):
        detalle = [
            {"factura_numero": "FAC-20260701-001", "nombre_producto": "A"},
            {"factura_numero": "FAC-20260701-001", "nombre_producto": "B"},
        ]
        self.assertEqual(detalle_con_separadores_factura(detalle), detalle)


class TestAgruparDetallePorFactura(unittest.TestCase):
    """Bloques independientes por factura para el PDF."""

    def test_agrupa_renglones_consecutivos(self):
        detalle = [
            {"factura_numero": "FAC-20260701-001", "nombre_producto": "A"},
            {"factura_numero": "FAC-20260701-001", "nombre_producto": "B"},
            {"factura_numero": "FAC-20260701-002", "nombre_producto": "C"},
        ]
        grupos = agrupar_detalle_por_factura(detalle)
        self.assertEqual(len(grupos), 2)
        self.assertEqual(len(grupos[0]), 2)
        self.assertEqual(grupos[1][0]["nombre_producto"], "C")


if __name__ == "__main__":
    unittest.main(verbosity=2)
