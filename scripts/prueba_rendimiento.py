"""Pruebas de rendimiento offline para el hardware objetivo (HP Pavilion dv4).

Mide tiempos y memoria pico en operaciones críticas usando una BD temporal
con datos de carga realista. No modifica restaurante.db.

Uso (desde la raíz del proyecto):
    python scripts/prueba_rendimiento.py
    python scripts/prueba_rendimiento.py --simular-dv4
    python scripts/prueba_rendimiento.py --simular-dv4 --reservar-memoria-mb 512
    python scripts/prueba_rendimiento.py --productos 300 --facturas-dia 150
    python scripts/prueba_rendimiento.py --salida resultados_rendimiento.txt

Modo --simular-dv4 (Windows): 1 núcleo, prioridad baja y opcional reserva RAM.
Aproximación software del HP Pavilion dv4; no sustituye prueba en el equipo real.

Umbrales orientados a Core 2 Duo / 2–4 GB RAM. En un equipo más rápido
todos deberían pasar; en el dv4 sirven para detectar regresiones.
"""

import argparse
import ctypes
import gc
import platform
import shutil
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import bcrypt

import database.db_manager as db_manager
from config import ADMIN_INICIAL_PASSWORD, PAGINA_TAMANO_DEFAULT
from models.usuario import Usuario
from reports import exportar_pdf
from services import auth_service, facturacion_service, pedido_service, reporte_service
from services import plantilla_factura_service


# Umbrales en segundos (conservadores para Core 2 Duo).
_UMBRALES = {
    "init_db": 3.0,
    "pagina_usuarios_50": 0.15,
    "catalogo_pos": 0.35,
    "listar_mesas": 0.05,
    "crear_factura": 0.5,
    "datos_impresion_recibo": 0.2,
    "vista_previa_plantilla": 0.25,
    "reporte_diario_consolidar": 4.0,
    "exportar_pdf_diario": 8.0,
    "bcrypt_login": 4.0,
}


@dataclass
class ResultadoPrueba:
    """Resultado de una prueba de rendimiento."""

    nombre: str
    segundos: float
    umbral_seg: float
    memoria_kb: Optional[int] = None
    detalle: str = ""

    @property
    def estado(self) -> str:
        """Retorna OK, ADVERTENCIA o FALLO según el umbral."""
        if self.segundos <= self.umbral_seg:
            return "OK"
        if self.segundos <= self.umbral_seg * 1.5:
            return "ADVERTENCIA"
        return "FALLO"


# Perfil HP Pavilion dv4 (referencia nota de contexto).
_PERFIL_DV4 = {
    "nucleos": 1,
    "ram_objetivo_gb": 2,
    "descripcion": "Core 2 Duo ~1 núcleo efectivo, 2 GB RAM, prioridad baja",
}

_BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
_NORMAL_PRIORITY_CLASS = 0x00000020


