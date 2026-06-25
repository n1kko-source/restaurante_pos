"""Tests de integración para database/db_manager.py.

Cobertura de los casos identificados en la revisión QA (TC-01 a TC-10).
Usa BD en archivo temporal: sin red, sin efectos secundarios en restaurante.db.

Ejecutar desde la raíz del proyecto:
    python -m unittest tests.test_db_manager -v

No requiere dependencias fuera de requirements.txt.
"""

import shutil
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

# Insertar raíz del proyecto en el path antes de importar módulos del proyecto
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import database.db_manager as db_manager


# ---------------------------------------------------------------------------
# Mixin: BD temporal aislada por cada test
# ---------------------------------------------------------------------------

class _BdTemporal:
    """Crea un directorio temporal, apunta RUTA_DB a él y lo destruye al final."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        db_manager.RUTA_DB = Path(self._tmpdir) / "test.db"
        db_manager.init_db()

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# TC-01 — init_db idempotente
# ---------------------------------------------------------------------------

class TestInitDb(unittest.TestCase):
    """TC-01: init_db crea el contrato completo de forma idempotente."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        db_manager.RUTA_DB = Path(self._tmpdir) / "test.db"

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_crea_todas_las_tablas(self):
        """Todas las tablas del contrato existen tras init_db."""
        db_manager.init_db()
        con = db_manager.obtener_conexion()
        tablas = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        con.close()
        for tabla in db_manager._TABLAS_CONTRATO:
            with self.subTest(tabla=tabla):
                self.assertIn(tabla, tablas)

    def test_crea_11_mesas_semilla(self):
        """Las 11 mesas del salón se insertan al primer init_db."""
        db_manager.init_db()
        con = db_manager.obtener_conexion()
        count = con.execute("SELECT COUNT(*) FROM mesas").fetchone()[0]
        con.close()
        self.assertEqual(count, 11)

    def test_crea_usuario_admin_con_hash_bcrypt(self):
        """Se crea exactamente 1 administrador con hash bcrypt válido."""
        db_manager.init_db()
        con = db_manager.obtener_conexion()
        count = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        admin = con.execute("SELECT * FROM usuarios").fetchone()
        con.close()
        self.assertEqual(count, 1)
        self.assertEqual(admin["rol"], "administrador")
        self.assertTrue(admin["password_hash"].startswith("$2b$"))

    def test_idempotente_no_duplica_mesas_ni_admin(self):
        """Dos llamadas a init_db no duplican mesas ni usuarios."""
        db_manager.init_db()
        db_manager.init_db()
        con = db_manager.obtener_conexion()
        mesas = con.execute("SELECT COUNT(*) FROM mesas").fetchone()[0]
        usuarios = con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        con.close()
        self.assertEqual(mesas, 11)
        self.assertEqual(usuarios, 1)


# ---------------------------------------------------------------------------
# TC-09 — WAL activo
# ---------------------------------------------------------------------------

class TestWal(_BdTemporal, unittest.TestCase):
    """TC-09: modo journal WAL activo en cada conexión."""

    def test_journal_mode_wal(self):
        con = db_manager.obtener_conexion()
        modo = con.execute("PRAGMA journal_mode").fetchone()[0]
        con.close()
        self.assertEqual(modo, "wal")


# ---------------------------------------------------------------------------
# TC-02 — pedido único abierto por mesa
# ---------------------------------------------------------------------------

class TestPedidoUnico(_BdTemporal, unittest.TestCase):
    """TC-02: solo un pedido abierto por mesa a la vez."""

    def test_segundo_pedido_abierto_falla(self):
        """Insertar dos pedidos abiertos en la misma mesa lanza IntegrityError."""
        db_manager.crear_pedido(1, "2026-06-25", "10:00:00")
        with self.assertRaises(sqlite3.IntegrityError):
            db_manager.crear_pedido(1, "2026-06-25", "11:00:00")

    def test_pedido_cerrado_permite_nuevo_abierto(self):
        """Cerrar el pedido abierto permite abrir uno nuevo en la misma mesa."""
        pedido_id = db_manager.crear_pedido(1, "2026-06-25", "10:00:00")
        db_manager.cerrar_pedido(pedido_id)
        nuevo_id = db_manager.crear_pedido(1, "2026-06-25", "11:00:00")
        self.assertIsNotNone(nuevo_id)


