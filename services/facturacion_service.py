"""Lógica de facturación: totales, descuentos, numeración y división de cuenta.

Flujo de capas: ui/ -> services/facturacion_service.py -> database/db_manager.py
Este módulo nunca importa CustomTkinter ni nada de ui/.
"""

import time
from typing import Dict, List, Optional, Tuple, Union

from config import METODOS_PAGO_VALIDOS, RESTAURANTE
import database.db_manager as db
from models.factura import Factura, FacturaDetalle
from models.pedido import PedidoItem
from printing.colpos_printer import ColposPrinter, ErrorImpresora
from printing.plantilla_recibo import FacturaImpresion
from services import mesa_service
from services.auth_service import requiere_rol
from services import hora_service

# Asignación compartida entre todas las personas en división de cuenta.
ASIGNACION_TODOS = "todos"

_MIN_PERSONAS_DIVISION = 2
_MAX_PERSONAS_DIVISION = 8

# ============================================================
# HELPERS INTERNOS
# ============================================================

def _obtener_fecha_hora_actual() -> Tuple[str, str]:
    """Delega en hora_service la obtención validada de fecha y hora."""
    return hora_service.obtener_fecha_hora_actual()


def _validar_fecha(fecha: str) -> None:
    """Delega la validación semántica de fecha en hora_service."""
    hora_service.validar_fecha(fecha)


def _validar_hora(hora: str) -> None:
    """Delega la validación semántica de hora en hora_service."""
    hora_service.validar_hora(hora)


def _formatear_numero_factura(fecha: str, secuencia: int) -> str:
    """Construye un número FAC-YYYYMMDD-NNN validando longitud y rango."""
    _validar_fecha(fecha)
    if secuencia < 1 or secuencia > 999:
        raise ValueError(
            f"Secuencia de factura inválida: {secuencia}. Debe estar entre 1 y 999."
        )
    fecha_compacta = fecha.replace("-", "")
    numero = f"FAC-{fecha_compacta}-{secuencia:03d}"
    if len(numero) != 16:
        raise ValueError(f"Número de factura con longitud incorrecta: '{numero}'.")
    return numero


def _factura_desde_fila(fila) -> Factura:
    """Convierte una fila sqlite3.Row de facturas en instancia Factura."""
    keys = fila.keys()
    return Factura(
        id=fila["id"],
        numero=fila["numero"],
        pedido_id=fila["pedido_id"],
        mesa_id=fila["mesa_id"],
        fecha=fila["fecha"],
        hora=fila["hora"],
        total=fila["total"],
        descuento=fila["descuento"],
        metodo_pago=fila["metodo_pago"],
        estado=fila["estado"],
        es_parcial=fila["es_parcial"],
        grupo_division=fila["grupo_division"],
        comprador_nombre=fila["comprador_nombre"] if "comprador_nombre" in keys else "",
        comprador_identificacion=(
            fila["comprador_identificacion"]
            if "comprador_identificacion" in keys
            else ""
        ),
    )


def _detalle_desde_fila(fila) -> FacturaDetalle:
    """Convierte una fila sqlite3.Row de factura_detalles en FacturaDetalle."""
    return FacturaDetalle(
        id=fila["id"],
        factura_id=fila["factura_id"],
        producto_id=fila["producto_id"],
        nombre_producto=fila["nombre_producto"],
        cantidad=fila["cantidad"],
        precio_unitario=fila["precio_unitario"],
        subtotal=fila["subtotal"],
    )


def _validar_metodo_pago(metodo_pago: str) -> None:
    """Lanza ValueError si el método de pago no está permitido por el schema."""
    if metodo_pago not in METODOS_PAGO_VALIDOS:
        raise ValueError(
            f"Método de pago inválido: '{metodo_pago}'. "
            f"Valores permitidos: {', '.join(sorted(METODOS_PAGO_VALIDOS))}."
        )


def _validar_descuento(descuento: int, subtotal_bruto: int) -> None:
    """Valida que el descuento sea un entero no negativo y no supere el subtotal."""
    if descuento < 0:
        raise ValueError("El descuento no puede ser negativo.")
    if descuento > subtotal_bruto:
        raise ValueError(
            f"El descuento ({descuento}) no puede superar el subtotal ({subtotal_bruto})."
        )


