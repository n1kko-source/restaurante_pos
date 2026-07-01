"""Obtención y corrección manual de fecha y hora local del sistema.

Fuente única de verdad para timestamps del POS. Valida rangos semánticos
antes de insertar en pedidos, facturas, alertas o cierres.
"""

import subprocess
import sys
from datetime import datetime
from typing import Tuple

# Nombres en español para la UI (sin depender de locale del SO).
_DIAS = (
    "lunes", "martes", "miércoles", "jueves",
    "viernes", "sábado", "domingo",
)
_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def obtener_datetime_actual() -> datetime:
    """Retorna el instante actual del reloj local de Windows."""
    return datetime.now()


def validar_fecha(fecha: str) -> None:
    """Valida formato ISO YYYY-MM-DD y rangos semánticos básicos."""
    if len(fecha) != 10 or fecha[4] != "-" or fecha[7] != "-":
        raise ValueError(f"Fecha inválida: '{fecha}'. Use formato YYYY-MM-DD.")
    try:
        anio, mes, dia = (int(p) for p in fecha.split("-"))
    except ValueError:
        raise ValueError(f"Fecha inválida: '{fecha}'.")
    if not (1 <= mes <= 12 and 1 <= dia <= 31 and anio >= 1):
        raise ValueError(f"Fecha fuera de rango: '{fecha}'.")
    # Comprobación calendario real (evita 2026-02-31).
    datetime(anio, mes, dia)


def validar_hora(hora: str) -> None:
    """Valida formato HH:MM:SS y rangos 00-23 / 00-59."""
    if len(hora) != 8 or hora[2] != ":" or hora[5] != ":":
        raise ValueError(f"Hora inválida: '{hora}'. Use formato HH:MM:SS.")
    try:
        horas, minutos, segundos = (int(p) for p in hora.split(":"))
    except ValueError:
        raise ValueError(f"Hora inválida: '{hora}'.")
    if not (0 <= horas <= 23 and 0 <= minutos <= 59 and 0 <= segundos <= 59):
        raise ValueError(f"Hora fuera de rango: '{hora}'.")


def obtener_fecha_hora_actual() -> Tuple[str, str]:
    """
    Retorna (fecha, hora) del reloj local en formatos del schema.
    Valida rangos semánticos antes de usarlos en operaciones de negocio.
    """
    ahora = obtener_datetime_actual()
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M:%S")
    validar_fecha(fecha)
    validar_hora(hora)
    return fecha, hora


def formatear_legible(momento: datetime) -> str:
    """Formatea fecha y hora en español para etiquetas de reloj."""
    dia_semana = _DIAS[momento.weekday()]
    mes = _MESES[momento.month - 1]
    fecha = f"{dia_semana}, {momento.day} de {mes} de {momento.year}"
    hora = momento.strftime("%H:%M:%S")
    return f"{fecha}  —  {hora}"


def abrir_ajuste_hora_windows() -> None:
    """
    Abre el panel de fecha y hora de Windows para corrección manual.
    Requiere permisos de administrador del SO para guardar cambios.
    """
    if sys.platform != "win32":
        raise OSError(
            "El ajuste de hora del sistema solo está disponible en Windows."
        )
    try:
        subprocess.Popen(
            ["control", "timedate.cpl"],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        raise OSError(
            "No se pudo abrir el panel de fecha y hora de Windows."
        ) from error
