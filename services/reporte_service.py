"""Consolidación de datos para reportes diarios y mensuales.

Flujo de capas: ui/ -> services/reporte_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import database.db_manager as db
from config import METODOS_PAGO, PAGINA_TAMANO_DEFAULT
from models.cierre import Cierre
from services.auth_service import requiere_rol
from services import hora_service


def _validar_fecha(fecha: str) -> None:
    """Valida formato ISO y rangos semánticos básicos de una fecha."""
    if len(fecha) != 10 or fecha[4] != "-" or fecha[7] != "-":
        raise ValueError(f"Fecha inválida: '{fecha}'. Use formato YYYY-MM-DD.")
    try:
        anio, mes, dia = (int(p) for p in fecha.split("-"))
    except ValueError:
        raise ValueError(f"Fecha inválida: '{fecha}'.")
    if not (1 <= mes <= 12 and 1 <= dia <= 31 and anio >= 1):
        raise ValueError(f"Fecha fuera de rango: '{fecha}'.")


def _validar_anio_mes(anio: int, mes: int) -> None:
    """Valida año y mes para consultas mensuales."""
    if anio < 1:
        raise ValueError(f"Año inválido: {anio}.")
    if not (1 <= mes <= 12):
        raise ValueError(f"Mes inválido: {mes}. Debe estar entre 1 y 12.")


def _cierre_desde_fila(fila) -> Cierre:
    """Convierte una fila sqlite3.Row de cierres_diarios en instancia Cierre."""
    return Cierre(
        id=fila["id"],
        fecha=fila["fecha"],
        total_ventas=fila["total_ventas"],
        numero_facturas=fila["numero_facturas"],
        generado_en=fila["generado_en"],
    )


def _cierre_a_dict(cierre: Cierre) -> Dict[str, Any]:
    """Serializa un Cierre a dict para el reporte mensual."""
    return {
        "id": cierre.id,
        "fecha": cierre.fecha,
        "total_ventas": cierre.total_ventas,
        "numero_facturas": cierre.numero_facturas,
        "generado_en": cierre.generado_en,
    }


def _consolidar_totales_por_metodo_pago(fecha: str) -> Dict[str, int]:
    """Arma totales netos por método de pago; métodos sin ventas quedan en 0."""
    totales = {codigo: 0 for codigo, _ in METODOS_PAGO}
    for fila in db.obtener_totales_ventas_dia_por_metodo_pago(fecha):
        metodo = fila["metodo_pago"]
        if metodo in totales:
            totales[metodo] = int(fila["total"])
    return totales


def _cargar_detalle_ventas_dia(fecha: str) -> List[Dict[str, Any]]:
    """
    Carga renglones de venta del día agrupados por número de factura.
    Pagina en bloques para no cargar todo el día en memoria de una vez.
    """
    detalle: List[Dict[str, Any]] = []
    pagina = 1

    while True:
        filas = db.obtener_detalles_ventas_dia_pagina(
            fecha, pagina, PAGINA_TAMANO_DEFAULT
        )
        if not filas:
            break

        for fila in filas:
            detalle.append(
                {
                    "factura_numero": fila["factura_numero"],
                    "metodo_pago": fila["metodo_pago"],
                    "comprador_nombre": fila["comprador_nombre"] or "",
                    "producto_id": fila["producto_id"],
                    "nombre_producto": fila["nombre_producto"],
                    "cantidad": int(fila["cantidad"]),
                    "subtotal": int(fila["subtotal"]),
                }
            )

        if len(filas) < PAGINA_TAMANO_DEFAULT:
            break
        pagina += 1

    return detalle


def _cargar_cierres_mes(anio: int, mes: int) -> List[Cierre]:
    """Carga todos los cierres diarios del mes paginando desde SQLite."""
    total = db.obtener_total_cierres_mes(anio, mes)
    if total == 0:
        return []

    cierres: List[Cierre] = []
    pagina = 1
    while len(cierres) < total:
        filas = db.obtener_cierres_mes_pagina(
            anio, mes, pagina, PAGINA_TAMANO_DEFAULT
        )
        if not filas:
            break
        cierres.extend(_cierre_desde_fila(fila) for fila in filas)
        pagina += 1

    return cierres


def _registrar_cierre_si_ausente(
    fecha: str, total_ventas: int, numero_facturas: int
) -> Tuple[bool, Optional[Cierre]]:
    """
    Inserta un cierre diario si no existe para la fecha.
    Retorna (registrado_nuevo, cierre).
    """
    existente = db.obtener_cierre_por_fecha(fecha)
    if existente is not None:
        return False, _cierre_desde_fila(existente)

    generado_en = hora_service.obtener_datetime_actual().isoformat(timespec="seconds")
    cierre_id = db.crear_cierre_diario(
        fecha, total_ventas, numero_facturas, generado_en
    )
    fila = db.obtener_cierre_por_fecha(fecha)
    if fila is None:
        raise RuntimeError(f"No se pudo recuperar el cierre recién creado ({fecha}).")
    return True, Cierre(
        id=cierre_id,
        fecha=fecha,
        total_ventas=total_ventas,
        numero_facturas=numero_facturas,
        generado_en=generado_en,
    )


@requiere_rol("supervisor", "administrador")
def reporte_diario(fecha: str) -> Dict[str, Any]:
    """
    Consolida las ventas pagadas de un día y registra el cierre en cierres_diarios.

    Retorna dict con total_ventas, numero_facturas, detalle_ventas
    (renglones por factura) y totales_por_metodo_pago.
    """
    _validar_fecha(fecha)

    resumen = db.obtener_resumen_ventas_dia(fecha)
    total_ventas = int(resumen["total_ventas"])
    numero_facturas = int(resumen["numero_facturas"])
    detalle_ventas = _cargar_detalle_ventas_dia(fecha)
    totales_por_metodo_pago = _consolidar_totales_por_metodo_pago(fecha)

    cierre_nuevo, cierre = _registrar_cierre_si_ausente(
        fecha, total_ventas, numero_facturas
    )

    return {
        "fecha": fecha,
        "total_ventas": total_ventas,
        "numero_facturas": numero_facturas,
        "detalle_ventas": detalle_ventas,
        "totales_por_metodo_pago": totales_por_metodo_pago,
        "cierre_registrado": cierre_nuevo,
        "cierre": _cierre_a_dict(cierre),
    }


@requiere_rol("administrador")
def reporte_mensual(anio: int, mes: int) -> Dict[str, Any]:
    """
    Consolida las ventas pagadas de un mes y lista los cierres diarios registrados.

    Retorna dict con total_ventas, numero_facturas y cierres_diarios
    (cada uno con id, fecha, total_ventas, numero_facturas, generado_en).
    """
    _validar_anio_mes(anio, mes)

    resumen = db.obtener_resumen_ventas_mes(anio, mes)
    cierres = _cargar_cierres_mes(anio, mes)

    return {
        "anio": anio,
        "mes": mes,
        "total_ventas": int(resumen["total_ventas"]),
        "numero_facturas": int(resumen["numero_facturas"]),
        "cierres_diarios": [_cierre_a_dict(cierre) for cierre in cierres],
    }


def _factura_resumen_desde_fila(fila) -> Dict[str, Any]:
    """Serializa una fila de facturas para listados en reportes."""
    total_neto = int(fila["total"]) - int(fila["descuento"])
    return {
        "id": fila["id"],
        "numero": fila["numero"],
        "fecha": fila["fecha"],
        "hora": fila["hora"],
        "total": int(fila["total"]),
        "descuento": int(fila["descuento"]),
        "total_neto": total_neto,
        "estado": fila["estado"],
        "comprador_nombre": fila["comprador_nombre"] or "",
    }


def _calcular_total_paginas(total: int, por_pagina: int) -> int:
    """Calcula el número de páginas para un listado paginado."""
    if total <= 0:
        return 1
    return max(1, math.ceil(total / por_pagina))


@requiere_rol("supervisor", "administrador")
def listar_facturas_dia(
    fecha: str, pagina: int = 1, por_pagina: int = PAGINA_TAMANO_DEFAULT
) -> Dict[str, Any]:
    """
    Retorna el historial paginado de facturas de un día.

    Cada factura incluye id, numero, hora, total_neto, comprador_nombre y estado.
    """
    _validar_fecha(fecha)
    pagina = max(1, pagina)
    total = db.obtener_total_facturas_fecha(fecha)
    filas = db.obtener_facturas_por_fecha_pagina(fecha, pagina, por_pagina)
    return {
        "fecha": fecha,
        "facturas": [_factura_resumen_desde_fila(fila) for fila in filas],
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total": total,
        "total_paginas": _calcular_total_paginas(total, por_pagina),
    }


@requiere_rol("supervisor", "administrador")
def contar_cola_impresion() -> int:
    """Retorna cuántas facturas están pendientes de impresión."""
    return db.obtener_total_cola_impresion()


@requiere_rol("supervisor", "administrador")
def listar_cola_impresion(
    pagina: int = 1, por_pagina: int = PAGINA_TAMANO_DEFAULT
) -> Dict[str, Any]:
    """
    Retorna facturas que no se pudieron imprimir y quedaron en cola.

    Cada registro incluye datos de la factura y el último error registrado.
    """
    pagina = max(1, pagina)
    total = db.obtener_total_cola_impresion()
    filas = db.obtener_cola_impresion_pagina(pagina, por_pagina)
    registros: List[Dict[str, Any]] = []
    for fila in filas:
        total_neto = int(fila["total"]) - int(fila["descuento"])
        registros.append(
            {
                "cola_id": fila["cola_id"],
                "factura_id": fila["factura_id"],
                "numero": fila["numero"],
                "fecha": fila["fecha"],
                "hora": fila["hora"],
                "total_neto": total_neto,
                "error_ultimo": fila["error_ultimo"] or "",
                "intentos": int(fila["intentos"]),
                "registrado_en": fila["registrado_en"],
            }
        )
    return {
        "registros": registros,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total": total,
        "total_paginas": _calcular_total_paginas(total, por_pagina),
    }