def _validar_pedido_facturable(pedido_id: int) -> Tuple[dict, List[PedidoItem]]:
    """
    Valida que el pedido exista, esté abierto y tenga ítems.
    Retorna (fila_pedido, items).
    """
    fila_pedido = db.obtener_pedido_por_id(pedido_id)
    if fila_pedido is None:
        raise ValueError(f"No existe un pedido con id {pedido_id}.")
    if fila_pedido["estado"] != "abierto":
        raise ValueError(
            f"El pedido {pedido_id} no está abierto (estado: '{fila_pedido['estado']}')."
        )

    items = mesa_service.obtener_items_pedido(pedido_id)
    if not items:
        raise ValueError(
            f"El pedido {pedido_id} no tiene ítems. Agregue productos antes de facturar."
        )
    return fila_pedido, items


def _detalle_desde_item(item: PedidoItem) -> dict:
    """Convierte un PedidoItem en dict para factura_detalles."""
    return {
        "producto_id": item.producto_id,
        "nombre_producto": item.nombre_producto,
        "cantidad": item.cantidad,
        "precio_unitario": item.precio_unitario,
        "subtotal": item.subtotal,
    }


def _normalizar_asignacion(valor: Union[int, str]) -> Union[int, str]:
    """Normaliza la asignación de un ítem en división de cuenta."""
    if isinstance(valor, str):
        texto = valor.strip().lower()
        if texto == ASIGNACION_TODOS:
            return ASIGNACION_TODOS
        if texto.isdigit():
            return int(texto)
        raise ValueError(
            f"Asignación inválida: '{valor}'. Use un número de persona (1-N) o 'todos'."
        )
    if isinstance(valor, int):
        return valor
    raise ValueError(
        f"Asignación inválida: '{valor}'. Use un número de persona (1-N) o 'todos'."
    )


def _validar_asignaciones(
    items: List[PedidoItem],
    num_personas: int,
    asignaciones: Dict[int, Union[int, str]],
) -> Dict[int, Union[int, str]]:
    """
    Valida cobertura completa de ítems y rangos de persona.
    Retorna asignaciones normalizadas.
    """
    if num_personas < _MIN_PERSONAS_DIVISION or num_personas > _MAX_PERSONAS_DIVISION:
        raise ValueError(
            f"El número de personas debe estar entre {_MIN_PERSONAS_DIVISION} "
            f"y {_MAX_PERSONAS_DIVISION}."
        )

    ids_pedido = {item.id for item in items}
    if set(asignaciones.keys()) != ids_pedido:
        faltantes = ids_pedido - set(asignaciones.keys())
        sobrantes = set(asignaciones.keys()) - ids_pedido
        mensajes = []
        if faltantes:
            mensajes.append(f"ítems sin asignar: {sorted(faltantes)}")
        if sobrantes:
            mensajes.append(f"asignaciones desconocidas: {sorted(sobrantes)}")
        raise ValueError(
            "Las asignaciones deben cubrir exactamente todos los ítems del pedido "
            f"({'; '.join(mensajes)})."
        )

    normalizadas: Dict[int, Union[int, str]] = {}
    for item_id, valor in asignaciones.items():
        asignacion = _normalizar_asignacion(valor)
        if asignacion != ASIGNACION_TODOS:
            if not (1 <= asignacion <= num_personas):
                raise ValueError(
                    f"La persona {asignacion} del ítem {item_id} está fuera de rango "
                    f"(1 a {num_personas})."
                )
        normalizadas[item_id] = asignacion
    return normalizadas


def _detalle_parte_compartida(item: PedidoItem, monto: int) -> dict:
    """
    Crea un renglón de factura para la parte individual de un ítem compartido.
    Usa cantidad=1 y precio_unitario=monto para cumplir el CHECK del schema.
    """
    return {
        "producto_id": item.producto_id,
        "nombre_producto": item.nombre_producto,
        "cantidad": 1,
        "precio_unitario": monto,
        "subtotal": monto,
    }


def _construir_detalles_por_persona(
    items: List[PedidoItem],
    num_personas: int,
    asignaciones: Dict[int, Union[int, str]],
) -> Dict[int, List[dict]]:
    """Arma los renglones de factura para cada persona según las asignaciones."""
    items_por_id = {item.id: item for item in items}
    detalles_por_persona: Dict[int, List[dict]] = {
        persona: [] for persona in range(1, num_personas + 1)
    }

    for item_id, asignacion in asignaciones.items():
        item = items_por_id[item_id]
        if asignacion == ASIGNACION_TODOS:
            partes = calcular_division_partes_iguales(item.subtotal, num_personas)
            for indice, monto in enumerate(partes):
                if monto > 0:
                    detalles_por_persona[indice + 1].append(
                        _detalle_parte_compartida(item, monto)
                    )
        else:
            detalles_por_persona[asignacion].append(_detalle_desde_item(item))

    return detalles_por_persona


