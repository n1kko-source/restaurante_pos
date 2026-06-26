"""Consolidación de datos para reportes diarios y mensuales.

Flujo de capas: ui/ -> services/reporte_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import database.db_manager as db
from config import PAGINA_TAMANO_DEFAULT
from models.cierre import Cierre
from services.auth_service import requiere_rol


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


def _consolidar_ventas_por_producto(fecha: str) -> List[Dict[str, Any]]:
    """
    Agrega ventas por producto leyendo renglones paginados (cursor por páginas).
    No carga todos los detalles del día en memoria de una sola vez.
    """
    acumulado: Dict[int, Dict[str, Any]] = {}
    pagina = 1

    while True:
        filas = db.obtener_detalles_ventas_dia_pagina(
            fecha, pagina, PAGINA_TAMANO_DEFAULT
        )
        if not filas:
            break

        for fila in filas:
            producto_id = fila["producto_id"]
            if producto_id not in acumulado:
                acumulado[producto_id] = {
                    "producto_id": producto_id,
                    "nombre_producto": fila["nombre_producto"],
                    "cantidad": 0,
                    "subtotal": 0,
                }
            acumulado[producto_id]["cantidad"] += fila["cantidad"]
            acumulado[producto_id]["subtotal"] += fila["subtotal"]

        if len(filas) < PAGINA_TAMANO_DEFAULT:
            break
        pagina += 1

    return sorted(
        acumulado.values(),
        key=lambda item: item["nombre_producto"].lower(),
    )


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

    generado_en = datetime.now().isoformat(timespec="seconds")
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

    Retorna dict con total_ventas, numero_facturas y ventas_por_producto
    (lista de {producto_id, nombre_producto, cantidad, subtotal}).
    """
    _validar_fecha(fecha)

    resumen = db.obtener_resumen_ventas_dia(fecha)
    total_ventas = int(resumen["total_ventas"])
    numero_facturas = int(resumen["numero_facturas"])
    ventas_por_producto = _consolidar_ventas_por_producto(fecha)

    cierre_nuevo, cierre = _registrar_cierre_si_ausente(
        fecha, total_ventas, numero_facturas
    )

    return {
        "fecha": fecha,
        "total_ventas": total_ventas,
        "numero_facturas": numero_facturas,
        "ventas_por_producto": ventas_por_producto,
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