# ---------------------------------------------------------------------------
# TC-03 — numeración de facturas y límite diario
# ---------------------------------------------------------------------------

class TestNumeracionFacturas(_BdTemporal, unittest.TestCase):
    """TC-03: numeración FAC-YYYYMMDD-NNN y límite de 999 facturas/día."""

    def setUp(self):
        super().setUp()
        cat_id = db_manager.crear_categoria("Bebidas")
        prod_id = db_manager.crear_producto(cat_id, "Agua", 2000, 100)
        self._pedido_id = db_manager.crear_pedido(1, "2026-06-25", "10:00:00")
        self._detalle = {
            "producto_id": prod_id,
            "nombre_producto": "Agua",
            "cantidad": 1,
            "precio_unitario": 2000,
            "subtotal": 2000,
        }

    def test_primera_factura_numero_001(self):
        """Primera factura del día recibe el sufijo -001 y tiene exactamente 16 chars."""
        _, numero = db_manager.registrar_factura_completa(
            self._pedido_id, 1, "2026-06-25", "10:00:00",
            2000, 0, "efectivo", [self._detalle],
        )
        self.assertEqual(numero, "FAC-20260625-001")
        self.assertEqual(len(numero), 16)

    def test_factura_999_se_genera_correctamente(self):
        """Factura #999 en el día debe generarse sin error."""
        con = db_manager.obtener_conexion()
        con.execute(
            "INSERT INTO contador_facturas (fecha, ultimo_numero) VALUES ('2026-06-25', 998)"
        )
        con.commit()
        con.close()
        _, numero = db_manager.registrar_factura_completa(
            self._pedido_id, 1, "2026-06-25", "10:00:00",
            2000, 0, "efectivo", [self._detalle],
        )
        self.assertEqual(numero, "FAC-20260625-999")

    def test_factura_1000_lanza_value_error(self):
        """La factura #1000 del mismo día lanza ValueError con mensaje claro."""
        con = db_manager.obtener_conexion()
        con.execute(
            "INSERT INTO contador_facturas (fecha, ultimo_numero) VALUES ('2026-06-25', 999)"
        )
        con.commit()
        con.close()
        with self.assertRaises(ValueError) as ctx:
            db_manager.registrar_factura_completa(
                self._pedido_id, 1, "2026-06-25", "10:00:00",
                2000, 0, "efectivo", [self._detalle],
            )
        self.assertIn("999", str(ctx.exception))

    def test_limite_excedido_no_corrompe_contador(self):
        """Tras el error por límite, el contador vuelve a 999 (rollback)."""
        con = db_manager.obtener_conexion()
        con.execute(
            "INSERT INTO contador_facturas (fecha, ultimo_numero) VALUES ('2026-06-25', 999)"
        )
        con.commit()
        con.close()
        try:
            db_manager.registrar_factura_completa(
                self._pedido_id, 1, "2026-06-25", "10:00:00",
                2000, 0, "efectivo", [self._detalle],
            )
        except ValueError:
            pass
        con = db_manager.obtener_conexion()
        num = con.execute(
            "SELECT ultimo_numero FROM contador_facturas WHERE fecha='2026-06-25'"
        ).fetchone()[0]
        con.close()
        self.assertEqual(num, 999)


# ---------------------------------------------------------------------------
# TC-04 — rollback ante detalle inválido
# ---------------------------------------------------------------------------

class TestRollbackFactura(_BdTemporal, unittest.TestCase):
    """TC-04: si un detalle viola CHECK de subtotal, rollback completo (sin factura huérfana)."""

    def setUp(self):
        super().setUp()
        cat_id = db_manager.crear_categoria("Comidas")
        self._prod_id = db_manager.crear_producto(cat_id, "Arroz", 8000, 50)
        self._pedido_id = db_manager.crear_pedido(1, "2026-06-25", "12:00:00")

    def test_detalle_con_subtotal_incorrecto_hace_rollback(self):
        """CHECK(subtotal = cantidad * precio_unitario) rechaza el insert y rollback total."""
        detalle_invalido = {
            "producto_id": self._prod_id,
            "nombre_producto": "Arroz",
            "cantidad": 2,
            "precio_unitario": 8000,
            "subtotal": 99999,  # Incorrecto: debería ser 16000
        }
        with self.assertRaises(sqlite3.IntegrityError):
            db_manager.registrar_factura_completa(
                self._pedido_id, 1, "2026-06-25", "12:00:00",
                99999, 0, "efectivo", [detalle_invalido],
            )
        con = db_manager.obtener_conexion()
        facturas = con.execute("SELECT COUNT(*) FROM facturas").fetchone()[0]
        detalles = con.execute("SELECT COUNT(*) FROM factura_detalles").fetchone()[0]
        con.close()
        self.assertEqual(facturas, 0, "No debe quedar factura huérfana tras rollback")
        self.assertEqual(detalles, 0)