class _SimulacionDv4:
    """
    Limita CPU y RAM del proceso para aproximar el equipo objetivo.

    En Windows fija afinidad a un núcleo y prioridad por debajo de lo normal.
    Opcionalmente reserva RAM para simular un sistema con poca memoria libre.
    """

    def __init__(self, reservar_memoria_mb: int = 0, iteraciones: int = 3):
        self._reservar_mb = max(0, reservar_memoria_mb)
        self._iteraciones = max(1, iteraciones)
        self._bloque_ram = None
        self._handle = None
        self._prioridad_anterior = None
        self._afinidad_anterior = None
        self._activa = False

    @property
    def iteraciones_medicion(self) -> int:
        """Número de repeticiones por prueba (peor caso bajo limitación)."""
        return self._iteraciones if self._activa else 1

    def aplicar(self) -> List[str]:
        """Aplica límites; retorna líneas descriptivas para el informe."""
        notas = [
            "SIMULACIÓN ACTIVA: {}".format(_PERFIL_DV4["descripcion"]),
            "  Núcleos efectivos: {}".format(_PERFIL_DV4["nucleos"]),
            "  Iteraciones por prueba (máximo): {}".format(self._iteraciones),
        ]
        if sys.platform == "win32":
            try:
                kernel32 = ctypes.windll.kernel32
                self._handle = kernel32.GetCurrentProcess()
                self._prioridad_anterior = kernel32.GetPriorityClass(
                    self._handle
                )
                kernel32.SetPriorityClass(
                    self._handle, _BELOW_NORMAL_PRIORITY_CLASS
                )
                afinidad_anterior = ctypes.c_size_t()
                sistema = ctypes.c_size_t()
                kernel32.GetProcessAffinityMask(
                    self._handle,
                    ctypes.byref(afinidad_anterior),
                    ctypes.byref(sistema),
                )
                self._afinidad_anterior = int(afinidad_anterior.value)
                mascara = 1 << (_PERFIL_DV4["nucleos"] - 1)
                kernel32.SetProcessAffinityMask(
                    self._handle, ctypes.c_size_t(mascara)
                )
                notas.append(
                    "  Prioridad: BELOW_NORMAL | Afinidad máscara: {}".format(
                        mascara
                    )
                )
            except Exception as error:
                notas.append(
                    "  AVISO: no se pudo limitar CPU ({})".format(error)
                )
        else:
            notas.append(
                "  AVISO: limitación de núcleos solo en Windows; "
                "ejecute en el equipo objetivo para medición fiel."
            )

        if self._reservar_mb > 0:
            try:
                self._bloque_ram = bytearray(self._reservar_mb * 1024 * 1024)
                notas.append(
                    "  RAM reservada en proceso: {} MB".format(self._reservar_mb)
                )
            except MemoryError:
                notas.append(
                    "  AVISO: no se pudo reservar {} MB".format(self._reservar_mb)
                )

        self._activa = True
        return notas

    def restaurar(self) -> None:
        """Restaura prioridad y afinidad del proceso."""
        if not self._activa or sys.platform != "win32" or self._handle is None:
            self._bloque_ram = None
            return
        try:
            kernel32 = ctypes.windll.kernel32
            if self._prioridad_anterior is not None:
                kernel32.SetPriorityClass(self._handle, self._prioridad_anterior)
            if self._afinidad_anterior is not None:
                kernel32.SetProcessAffinityMask(
                    self._handle,
                    ctypes.c_size_t(self._afinidad_anterior),
                )
        except Exception:
            pass
        self._bloque_ram = None
        self._activa = False


def _medir(
    nombre: str,
    umbral: float,
    funcion: Callable[[], None],
    medir_memoria: bool = False,
    iteraciones: int = 1,
) -> ResultadoPrueba:
    """Ejecuta una función y mide tiempo (peor caso si iteraciones > 1)."""
    memoria_kb = None
    segundos = 0.0
    for intento in range(iteraciones):
        gc.collect()
        if medir_memoria and intento == iteraciones - 1:
            tracemalloc.start()
        inicio = time.perf_counter()
        funcion()
        transcurrido = time.perf_counter() - inicio
        if transcurrido > segundos:
            segundos = transcurrido
        if medir_memoria and intento == iteraciones - 1:
            _, pico = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memoria_kb = int(pico / 1024)
    detalle = ""
    if iteraciones > 1:
        detalle = "máx. de {} corridas".format(iteraciones)
    return ResultadoPrueba(nombre, segundos, umbral, memoria_kb, detalle)


def _sembrar_productos(cantidad: int) -> int:
    """Inserta categorías y productos activos para pruebas de catálogo."""
    cat_id = db_manager.crear_categoria("Benchmark")
    for i in range(cantidad):
        db_manager.crear_producto(
            cat_id,
            f"Producto benchmark {i + 1:04d}",
            5000 + (i % 20) * 500,
            100,
        )
    return cat_id