# ============================================================
# API PÚBLICA
# ============================================================

def calcular_division_partes_iguales(total: int, num_personas: int) -> List[int]:
    """
    Reparte un monto total en partes enteras iguales, asignando el residuo
    a las primeras posiciones de la lista para que la suma sea exacta.
    Retorna una lista de N montos en pesos enteros (COP).
    """
    if num_personas <= 0:
        raise ValueError("El número de personas debe ser mayor a cero.")
    if total < 0:
        raise ValueError("El total a dividir no puede ser negativo.")

    parte_base = total // num_personas
    residuo = total - (parte_base * num_personas)
    return [
        parte_base + 1 if indice < residuo else parte_base
        for indice in range(num_personas)
    ]


def generar_numero_factura(fecha: Optional[str] = None) -> str:
    """
    Retorna el siguiente número FAC-YYYYMMDD-NNN que se asignaría en la fecha.

    Consulta el contador diario sin reservarlo; la reserva atómica ocurre
    al registrar la factura con crear_factura() o dividir_cuenta().
    """
    if fecha is None:
        fecha, _ = _obtener_fecha_hora_actual()
    _validar_fecha(fecha)

    siguiente = db.obtener_ultimo_numero_factura(fecha) + 1
    if siguiente > 999:
        raise ValueError(
            f"Límite diario de facturas alcanzado (999) para {fecha}. "
            "Contacte al administrador del sistema."
        )
    return _formatear_numero_factura(fecha, siguiente)


def calcular_total(pedido_id: int, descuento: int = 0) -> int:
    """
    Suma los subtotales del pedido y aplica el descuento.
    Retorna el total neto a pagar en pesos COP enteros.
    """
    fila_pedido = db.obtener_pedido_por_id(pedido_id)
    if fila_pedido is None:
        raise ValueError(f"No existe un pedido con id {pedido_id}.")

    items = mesa_service.obtener_items_pedido(pedido_id)
    subtotal_bruto = sum(item.subtotal for item in items)
    _validar_descuento(descuento, subtotal_bruto)
    return subtotal_bruto - descuento


@requiere_rol("cajero", "supervisor", "administrador")
def crear_factura(
    pedido_id: int,
    metodo_pago: str,
    descuento: int = 0,
    comprador_nombre: str = "",
    comprador_identificacion: str = "",
) -> Factura:
    """
    Registra una factura completa con sus detalles a partir del pedido activo.

    Copia nombre_producto y precios de pedido_items a factura_detalles.
    Reserva el número FAC-YYYYMMDD-NNN de forma atómica en la base de datos.
    """
    _validar_metodo_pago(metodo_pago)
    fila_pedido, items = _validar_pedido_facturable(pedido_id)

    subtotal_bruto = sum(item.subtotal for item in items)
    _validar_descuento(descuento, subtotal_bruto)

    fecha, hora = _obtener_fecha_hora_actual()
    detalles = [_detalle_desde_item(item) for item in items]

    factura_id, numero = db.registrar_factura_completa(
        pedido_id=pedido_id,
        mesa_id=fila_pedido["mesa_id"],
        fecha=fecha,
        hora=hora,
        total=subtotal_bruto,
        descuento=descuento,
        metodo_pago=metodo_pago,
        detalles=detalles,
        es_parcial=0,
        grupo_division=None,
        comprador_nombre=comprador_nombre,
        comprador_identificacion=comprador_identificacion,
    )

    fila_factura = db.obtener_factura_por_id(factura_id)
    if fila_factura is None:
        raise ValueError(
            f"La factura {numero} no pudo recuperarse tras el registro."
        )
    return _factura_desde_fila(fila_factura)