# ---------------------------------------------------------------------------
# TC-05 — CHECK de división de cuenta
# ---------------------------------------------------------------------------

class TestDivisionCuenta(_BdTemporal, unittest.TestCase):
    """TC-05: es_parcial=1 sin grupo_division viola CHECK del schema."""

    def setUp(self):
        super().setUp()
        cat_id = db_manager.crear_categoria("Comidas")
        prod_id = db_manager.crear_producto(cat_id, "Sopa", 7000, 30)
        self._pedido_id = db_manager.crear_pedido(1, "2026-06-25", "13:00:00")
        self._detalle = {
            "producto_id": prod_id,
            "nombre_producto": "Sopa",
            "cantidad": 1,
            "precio_unitario": 7000,
            "subtotal": 7000,
        }

    def test_es_parcial_sin_grupo_division_falla(self):
        """es_parcial=1 con grupo_division=None debe ser rechazado por la BD."""
        with self.assertRaises(sqlite3.IntegrityError):
            db_manager.registrar_factura_completa(
                self._pedido_id, 1, "2026-06-25", "13:00:00",
                7000, 0, "efectivo", [self._detalle],
                es_parcial=1, grupo_division=None,
            )

    def test_factura_split_con_grupo_division_ok(self):
        """es_parcial=1 con grupo_division definido debe insertarse correctamente."""
        factura_id, _ = db_manager.registrar_factura_completa(
            self._pedido_id, 1, "2026-06-25", "13:00:00",
            7000, 0, "efectivo", [self._detalle],
            es_parcial=1, grupo_division="split-1-1750000000",
        )
        self.assertIsNotNone(factura_id)


# ---------------------------------------------------------------------------
# TC-07 — paginación de facturas por fecha
# ---------------------------------------------------------------------------

class TestPaginacionFacturas(_BdTemporal, unittest.TestCase):
    """TC-07: Treeview recibe máx PAGINA_TAMANO_DEFAULT filas; página 0 normaliza a 1."""

    def setUp(self):
        super().setUp()
        cat_id = db_manager.crear_categoria("Bebidas")
        prod_id = db_manager.crear_producto(cat_id, "Jugo", 3000, 200)
        self._detalle = {
            "producto_id": prod_id,
            "nombre_producto": "Jugo",
            "cantidad": 1,
            "precio_unitario": 3000,
            "subtotal": 3000,
        }
        # Insertar 60 facturas usando el mismo pedido (reutilización válida en BD)
        pedido_id = db_manager.crear_pedido(1, "2026-06-25", "08:00:00")
        for i in range(60):
            hora = f"08:{i:02d}:00"
            db_manager.registrar_factura_completa(
                pedido_id, 1, "2026-06-25", hora,
                3000, 0, "efectivo", [self._detalle],
            )

    def test_pagina_1_retorna_50_filas(self):
        filas = db_manager.obtener_facturas_por_fecha_pagina("2026-06-25", pagina=1)
        self.assertEqual(len(filas), 50)

    def test_pagina_2_retorna_10_filas(self):
        filas = db_manager.obtener_facturas_por_fecha_pagina("2026-06-25", pagina=2)
        self.assertEqual(len(filas), 10)

    def test_pagina_0_normaliza_a_pagina_1(self):
        """pagina=0 no debe producir OFFSET negativo; se trata como pagina=1."""
        filas_p0 = db_manager.obtener_facturas_por_fecha_pagina("2026-06-25", pagina=0)
        filas_p1 = db_manager.obtener_facturas_por_fecha_pagina("2026-06-25", pagina=1)
        self.assertEqual(len(filas_p0), len(filas_p1))
        self.assertEqual(
            [dict(f) for f in filas_p0],
            [dict(f) for f in filas_p1],
        )

    def test_total_facturas_fecha(self):
        total = db_manager.obtener_total_facturas_fecha("2026-06-25")
        self.assertEqual(total, 60)