def _sembrar_facturas_dia(fecha: str, cantidad: int, cat_id: int) -> None:
    """Registra facturas de un día para pruebas de reportes."""
    prod_id = db_manager.crear_producto(cat_id, "Ítem reporte", 10000, 999)
    for i in range(cantidad):
        mesa_id = (i % 11) + 1
        pedido_id = db_manager.crear_pedido(mesa_id, fecha, "12:00:00")
        db_manager.agregar_item_pedido(
            pedido_id, prod_id, "Ítem reporte", 1, 10000, 10000
        )
        db_manager.registrar_factura_completa(
            pedido_id=pedido_id,
            mesa_id=mesa_id,
            fecha=fecha,
            hora="12:{:02d}:00".format(i % 60),
            total=10000,
            descuento=0,
            metodo_pago="efectivo",
            detalles=[
                {
                    "producto_id": prod_id,
                    "nombre_producto": "Ítem reporte",
                    "cantidad": 1,
                    "precio_unitario": 10000,
                    "subtotal": 10000,
                }
            ],
            es_parcial=0,
            grupo_division=None,
        )
        db_manager.cerrar_pedido(pedido_id)


def _configurar_sesion_admin() -> None:
    """Simula sesión de administrador para services con @requiere_rol."""
    auth_service._usuario_actual = Usuario(
        id=1,
        nombre="Admin Benchmark",
        usuario="admin",
        rol="administrador",
    )


def ejecutar_pruebas(
    productos: int,
    facturas_dia: int,
    simulacion: Optional[_SimulacionDv4] = None,
) -> Tuple[List[ResultadoPrueba], dict]:
    """
    Ejecuta la batería de benchmarks en BD temporal.
    Retorna (resultados, metadatos del entorno).
    """
    if simulacion is None:
        simulacion = _SimulacionDv4()
    reps = simulacion.iteraciones_medicion

    resultados: List[ResultadoPrueba] = []
    tmpdir = tempfile.mkdtemp(prefix="pos_bench_")
    db_manager.RUTA_DB = Path(tmpdir) / "benchmark.db"

    try:
        resultados.append(
            _medir(
                "init_db (schema + mesas + admin)",
                _UMBRALES["init_db"],
                db_manager.init_db,
                iteraciones=1,
            )
        )

        _configurar_sesion_admin()
        cat_id = _sembrar_productos(productos)

        resultados.append(
            _medir(
                "Paginación usuarios (50 filas)",
                _UMBRALES["pagina_usuarios_50"],
                lambda: db_manager.obtener_usuarios_pagina(1),
                iteraciones=reps,
            )
        )

        resultados.append(
            _medir(
                "Catálogo POS ({} productos activos)".format(productos),
                _UMBRALES["catalogo_pos"]
                if productos <= 200
                else _UMBRALES["catalogo_pos"] * 2,
                lambda: pedido_service.obtener_catalogo_agrupado(""),
                medir_memoria=True,
                iteraciones=reps,
            )
        )

        resultados.append(
            _medir(
                "Listar 11 mesas",
                _UMBRALES["listar_mesas"],
                lambda: db_manager.obtener_todas_mesas(),
                iteraciones=reps,
            )
        )

        pedido_id = db_manager.crear_pedido(1, "2026-06-29", "14:00:00")
        prod_id = db_manager.crear_producto(cat_id, "Plato prueba", 18000, 10)
        db_manager.agregar_item_pedido(
            pedido_id, prod_id, "Plato prueba", 2, 18000, 36000
        )

        factura_holder = {"id": None}

        def _crear_factura():
            factura = facturacion_service.crear_factura(
                pedido_id, "efectivo", 0, "Cliente prueba", "900123456"
            )
            factura_holder["id"] = factura.id

        resultados.append(
            _medir(
                "crear_factura (1 pedido)",
                _UMBRALES["crear_factura"],
                _crear_factura,
                iteraciones=1,
            )
        )

        db_manager.cerrar_pedido(pedido_id)

        factura_id = factura_holder["id"]
        resultados.append(
            _medir(
                "obtener_datos_impresion (recibo)",
                _UMBRALES["datos_impresion_recibo"],
                lambda: facturacion_service.obtener_datos_impresion(factura_id),
                iteraciones=reps,
            )
        )

        resultados.append(
            _medir(
                "generar_vista_previa plantilla",
                _UMBRALES["vista_previa_plantilla"],
                lambda: plantilla_factura_service.generar_vista_previa(
                    titulo_documento="Factura Electrónica de Venta",
                    razon_social="Restaurante Hogareños",
                ),
                iteraciones=reps,
            )
        )

        fecha_reporte = "2026-06-28"
        _sembrar_facturas_dia(fecha_reporte, facturas_dia, cat_id)

        resultados.append(
            _medir(
                "reporte_diario consolidar ({} facturas)".format(facturas_dia),
                _UMBRALES["reporte_diario_consolidar"],
                lambda: reporte_service.reporte_diario(fecha_reporte),
                medir_memoria=True,
                iteraciones=reps,
            )
        )

        reporte = reporte_service.reporte_diario(fecha_reporte)
        ruta_pdf = Path(tmpdir) / "reporte_benchmark.pdf"

        resultados.append(
            _medir(
                "exportar_reporte_diario_pdf",
                _UMBRALES["exportar_pdf_diario"],
                lambda: exportar_pdf.exportar_reporte_diario_pdf(
                    reporte, ruta_pdf
                ),
                iteraciones=reps,
            )
        )

        fila_admin = db_manager.obtener_usuario_por_nombre("admin")
        hash_guardado = fila_admin["password_hash"].encode("utf-8")

        def _verificar_bcrypt():
            bcrypt.checkpw(
                ADMIN_INICIAL_PASSWORD.encode("utf-8"),
                hash_guardado,
            )

        resultados.append(
            _medir(
                "bcrypt.checkpw (login)",
                _UMBRALES["bcrypt_login"],
                _verificar_bcrypt,
                iteraciones=reps,
            )
        )

    finally:
        auth_service.cerrar_sesion()
        shutil.rmtree(tmpdir, ignore_errors=True)

    ram_total_mb = None
    if sys.platform == "win32":
        try:
            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            estado = _MemStatus()
            estado.dwLength = ctypes.sizeof(estado)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
                ram_total_mb = int(estado.ullTotalPhys / (1024 * 1024))
        except Exception:
            pass

    meta = {
        "python": sys.version.split()[0],
        "plataforma": platform.platform(),
        "procesador": platform.processor() or platform.machine(),
        "productos_sembrados": productos,
        "facturas_dia_sembradas": facturas_dia,
        "pagina_tamano": PAGINA_TAMANO_DEFAULT,
        "simulacion_dv4": simulacion._activa,
        "notas_simulacion": getattr(simulacion, "_notas_informe", []),
        "ram_sistema_mb": ram_total_mb,
    }
    return resultados, meta


