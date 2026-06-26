"""Tests de integración para services/menu_service.py.

Ejecutar desde la raíz del proyecto:
    python -m unittest tests.test_menu_service -v
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import database.db_manager as db_manager
from models.usuario import Usuario
from services import auth_service, menu_service


class _MenuBdTemporal(unittest.TestCase):
    """BD temporal con sesión de supervisor para pruebas de menú."""

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


class TestCategoriasMenu(_MenuBdTemporal):
    """CRUD de categorías."""

    def test_crear_y_listar_categoria(self):
        categoria = menu_service.crear_categoria("Bebidas")
        self.assertEqual(categoria.nombre, "Bebidas")

        categorias, total, paginas = menu_service.listar_categorias_pagina()
        self.assertEqual(total, 1)
        self.assertEqual(categorias[0].nombre, "Bebidas")
        self.assertGreaterEqual(paginas, 1)

    def test_renombrar_categoria(self):
        categoria = menu_service.crear_categoria("Postres")
        actualizada = menu_service.renombrar_categoria(categoria.id, "Dulces")
        self.assertEqual(actualizada.nombre, "Dulces")


class TestProductosMenu(_MenuBdTemporal):
    """CRUD y activación de productos."""

    def setUp(self):
        super().setUp()
        self._categoria = menu_service.crear_categoria("Platos")

    def test_crear_listar_y_editar_producto(self):
        producto = menu_service.crear_producto(
            self._categoria.id, "Bandeja paisa", 18000, 20
        )
        self.assertEqual(producto.nombre, "Bandeja paisa")
        self.assertEqual(producto.nombre_categoria, "Platos")

        productos, total, _paginas = menu_service.listar_productos_pagina()
        self.assertEqual(total, 1)
        self.assertEqual(productos[0].id, producto.id)

        actualizado = menu_service.actualizar_producto(
            producto.id, self._categoria.id, "Bandeja típica", 20000, 15
        )
        self.assertEqual(actualizado.nombre, "Bandeja típica")
        self.assertEqual(actualizado.precio, 20000)

    def test_desactivar_y_activar_producto(self):
        producto = menu_service.crear_producto(
            self._categoria.id, "Sopa", 7000, 10
        )
        inactivo = menu_service.desactivar_producto(producto.id)
        self.assertFalse(inactivo.esta_activo())

        productos, total, _paginas = menu_service.listar_productos_pagina()
        self.assertEqual(total, 1)
        self.assertEqual(productos[0].activo, 0)

        activo = menu_service.activar_producto(producto.id)
        self.assertTrue(activo.esta_activo())

    def test_filtro_por_categoria(self):
        otra = menu_service.crear_categoria("Bebidas")
        menu_service.crear_producto(self._categoria.id, "Arroz", 5000, 5)
        menu_service.crear_producto(otra.id, "Jugo", 3000, 5)

        filtrados, total, _paginas = menu_service.listar_productos_pagina(
            categoria_id=otra.id
        )
        self.assertEqual(total, 1)
        self.assertEqual(filtrados[0].nombre, "Jugo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