# ---------------------------------------------------------------------------
# TC-10 — histórico de producto preservado tras desactivar
# ---------------------------------------------------------------------------

class TestHistoricoProducto(_BdTemporal, unittest.TestCase):
    """TC-10: desactivar producto no borra pedido_items; FK RESTRICT bloquea DELETE."""

    def setUp(self):
        super().setUp()
        cat_id = db_manager.crear_categoria("Comidas")
        self._prod_id = db_manager.crear_producto(cat_id, "Cazuela", 12000, 20)
        pedido_id = db_manager.crear_pedido(1, "2026-06-25", "14:00:00")
        db_manager.agregar_item_pedido(
            pedido_id, self._prod_id, "Cazuela", 2, 12000, 24000
        )
        self._pedido_id = pedido_id

    def test_desactivar_producto_conserva_items(self):
        """Tras desactivar el producto, los ítems del pedido permanecen intactos."""
        db_manager.desactivar_producto(self._prod_id)
        items = db_manager.obtener_items_pedido(self._pedido_id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["nombre_producto"], "Cazuela")

    def test_eliminar_producto_con_historial_falla(self):
        """DELETE en producto referenciado por pedido_items viola FK RESTRICT."""
        with self.assertRaises(sqlite3.IntegrityError):
            con = db_manager.obtener_conexion()
            con.execute("DELETE FROM productos WHERE id=?", (self._prod_id,))
            con.commit()
            con.close()


# ---------------------------------------------------------------------------
# TC-06 — benchmark: resumen mensual con 10k facturas < 2s
# ---------------------------------------------------------------------------

class TestBenchmarkReporteMensual(unittest.TestCase):
    """TC-06: obtener_resumen_ventas_mes sobre 10k facturas debe completarse en < 2s."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        db_manager.RUTA_DB = Path(self._tmpdir) / "test.db"
        db_manager.init_db()

        con = db_manager.obtener_conexion()
        # Catálogo mínimo
        con.execute("INSERT INTO categorias (nombre) VALUES ('Cat')")
        con.execute(
            "INSERT INTO productos (categoria_id, nombre, precio, stock) VALUES (1, 'Prod', 5000, 9999)"
        )
        pedido_id = con.execute(
            "INSERT INTO pedidos (mesa_id, fecha, hora) VALUES (1, '2026-06-01', '08:00:00')"
        ).lastrowid

        # Batch de 10 000 facturas repartidas en los 30 días de junio
        # Máx por día: ceil(10000/30) = 334 < 999 → sufijo :03d válido, length=16 siempre
        facturas = []
        detalles = []
        for i in range(10000):
            dia = (i % 30) + 1
            num_dia = (i // 30) + 1
            fecha = f"2026-06-{dia:02d}"
            numero = f"FAC-202606{dia:02d}-{num_dia:03d}"
            facturas.append((
                numero, pedido_id, 1, fecha, "10:00:00",
                5000, 0, "efectivo", 0, None,
            ))
            detalles.append((i + 1, 1, "Prod", 1, 5000, 5000))

        con.executemany(
            """INSERT INTO facturas
               (numero, pedido_id, mesa_id, fecha, hora, total, descuento,
                metodo_pago, es_parcial, grupo_division)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            facturas,
        )
        con.executemany(
            """INSERT INTO factura_detalles
               (factura_id, producto_id, nombre_producto, cantidad, precio_unitario, subtotal)
               VALUES (?, ?, ?, ?, ?, ?)""",
            detalles,
        )
        con.commit()
        con.close()

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_resumen_10k_facturas_menor_2s(self):
        """obtener_resumen_ventas_mes con 10k filas debe completarse en < 2s."""
        inicio = time.time()
        resultado = db_manager.obtener_resumen_ventas_mes(2026, 6)
        elapsed = time.time() - inicio

        self.assertEqual(resultado["numero_facturas"], 10000)
        self.assertEqual(resultado["total_ventas"], 10000 * 5000)
        self.assertLess(
            elapsed, 2.0,
            f"Resumen mensual tardó {elapsed:.3f}s (umbral: 2.0s para hardware objetivo)",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