def _formatear_informe(
    resultados: List[ResultadoPrueba],
    meta: dict,
) -> str:
    """Genera informe tipo checklist en texto."""
    lineas = [
        "=" * 60,
        "PRUEBAS DE RENDIMIENTO — POS Restaurante Hogareños",
        "Hardware de referencia: HP Pavilion dv4, Core 2 Duo, 2–4 GB RAM",
        "=" * 60,
        "",
        "Entorno de ejecución:",
        "  Python:     {}".format(meta["python"]),
        "  Plataforma: {}".format(meta["plataforma"]),
        "  CPU:        {}".format(meta["procesador"]),
        "  Productos:  {}".format(meta["productos_sembrados"]),
        "  Facturas/día: {}".format(meta["facturas_dia_sembradas"]),
    ]
    if meta.get("ram_sistema_mb"):
        lineas.append("  RAM sistema: {} MB".format(meta["ram_sistema_mb"]))
    if meta.get("simulacion_dv4"):
        lineas.append("")
        for nota in meta.get("notas_simulacion", []):
            lineas.append(nota)
    lineas.extend(
        [
        "",
        "Resultados automáticos:",
        "-" * 60,
        ]
    )
    ok = adv = fallo = 0
    for r in resultados:
        estado = r.estado
        if estado == "OK":
            ok += 1
        elif estado == "ADVERTENCIA":
            adv += 1
        else:
            fallo += 1
        mem = ""
        if r.memoria_kb is not None:
            mem = " | mem ~{} KB".format(r.memoria_kb)
        lineas.append(
            "[{estado:11}] {nombre}: {seg:.3f}s (umbral {umb:.2f}s){mem}{det}".format(
                estado=estado,
                nombre=r.nombre,
                seg=r.segundos,
                umb=r.umbral_seg,
                mem=mem,
                det=" — {}".format(r.detalle) if r.detalle else "",
            )
        )
    lineas.extend(
        [
            "-" * 60,
            "Resumen: {} OK | {} ADVERTENCIA | {} FALLO".format(ok, adv, fallo),
            "",
            "CHECKLIST MANUAL EN EL EQUIPO OBJETIVO",
            "(marcar tras probar con el .exe o python main.py)",
            "",
            "[ ] Arranque hasta login visible                    < 15 s",
            "[ ] Login (admin) hasta ventana principal           < 5 s",
            "[ ] Abrir mapa de mesas (primera vez)               < 2 s",
            "[ ] Abrir POS desde una mesa                        < 2 s",
            "[ ] Buscar producto en catálogo (teclear 3 letras)  < 0.5 s",
            "[ ] Cerrar sesión y volver a entrar                 sin errores UI",
            "[ ] Abrir Configuración (desplegables + vista previa) < 3 s",
            "[ ] Abrir Inventario / Menú / Reportes              < 2 s cada uno",
            "[ ] Facturar e imprimir (sin impresora: solo registro) < 3 s",
            "[ ] Exportar PDF reporte del día                      < 10 s",
            "[ ] RAM total del proceso (Administrador tareas)      < 250 MB en uso normal",
            "",
            "Nota: Python 3.9 requiere Windows 8.1+. Si el equipo es Vista,",
            "validar primero que el runtime arranque antes de estas pruebas.",
            "=" * 60,
        ]
    )
    return "\n".join(lineas)


