"""Tests unitarios para printing/plantilla_recibo.py.

Ejecutar desde la raíz del proyecto:
    python -m unittest tests.test_plantilla_recibo -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RESTAURANTE
from models.factura import Factura, FacturaDetalle
from printing.plantilla_recibo import (
    ANCHO_PAPEL_58MM,
    ANCHO_PAPEL_80MM,
    FacturaImpresion,
    formatear_recibo,
    generar_lineas_recibo,
    normalizar_ancho_papel,
)


def _factura_ejemplo(descuento: int = 0, es_parcial: int = 0) -> Factura:
    """Construye una factura de prueba con datos del schema."""
    return Factura(
        id=1,
        numero="FAC-20260625-001",
        pedido_id=1,
        mesa_id=1,
        fecha="2026-06-25",
        hora="14:30:45",
        total=44000,
        descuento=descuento,
        metodo_pago="billetera_digital",
        estado="pagada",
        es_parcial=es_parcial,
        grupo_division="split-1-1" if es_parcial else None,
    )


def _datos_ejemplo(descuento: int = 0) -> FacturaImpresion:
    """Paquete completo de impresión para pruebas."""
    return FacturaImpresion(
        factura=_factura_ejemplo(descuento=descuento),
        detalles=[
            FacturaDetalle(1, 1, 1, "Bandeja paisa", 2, 18000, 36000),
            FacturaDetalle(2, 1, 2, "Limonada natural", 1, 8000, 8000),
        ],
        mesa_numero=5,
    )


class TestNormalizarAnchoPapel(unittest.TestCase):
    """Normalización de ancho según config de papel térmico."""

    def test_32_para_papel_58mm(self):
        self.assertEqual(normalizar_ancho_papel(32), ANCHO_PAPEL_58MM)

    def test_40_intermedio_usa_valor_directo(self):
        self.assertEqual(normalizar_ancho_papel(40), 40)

    def test_48_para_papel_80mm(self):
        self.assertEqual(normalizar_ancho_papel(48), ANCHO_PAPEL_80MM)


class TestFormatearRecibo(unittest.TestCase):
    """Contenido y formato del recibo impreso."""

    def setUp(self):
        self.datos = _datos_ejemplo()

    def test_retorna_string_con_saltos_de_linea(self):
        texto = formatear_recibo(self.datos, 32)
        self.assertIsInstance(texto, str)
        self.assertIn("\n", texto)
        self.assertEqual(texto, "\n".join(generar_lineas_recibo(self.datos, 32)))

    def test_encabezado_con_nombre_direccion_y_fecha(self):
        lineas = generar_lineas_recibo(self.datos, 48)
        self.assertIn(RESTAURANTE["nombre"].upper(), lineas[0].upper())
        self.assertIn(RESTAURANTE["direccion"], lineas[1])
        self.assertIn("2026-06-25", lineas[2])
        self.assertIn("14:30", lineas[2])

    def test_separadores_son_guiones_del_ancho_correcto(self):
        ancho = normalizar_ancho_papel(32)
        lineas = generar_lineas_recibo(self.datos, 32)
        separadores = [l for l in lineas if l and set(l) == {"-"}]
        self.assertGreaterEqual(len(separadores), 2)
        for sep in separadores:
            self.assertEqual(len(sep), ancho)

    def test_tabla_items_incluye_columnas_y_renglones(self):
        texto = formatear_recibo(self.datos, 48)
        self.assertIn("Ct", texto)
        self.assertIn("Producto", texto)
        self.assertIn("P.Unit", texto)
        self.assertIn("Total", texto)
        self.assertIn("Bandeja paisa", texto)
        self.assertIn("$18.000", texto)
        self.assertIn("$36.000", texto)

    def test_total_y_metodo_de_pago(self):
        texto = formatear_recibo(self.datos, 48)
        self.assertIn("TOTAL:", texto)
        self.assertIn("$44.000", texto)
        self.assertIn("Billetera digital", texto)

    def test_pie_agradecimiento(self):
        texto = formatear_recibo(self.datos, 32)
        self.assertIn("Gracias por su visita", texto)

    def test_descuento_muestra_subtotal_y_descuento(self):
        datos = _datos_ejemplo(descuento=4000)
        texto = formatear_recibo(datos, 48)
        self.assertIn("Subtotal:", texto)
        self.assertIn("Descuento:", texto)
        self.assertIn("-$4.000", texto)
        self.assertIn("$40.000", texto)

    def test_cuenta_dividida_marca_en_recibo(self):
        datos = _datos_ejemplo()
        datos.factura = _factura_ejemplo(es_parcial=1)
        texto = formatear_recibo(datos, 48)
        self.assertIn("Cuenta dividida", texto)

    def test_todas_las_lineas_respetan_ancho(self):
        for ancho_config in (32, 40, 48):
            with self.subTest(ancho=ancho_config):
                ancho = normalizar_ancho_papel(ancho_config)
                for linea in formatear_recibo(self.datos, ancho_config).splitlines():
                    self.assertLessEqual(
                        len(linea),
                        ancho,
                        f"Línea excede {ancho} chars: {linea!r}",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