@requiere_rol("cajero", "supervisor", "administrador")
def dividir_cuenta(
    pedido_id: int,
    num_personas: int,
    asignaciones: Dict[int, Union[int, str]],
    metodo_pago: str = "efectivo",
    comprador_nombre: str = "",
    comprador_identificacion: str = "",
) -> List[Factura]:
    """
    Divide el pedido en N facturas independientes según las asignaciones.

    asignaciones: mapa {item_id: persona} donde persona es 1..N, o 'todos'
    para repartir ese ítem en partes iguales entre todas las personas.
    Todas las facturas comparten el mismo grupo_division para trazabilidad.
    """
    _validar_metodo_pago(metodo_pago)
    fila_pedido, items = _validar_pedido_facturable(pedido_id)
    asignaciones_norm = _validar_asignaciones(items, num_personas, asignaciones)

    detalles_por_persona = _construir_detalles_por_persona(
        items, num_personas, asignaciones_norm
    )

    fecha, hora = _obtener_fecha_hora_actual()
    grupo_division = f"split-{pedido_id}-{int(time.time())}"

    facturas: List[Factura] = []
    for persona in range(1, num_personas + 1):
        detalles = detalles_por_persona[persona]
        if not detalles:
            continue

        total_persona = sum(detalle["subtotal"] for detalle in detalles)
        factura_id, _numero = db.registrar_factura_completa(
            pedido_id=pedido_id,
            mesa_id=fila_pedido["mesa_id"],
            fecha=fecha,
            hora=hora,
            total=total_persona,
            descuento=0,
            metodo_pago=metodo_pago,
            detalles=detalles,
            es_parcial=1,
            grupo_division=grupo_division,
            comprador_nombre=comprador_nombre,
            comprador_identificacion=comprador_identificacion,
        )
        fila_factura = db.obtener_factura_por_id(factura_id)
        if fila_factura is None:
            raise ValueError(
                f"No se pudo recuperar la factura parcial de la persona {persona}."
            )
        facturas.append(_factura_desde_fila(fila_factura))

    if not facturas:
        raise ValueError(
            "No se generó ninguna factura. Verifique las asignaciones de ítems."
        )

    total_pedido = sum(item.subtotal for item in items)
    total_facturas = sum(factura.total for factura in facturas)
    if total_facturas != total_pedido:
        raise ValueError(
            f"Inconsistencia en la división: pedido={total_pedido}, "
            f"facturas={total_facturas}."
        )

    return facturas


def preview_totales_division(
    pedido_id: int,
    num_personas: int,
    asignaciones: Dict[int, Union[int, str]],
) -> Dict[int, int]:
    """
    Calcula el total a pagar por cada persona sin registrar facturas.

    Útil para la vista previa en la UI de dividir cuenta.
    Retorna un mapa {persona: total} con personas 1-indexadas.
    """
    fila_pedido = db.obtener_pedido_por_id(pedido_id)
    if fila_pedido is None:
        raise ValueError(f"No existe un pedido con id {pedido_id}.")

    items = mesa_service.obtener_items_pedido(pedido_id)
    if not items:
        raise ValueError(
            f"El pedido {pedido_id} no tiene ítems. Agregue productos antes de dividir."
        )

    asignaciones_norm = _validar_asignaciones(items, num_personas, asignaciones)
    detalles_por_persona = _construir_detalles_por_persona(
        items, num_personas, asignaciones_norm
    )
    return {
        persona: sum(detalle["subtotal"] for detalle in detalles)
        for persona, detalles in detalles_por_persona.items()
    }


def obtener_factura(factura_id: int) -> Optional[Factura]:
    """Retorna la cabecera de una factura por su id, o None si no existe."""
    fila = db.obtener_factura_por_id(factura_id)
    if fila is None:
        return None
    return _factura_desde_fila(fila)


def obtener_detalles_factura(factura_id: int) -> List[FacturaDetalle]:
    """Retorna los renglones de una factura ordenados por id."""
    fila = db.obtener_factura_por_id(factura_id)
    if fila is None:
        raise ValueError(f"No existe una factura con id {factura_id}.")
    filas = db.obtener_detalles_factura(factura_id)
    return [_detalle_desde_fila(fila) for fila in filas]


def obtener_datos_impresion(factura_id: int) -> Optional[FacturaImpresion]:
    """
    Arma el paquete completo de datos para imprimir una factura en Colpos.
    Incluye número de mesa visible si la mesa aún existe en el salón.
    """
    from services import plantilla_factura_service

    factura = obtener_factura(factura_id)
    if factura is None:
        return None

    detalles = obtener_detalles_factura(factura_id)
    mesa = mesa_service.obtener_mesa(factura.mesa_id)
    plantilla = plantilla_factura_service.obtener_config_plantilla()
    return FacturaImpresion(
        factura=factura,
        detalles=detalles,
        mesa_numero=mesa.numero if mesa is not None else None,
        nombre_restaurante=plantilla.get("razon_social") or RESTAURANTE["nombre"],
        direccion_restaurante=plantilla.get("direccion") or RESTAURANTE["direccion"],
        titulo_documento=plantilla.get("titulo_documento", ""),
        razon_social=plantilla.get("razon_social", ""),
        nit=plantilla.get("nit", ""),
        direccion=plantilla.get("direccion", ""),
        regimen_tributario=plantilla.get("regimen_tributario", ""),
        comprador_nombre=factura.comprador_nombre,
        comprador_identificacion=factura.comprador_identificacion,
        ruta_logo=plantilla_factura_service.obtener_ruta_logo_efectiva(),
    )