def main() -> int:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(
        description="Benchmark offline del POS (BD temporal, sin red)."
    )
    parser.add_argument(
        "--productos",
        type=int,
        default=120,
        help="Productos activos a sembrar para catálogo POS (default: 120)",
    )
    parser.add_argument(
        "--facturas-dia",
        type=int,
        default=80,
        help="Facturas de un día para reporte (default: 80)",
    )
    parser.add_argument(
        "--salida",
        type=str,
        default="",
        help="Ruta opcional para guardar el informe en texto",
    )
    parser.add_argument(
        "--simular-dv4",
        action="store_true",
        help="Limita a 1 núcleo y prioridad baja (aprox. HP Pavilion dv4)",
    )
    parser.add_argument(
        "--reservar-memoria-mb",
        type=int,
        default=0,
        help="Reserva RAM en el proceso (ej. 512 para simular 2 GB totales)",
    )
    parser.add_argument(
        "--iteraciones",
        type=int,
        default=3,
        help="Repeticiones por prueba en modo simulación; toma el peor tiempo",
    )
    args = parser.parse_args()

    if args.productos < 1 or args.facturas_dia < 1:
        print("productos y facturas-dia deben ser >= 1", file=sys.stderr)
        return 2

    reserva_mb = args.reservar_memoria_mb
    if args.simular_dv4 and reserva_mb == 0:
        reserva_mb = 512

    sim = _SimulacionDv4(
        reservar_memoria_mb=reserva_mb if args.simular_dv4 else 0,
        iteraciones=args.iteraciones if args.simular_dv4 else 1,
    )

    modo = "con simulación dv4" if args.simular_dv4 else "sin simulación"
    print("Ejecutando pruebas de rendimiento (BD temporal, {})...".format(modo))

    sim._notas_informe = []
    if args.simular_dv4:
        sim._notas_informe = sim.aplicar()

    try:
        resultados, meta = ejecutar_pruebas(
            args.productos,
            args.facturas_dia,
            simulacion=sim,
        )
    finally:
        sim.restaurar()

    meta["notas_simulacion"] = sim._notas_informe
    informe = _formatear_informe(resultados, meta)
    print(informe)

    if args.salida:
        Path(args.salida).write_text(informe, encoding="utf-8")
        print("Informe guardado en: {}".format(args.salida))

    if any(r.estado == "FALLO" for r in resultados):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