def _imprimir_datos_factura(datos: FacturaImpresion) -> Tuple[bool, str]:
    """
    Envía una factura a la impresora Colpos.
    Retorna (éxito, mensaje) sin propagar excepciones de hardware.
    """
    impresora = ColposPrinter()
    if not impresora.conectar():
        mensaje = impresora.ultimo_error
        _gestionar_cola_impresion(datos.factura.id, False, mensaje)
        return False, mensaje

    try:
        impresora.imprimir_factura(datos)
        mensaje = f"Factura {datos.factura.numero} enviada a impresora."
        _gestionar_cola_impresion(datos.factura.id, True, "")
        return True, mensaje
    except ErrorImpresora as error:
        mensaje = str(error)
        _gestionar_cola_impresion(datos.factura.id, False, mensaje)
        return False, mensaje
    finally:
        impresora.desconectar()


def _gestionar_cola_impresion(
    factura_id: int, exito: bool, mensaje_error: str
) -> None:
    """Registra o retira una factura de la cola según el resultado de impresión."""
    if exito:
        db.quitar_de_cola_impresion(factura_id)
        return
    registrado_en = hora_service.obtener_datetime_actual().isoformat(
        timespec="seconds"
    )
    db.registrar_cola_impresion(factura_id, mensaje_error, registrado_en)


@requiere_rol("cajero", "supervisor", "administrador")
def imprimir_factura(factura_id: int) -> Tuple[bool, str]:
    """
    Imprime una factura ya registrada en la impresora térmica Colpos.

    Retorna (True, mensaje_ok) o (False, mensaje_error) sin tumbar el POS
    si la impresora no está disponible.
    """
    datos = obtener_datos_impresion(factura_id)
    if datos is None:
        return False, f"No existe una factura con id {factura_id}."
    if not datos.detalles:
        return False, "La factura no tiene renglones para imprimir."
    return _imprimir_datos_factura(datos)


@requiere_rol("cajero", "supervisor", "administrador")
def facturar_e_imprimir_pedido(
    pedido_id: int,
    metodo_pago: str,
    descuento: int = 0,
    comprador_nombre: str = "",
    comprador_identificacion: str = "",
) -> Tuple[Factura, bool, str]:
    """
    Registra la factura del pedido activo e intenta imprimirla en Colpos.

    Retorna (factura, éxito_impresión, mensaje). La factura queda guardada
    aunque falle la impresión física.
    """
    factura = crear_factura(
        pedido_id,
        metodo_pago,
        descuento,
        comprador_nombre=comprador_nombre,
        comprador_identificacion=comprador_identificacion,
    )
    datos = obtener_datos_impresion(factura.id)
    if datos is None:
        return factura, False, "No se pudieron cargar los datos de la factura."
    ok, mensaje = _imprimir_datos_factura(datos)
    return factura, ok, mensaje


@requiere_rol("cajero", "supervisor", "administrador")
def dividir_e_imprimir_cuenta(
    pedido_id: int,
    num_personas: int,
    asignaciones: Dict[int, Union[int, str]],
    metodo_pago: str = "efectivo",
    comprador_nombre: str = "",
    comprador_identificacion: str = "",
) -> Tuple[List[Factura], List[Tuple[int, bool, str]]]:
    """
    Divide el pedido en N facturas e intenta imprimir cada una.

    Retorna (facturas, resultados_impresión) donde cada resultado es
    (factura_id, éxito, mensaje).
    """
    facturas = dividir_cuenta(
        pedido_id,
        num_personas,
        asignaciones,
        metodo_pago=metodo_pago,
        comprador_nombre=comprador_nombre,
        comprador_identificacion=comprador_identificacion,
    )
    resultados: List[Tuple[int, bool, str]] = []
    for factura in facturas:
        ok, mensaje = imprimir_factura(factura.id)
        resultados.append((factura.id, ok, mensaje))
    return facturas, resultados

